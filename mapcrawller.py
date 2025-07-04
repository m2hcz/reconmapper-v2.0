#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse, asyncio, json, logging, re, urllib.robotparser, xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple, TypeVar, Generic
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table

T = TypeVar("T")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
DEF_TIMEOUT = 15
MAX_THREADS = 100
IGN_EXT = {".css"}
URL_RX = re.compile(r"[\"'()](?P<u>/(?!/)[\w./\-]*\??[\w=&\-]*|https?://[\w./\-]+\??[\w=&\-]*)[\"'()]")
CAT_ORDER = ("api_endpoints", "directories", "files", "parameters", "inputs", "source_files", "subdomains")

@dataclass(slots=True, frozen=True)
class Cfg(Generic[T]):
    target: T
    threads: T = 10
    timeout: T = DEF_TIMEOUT
    max_depth: T = 5
    out: Optional[T] = None
    summary: Optional[T] = None
    verbose: T = False
    wayback: T = False

class ReconMapper:
    def __init__(self, cfg: Cfg):
        self.cfg = cfg
        self.console = Console()
        logging.basicConfig(level="NOTSET", format="%(message)s",
                            handlers=[RichHandler(console=self.console, show_time=False, show_path=False)])
        self.log = logging.getLogger("ReconMapper")
        self.log.setLevel(logging.DEBUG if cfg.verbose else logging.INFO)
        self.base = urlparse(f"https://{cfg.target}").hostname or cfg.target
        self.q: asyncio.Queue[Tuple[str, int]] = asyncio.Queue()
        self.visit: Set[str] = set()
        self.assets: Dict[str, Set[str]] = {c: set() for c in CAT_ORDER}
        self.assets["subdomains"].add(self.base)
        self.rp = urllib.robotparser.RobotFileParser()
        self.sem = asyncio.Semaphore(cfg.threads)

    async def run(self):
        if self.cfg.out:
            Path(self.cfg.out).write_text("")
        await self._bootstrap()
        await self._crawl()
        self._show()

    async def _bootstrap(self):
        async with aiohttp.ClientSession(headers={"User-Agent": UA}, timeout=ClientTimeout(total=self.cfg.timeout)) as s:
            r_url = urlunparse(("https", self.cfg.target, "/robots.txt", "", "", ""))      
            try:
                async with s.get(r_url) as r:
                    if r.ok:
                        self.rp.parse((await r.text()).splitlines())
                        for sm in self.rp.sitemaps or []:
                            await self._sitemap(s, sm)
            except Exception:
                pass
            if self.cfg.wayback:
                await self._wayback(s)
        await self._enqueue(urlunparse(("https", self.cfg.target, "/", "", "", "")), 0)    

    async def _sitemap(self, s: aiohttp.ClientSession, u: str):
        try:
            async with s.get(u) as r:
                if r.status != 200:
                    return
                ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                for n in ET.fromstring(await r.text()).findall("ns:url", ns):
                    loc = n.findtext("ns:loc", default="", namespaces=ns)
                    if loc:
                        await self._enqueue(loc.strip(), 0)
        except Exception:
            pass

    async def _wayback(self, s: aiohttp.ClientSession):
        wb = f"http://web.archive.org/cdx/search/cdx?url=*.{self.base}/*&output=json&fl=original&collapse=urlkey"
        try:
            async with s.get(wb) as r:
                if r.status != 200:
                    return
                for item in (await r.json())[1:]:
                    await self._enqueue(item[0], 0)
        except Exception:
            pass

    async def _crawl(self):
        workers = [asyncio.create_task(self._worker()) for _ in range(self.cfg.threads)]   
        with Progress(SpinnerColumn(), *Progress.get_default_columns(), BarColumn(),       
                      TextColumn("[cyan]{task.description}"), console=self.console) as p:  
            task = p.add_task("Crawling", total=None)
            await self.q.join()
            for _ in workers:
                await self.q.put(("", -1))
            await asyncio.gather(*workers, return_exceptions=True)
            p.update(task, description="✔ Done", total=1, completed=1)

    async def _worker(self):
        async with aiohttp.ClientSession(headers={"User-Agent": UA},
                                         timeout=ClientTimeout(total=self.cfg.timeout)) as 
s:
            while True:
                url, d = await self.q.get()
                if d < 0:
                    self.q.task_done()
                    break
                try:
                    async with self.sem:
                        if d < self.cfg.max_depth:
                            if await self._html(s, url):
                                await self._parse_html(s, url, d)
                            else:
                                await self._parse_static(s, url)
                finally:
                    self.q.task_done()

    async def _html(self, s: aiohttp.ClientSession, u: str) -> bool:
        try:
            async with s.head(u, allow_redirects=True, timeout=5) as r:
                return "text/html" in r.headers.get("content-type", "")
        except Exception:
            return True

    async def _parse_html(self, s: aiohttp.ClientSession, u: str, d: int):
        try:
            async with s.get(u, allow_redirects=True) as r:
                if not r.ok:
                    return
                ct = r.headers.get("content-type", "").lower()
                if "application/json" in ct:
                    self._found("api_endpoints", str(r.url))
                    return
                html = await r.text()
        except Exception:
            return
        for link in await self._links(html, str(r.url)):
            await self._enqueue(link, d + 1)

    async def _parse_static(self, s: aiohttp.ClientSession, u: str):
        try:
            async with s.get(u) as r:
                if not r.ok:
                    return
                ct = r.headers.get("content-type", "").lower()
                if "application/json" in ct:
                    self._found("api_endpoints", str(r.url))
                    return
                if "javascript" in ct:
                    js = await r.text()
                    for m in URL_RX.finditer(js):
                        await self._enqueue(urljoin(u, m.group("u")), 0)
                    await self._sourcemap(s, u)
        except Exception:
            pass

    async def _sourcemap(self, s: aiohttp.ClientSession, js: str):
        try:
            async with s.get(f"{js}.map") as r:
                if r.status == 200:
                    for src in (await r.json()).get("sources", []):
                        self._found("source_files", src)
        except Exception:
            pass

    async def _links(self, html: str, base: str) -> Set[str]:
        soup = BeautifulSoup(html, "html.parser")
        res: Set[str] = set()
        for t in soup.find_all(["input", "textarea", "select", "form"]):
            n = t.get("name") or t.get("id")
            if n:
                self._found("inputs", f"{t.name}:{n}:{t.get('type') if t.name=='input' else t.name}")
        raw = {t.get(a) for t in soup.find_all(True, href=True)
               for a in ("href", "src", "action", "data-src") if t.get(a)}
        raw.update(m.group("u") for m in URL_RX.finditer(html))
        for u in raw:
            full = urljoin(base, u.strip())
            p = urlparse(full)
            for param in parse_qs(p.query):
                self._found("parameters", param)
            path = p.path or "/"
            if path != "/" and Path(path).suffix:
                self._found("files", path)
            for d in Path(path).parents:
                if str(d) != ".":
                    self._found("directories", str(d))
            res.add(full)
        return res

    async def _enqueue(self, u: str, d: int):
        p = urlparse(u)
        if p.scheme not in ("http", "https"):
            return
        if p.hostname and not (p.hostname == self.base or p.hostname.endswith("." + self.base)):
            return
        if Path(p.path).suffix.lower() in IGN_EXT:
            return
        if self.rp.can_fetch(UA, u) is False:
            return
        n = urlunparse((p.scheme, p.netloc.lower(), re.sub(r"/+", "/", p.path) or "/", "", 
"", ""))
        if n in self.visit:
            return
        self.visit.add(n)
        self.q.put_nowait((u, d))
        if self.cfg.verbose:
            self.log.debug(f"[queue] D={d} {u}")

    def _found(self, c: str, v: str):
        if v not in self.assets[c]:
            self.assets[c].add(v)
            if self.cfg.verbose:
                self.log.debug(f"[{c}] {v}")

    def _show(self):
        if self.cfg.summary:
            data = {k: sorted(self.assets[k]) for k in CAT_ORDER if self.assets[k]}        
            data["generated_at"] = datetime.now(timezone.utc).isoformat()
            Path(self.cfg.summary).write_text(json.dumps(data, ensure_ascii=False, indent=2))
        t = Table(title="ReconMapper Summary")
        t.add_column("Asset")
        t.add_column("Count", justify="right")
        for c in CAT_ORDER:
            t.add_row(c, str(len(self.assets[c])))
        self.console.print(t)

def parse_args() -> Cfg:
    p = argparse.ArgumentParser(description="ReconMapper async crawler")
    p.add_argument("-t", "--target", required=True)
    p.add_argument("-T", "--threads", type=int, default=10)
    p.add_argument("--timeout", type=int, default=DEF_TIMEOUT)
    p.add_argument("--max-depth", type=int, default=5)
    p.add_argument("-o", "--out")
    p.add_argument("--summary")
    p.add_argument("--wayback", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    if not (1 <= a.threads <= MAX_THREADS):
        a.threads = 10
    dom = urlparse(f"https://{a.target}").hostname or ""
    if not dom:
        raise SystemExit("Invalid target")
    return Cfg(dom, a.threads, a.timeout, a.max_depth, a.out, a.summary, a.verbose, a.wayback)

def main():
    cfg = parse_args()
    try:
        asyncio.run(ReconMapper(cfg).run())
    except KeyboardInterrupt:
        print("Interrupted")

if __name__ == "__main__":
    main()
