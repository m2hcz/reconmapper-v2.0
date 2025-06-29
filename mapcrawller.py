#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse, asyncio, json, logging, re, urllib.robotparser, xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from playwright.async_api import Browser, Page, Response, TimeoutError as PlaywrightTimeoutError, async_playwright
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
MAX_THREADS = 100
DEFAULT_TIMEOUT = 15
IGNORED_EXTENSIONS = {".css"}
URL_REGEX = re.compile(r"[\"'()](?P<url>/(?!/)[\w./\-]*\??[\w=&\-]*|https?://[\w./\-]+\??[\w=&\-]*)[\"'()]")

@dataclass(slots=True, frozen=True)
class Cfg:
    target: str
    threads: int = 10
    timeout: int = DEFAULT_TIMEOUT
    max_depth: int = 5
    out: Optional[str] = None
    summary: Optional[str] = None
    verbose: bool = False
    headless: bool = True
    wayback: bool = False

class ReconMapper:
    def __init__(self, cfg: Cfg) -> None:
        self.cfg = cfg
        self.console = Console()
        logging.basicConfig(level="NOTSET", format="%(message)s", handlers=[RichHandler(console=self.console, show_time=False, show_path=False)])
        self.log = logging.getLogger("ReconMapper")
        self.log.setLevel(logging.DEBUG if cfg.verbose else logging.INFO)
        self.base_host = urlparse(f"https://{cfg.target}").hostname or cfg.target
        self.queue: asyncio.Queue[Tuple[str,int]] = asyncio.Queue()
        self.visited: Set[str] = set()
        self.assets: Dict[str, Set[Any]] = defaultdict(set)
        self.robot_parser = urllib.robotparser.RobotFileParser()
        self._categories = {"directories","files","inputs","parameters","api_endpoints","source_files","subdomains"}
        for c in self._categories: self.assets[c] = set()
        self.assets["subdomains"].add(self.base_host)
    async def run(self) -> None:
        if self.cfg.out: Path(self.cfg.out).write_text("")
        await self._bootstrap()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.cfg.headless)
            try: await self._crawl(browser)
            finally: await browser.close()
        self._summarise()
    def _found(self, cat: str, val: str) -> None:
        if val not in self.assets[cat]:
            self.assets[cat].add(val)
            if self.cfg.verbose: self.log.debug(f"[{cat}] {val}")
    async def _bootstrap(self) -> None:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}, timeout=ClientTimeout(total=self.cfg.timeout)) as s:
            robots_url = urlunparse(("https", self.cfg.target, "/robots.txt", "", "", ""))
            try:
                async with s.get(robots_url) as r:
                    if r.status==200:
                        self.robot_parser.parse((await r.text()).splitlines())
                        for sm in self.robot_parser.sitemaps or []: await self._process_sitemap(s, sm)
            except: pass
            if self.cfg.wayback: await self._enqueue_wayback(s)
        await self._enqueue(urlunparse(("https", self.cfg.target, "/", "", "", "")),0)
    async def _process_sitemap(self,s:aiohttp.ClientSession,u:str)->None:
        try:
            async with s.get(u) as r:
                if r.status!=200: return
                ns={"ns":"http://www.sitemaps.org/schemas/sitemap/0.9"}
                for n in ET.fromstring(await r.text()).findall("ns:url",ns):
                    loc=n.findtext("ns:loc",default="",namespaces=ns)
                    if loc: await self._enqueue(loc.strip(),0)
        except: pass
    async def _enqueue_wayback(self,s:aiohttp.ClientSession)->None:
        wb=f"http://web.archive.org/cdx/search/cdx?url=*.{self.base_host}/*&output=json&fl=original&collapse=urlkey"
        try:
            async with s.get(wb) as r:
                if r.status!=200: return
                for item in (await r.json())[1:]: await self._enqueue(item[0],0)
        except: pass
    async def _crawl(self,browser:Browser)->None:
        workers=[asyncio.create_task(self._worker(browser)) for _ in range(self.cfg.threads)]
        with Progress(SpinnerColumn(),*Progress.get_default_columns(),BarColumn(),TextColumn("[cyan]{task.description}"),console=self.console) as prog:
            task=prog.add_task("Crawling",total=None)
            await self.queue.join()
            for _ in workers: await self.queue.put(("",-1))
            await asyncio.gather(*workers,return_exceptions=True)
            prog.update(task,description="✔ Done",total=1,completed=1)
    async def _worker(self,browser:Browser)->None:
        ctx=await browser.new_context(user_agent=USER_AGENT,ignore_https_errors=True)
        page=await ctx.new_page()
        page.on("response",self._on_response)
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT},timeout=ClientTimeout(total=self.cfg.timeout)) as s:
            while True:
                url,depth=await self.queue.get()
                if depth<0: self.queue.task_done(); break
                try:
                    if depth<self.cfg.max_depth:
                        if await self._is_html(s,url): await self._handle_html(page,url,depth)
                        else: await self._handle_static(s,url)
                finally: self.queue.task_done()
        await page.close(); await ctx.close()
    async def _handle_html(self,page:Page,url:str,depth:int)->None:
        try: await page.goto(url,wait_until="domcontentloaded",timeout=self.cfg.timeout*1000)
        except PlaywrightTimeoutError: return
        for link in await self._extract_links(await page.content(),page.url): await self._enqueue(link,depth+1)
    async def _handle_static(self,s:aiohttp.ClientSession,url:str)->None:
        try:
            async with s.get(url) as r:
                if r.ok and "javascript" in r.headers.get("content-type",""):
                    js=await r.text()
                    for m in URL_REGEX.finditer(js): await self._enqueue(urljoin(url,m.group("url")),0)
                    await self._fetch_sourcemap(s,url)
        except: pass
    async def _fetch_sourcemap(self,s:aiohttp.ClientSession,js_url:str)->None:
        try:
            async with s.get(f"{js_url}.map") as r:
                if r.status==200:
                    for src in (await r.json()).get("sources",[]): self._found("source_files",src)
        except: pass
    async def _is_html(self,s:aiohttp.ClientSession,url:str)->bool:
        try:
            async with s.head(url,allow_redirects=True,timeout=5) as r:
                return "text/html" in r.headers.get("content-type","")
        except: return True
    async def _extract_links(self,html:str,base:str)->Set[str]:
        soup=BeautifulSoup(html,"html.parser"); links:Set[str]=set()
        for tag in soup.find_all(["input","textarea","select","form"]):
            name=tag.get("name") or tag.get("id")
            if name: self._found("inputs",f"{tag.name}:{name}:{tag.get('type') if tag.name=='input' else tag.name}")
        raw={tag.get(a) for tag in soup.find_all(True,href=True) for a in ("href","src","action","data-src") if tag.get(a)}
        raw.update(m.group("url") for m in URL_REGEX.finditer(html))
        for u in raw:
            full=urljoin(base,u.strip()); p=urlparse(full)
            for param in parse_qs(p.query): self._found("parameters",param)
            path=p.path or "/"
            if path!="/" and Path(path).suffix: self._found("files",path)
            for d in Path(path).parents:
                if str(d)!=".": self._found("directories",str(d))
            links.add(full)
        return links
    async def _on_response(self,r:Response)->None:
        if "application/json" in r.headers.get("content-type","").lower(): self._found("api_endpoints",r.url)
    async def _enqueue(self,url:str,depth:int)->None:
        p=urlparse(url)
        if not p.scheme.startswith("http"): return
        if p.hostname and not (p.hostname==self.base_host or p.hostname.endswith("."+self.base_host)): return
        if Path(p.path).suffix.lower() in IGNORED_EXTENSIONS: return
        if not self.robot_parser.can_fetch(USER_AGENT,url): return
        norm=urlunparse((p.scheme,p.netloc.lower(),re.sub(r'/+','/',p.path) or '/', "","", ""))
        if norm not in self.visited:
            self.visited.add(norm)
            self.queue.put_nowait((url,depth))
            if self.cfg.verbose: self.log.debug(f"[queue] D={depth} {url}")
    def _summarise(self)->None:
        if self.cfg.summary:
            data={k:sorted(v) for k,v in self.assets.items() if v}
            data["generated_at"]=datetime.now(timezone.utc).isoformat()
            Path(self.cfg.summary).write_text(json.dumps(data,ensure_ascii=False,indent=2))
        t=Table(title="ReconMapper Summary"); t.add_column("Asset"); t.add_column("Count",justify="right")
        for k,v in sorted(self.assets.items()): t.add_row(k,str(len(v)))
        self.console.print(t)

def parse_args()->Cfg:
    p=argparse.ArgumentParser(description="ReconMapper – async crawler")
    p.add_argument("-t","--target",required=True)
    p.add_argument("-T","--threads",type=int,default=10)
    p.add_argument("--timeout",type=int,default=15)
    p.add_argument("--max-depth",type=int,default=5)
    p.add_argument("--headless",action=argparse.BooleanOptionalAction,default=True)
    p.add_argument("-o","--out"); p.add_argument("--summary")
    p.add_argument("--wayback",action="store_true")
    p.add_argument("-v","--verbose",action="store_true")
    args=p.parse_args()
    if not (1<=args.threads<=MAX_THREADS): args.threads=10
    domain=urlparse(f"https://{args.target}").hostname or ""
    if not domain: raise SystemExit("Invalid target")
    return Cfg(domain,args.threads,args.timeout,args.max_depth,args.out,args.summary,args.verbose,args.headless,args.wayback)

def main()->None:
    cfg=parse_args()
    try: asyncio.run(ReconMapper(cfg).run())
    except KeyboardInterrupt: print("Interrupted")

if __name__=="__main__": main()
