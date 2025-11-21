#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import random
import ssl
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple, Pattern, Any
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import aiohttp
from aiohttp import ClientSession, TCPConnector, ClientTimeout
from bs4 import BeautifulSoup
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

IGNORED_EXTENSIONS = {
    ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", 
    ".ttf", ".eot", ".mp4", ".mp3", ".pdf", ".zip", ".gz", ".tar", ".rar", ".webp", ".xml"
}

URL_PATTERN: Pattern = re.compile(
    r"(?:\"|')(((?:[a-zA-Z]{1,10}://|//)[^\"'/]{1,}\.[a-zA-Z]{2,}[^\"']{0,})|((?:/|\.\./|\./)[a-zA-Z0-9\-_./?=&%]{2,}))(?:\"|')"
)

EMAIL_PATTERN: Pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

@dataclass(slots=True)
class Configuration:
    input_target: str
    threads: int
    timeout: int
    max_depth: int
    output_file: Optional[Path]
    verbose: bool
    use_wayback: bool
    ignore_ssl: bool = True
    headers: Dict[str, str] = field(default_factory=lambda: {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": random.choice(USER_AGENTS)
    })

@dataclass
class AssetDetail:
    value: str
    source_url: str
    context: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

class StateManager:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.urls_processed = 0
        self.urls_failed = 0
        self.queue_size = 0
        self.current_url = "Starting..."
        self.start_time = datetime.now()
        
        self.assets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.seen_assets: Set[str] = set()
        
        self.logs: List[str] = []
        self.root_domain: str = ""
        
    def add_asset(self, category: str, value: str, source: str, context: str = "generic"):
        if not value or len(value) > 500: return
        
        unique_key = f"{category}:{value}:{source}"
        
        if unique_key not in self.seen_assets:
            self.seen_assets.add(unique_key)
            
            asset_obj = {
                "value": value,
                "source": source,
                "context": context,
                "found_at": datetime.now().isoformat()
            }
            self.assets[category].append(asset_obj)
            
            if category in ["api_endpoints", "secrets", "forms"]:
                self.log(f"[green]Found {category}:[/] {value[:40]}...")

    def log(self, message: str, force: bool = False):
        if "[dim]" in message and not self.verbose and not force:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")
        if len(self.logs) > 8:
            self.logs.pop(0)

    def get_duration(self) -> str:
        diff = datetime.now() - self.start_time
        seconds = int(diff.total_seconds())
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

class InterfaceManager:
    def __init__(self, state: StateManager, config: Configuration):
        self.state = state
        self.config = config
        self.layout = Layout()
        self._setup_layout()

    def _setup_layout(self):
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=10)
        )
        self.layout["main"].split_row(
            Layout(name="stats", ratio=1),
            Layout(name="assets", ratio=1)
        )

    def render(self) -> Layout:
        target_display = self.state.root_domain if self.state.root_domain else self.config.input_target
        header_style = "white on red" if self.state.urls_failed > 50 else "white on blue"
        
        self.layout["header"].update(Panel(f"ReconMapper Pro v2.1 | Target: [bold]{target_display}[/]", style=header_style))
        
        # Stats
        stats = Table(show_header=False, box=None, expand=True)
        stats.add_row("Status", "[green]Running[/]" if self.state.queue_size > 0 else "[yellow]Finalizing[/]")
        stats.add_row("Processed", f"{self.state.urls_processed}")
        stats.add_row("Failed", f"[red]{self.state.urls_failed}[/]")
        stats.add_row("Queue", f"{self.state.queue_size}")
        stats.add_row("Current", f"[dim]{self.state.current_url[:50]}[/]")
        
        if self.config.verbose:
            stats.add_row("Mode", "[bold cyan]VERBOSE[/]")

        self.layout["stats"].update(Panel(stats, title="Statistics", border_style="green"))

        # Assets Table
        table = Table(show_header=True, expand=True, header_style="bold magenta")
        table.add_column("Category")
        table.add_column("Unique", justify="right")
        
        total = 0
        for cat, items in self.state.assets.items():
            unique_values = len(set(i['value'] for i in items))
            total += unique_values
            if unique_values > 0:
                table.add_row(cat.replace("_", " ").title(), str(unique_values))
        
        table.add_row("TOTAL UNIQUE", str(total), style="bold")
        self.layout["assets"].update(Panel(table, title="Findings (Detailed)", border_style="magenta"))

        # Logs
        self.layout["footer"].update(Panel("\n".join(self.state.logs), title="Event Logs", border_style="grey50"))
        return self.layout

class ReconCrawler:
    def __init__(self, config: Configuration, state: StateManager):
        self.config = config
        self.state = state
        self.queue: asyncio.Queue[Tuple[str, int]] = asyncio.Queue()
        self.visited: Set[str] = set()
        self.base_domain = ""
        self.session: Optional[ClientSession] = None

    async def run(self):
        ssl_ctx = ssl.create_default_context()
        if self.config.ignore_ssl:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        connector = TCPConnector(limit=self.config.threads, ssl=ssl_ctx)
        timeout_val = None if self.config.timeout == 0 else self.config.timeout
        client_timeout = ClientTimeout(total=timeout_val, connect=10)

        async with ClientSession(connector=connector, headers=self.config.headers, timeout=client_timeout, cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
            self.session = session
            await self._pre_flight()

            if self.config.use_wayback and self.base_domain:
                asyncio.create_task(self._fetch_wayback())

            workers = [asyncio.create_task(self._worker()) for _ in range(self.config.threads)]
            await self.queue.join()
            
            for w in workers: w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

    async def _pre_flight(self):
        target = self.config.input_target
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"
        
        self.state.log(f"Pre-flight check: {target}", force=True)
        try:
            async with self.session.get(target, allow_redirects=True) as resp:
                final_url = str(resp.url)
                parsed = urlparse(final_url)
                
                self.base_domain = parsed.netloc.replace("www.", "")
                self.state.root_domain = self.base_domain
                
                if self.config.verbose:
                    self.state.log(f"Redirected to: {final_url} ({resp.status})")
                
                self.state.log(f"Scope locked to: *.{self.base_domain}", force=True)
                await self.add_url(final_url, 0)
        except Exception as e:
            self.state.log(f"[red]Pre-flight Failed: {e}[/]", force=True)
            # Fallback
            parsed = urlparse(target)
            self.base_domain = parsed.netloc.replace("www.", "")
            self.state.root_domain = self.base_domain
            await self.add_url(target, 0)

    async def _fetch_wayback(self):
        if self.config.verbose: self.state.log("Starting Wayback Machine fetch...")
        url = f"http://web.archive.org/cdx/search/cdx?url=*.{self.base_domain}/*&output=json&fl=original&collapse=urlkey&limit=300"
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    count = 0
                    for item in data[1:]:
                        if count < 200:
                            await self.add_url(item[0], 1)
                            count += 1
                    self.state.log(f"Wayback: Found {count} historical URLs", force=True)
        except: 
            if self.config.verbose: self.state.log("[yellow]Wayback fetch failed[/]")

    async def add_url(self, url: str, depth: int):
        if depth > self.config.max_depth: return
        try:
            url = url.split("#")[0]
            parsed = urlparse(url)
        except: return

        if not self.base_domain: return
        
        is_scope = self.base_domain in (parsed.netloc or "")
        if not is_scope:
            if parsed.netloc and self.base_domain in parsed.netloc:
                self.state.add_asset("subdomains", parsed.netloc, "N/A", "DNS/Link")
            return

        if self._is_ignored(parsed.path): return

        normalized = urlunparse(parsed)
        if normalized not in self.visited:
            self.visited.add(normalized)
            await self.queue.put((normalized, depth))
            self.state.queue_size = self.queue.qsize()

    def _is_ignored(self, path: str) -> bool:
        return Path(path).suffix.lower() in IGNORED_EXTENSIONS

    async def _worker(self):
        while True:
            try:
                url, depth = await self.queue.get()
                self.state.current_url = url
                self.state.queue_size = self.queue.qsize()
                try:
                    await self._process(url, depth)
                    self.state.urls_processed += 1
                except Exception as e:
                    self.state.urls_failed += 1
                    if self.config.verbose: self.state.log(f"[red]Err[/] {url}: {e}")
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break

    async def _process(self, url: str, depth: int):
        try:
            async with self.session.get(url, allow_redirects=True) as resp:
                if self.config.verbose:
                    color = "green" if resp.status < 300 else ("yellow" if resp.status < 400 else "red")
                    self.state.log(f"[{color}]{resp.status}[/] {url}")

                text = await resp.text(errors="ignore")
                
                self._extract_qs(str(resp.url))
                
                content_type = resp.headers.get("Content-Type", "").lower()
                
                if "text/html" in content_type:
                    await self._parse_html(text, str(resp.url), depth)
                
                await self._regex_extract(text, str(resp.url))
        except Exception as e:
            raise e

    async def _parse_html(self, html: str, base: str, depth: int):
        soup = BeautifulSoup(html, "html.parser")
        
        # Next.js Data
        data = soup.find("script", id="__NEXT_DATA__")
        if data:
            try:
                j = json.loads(data.string)
                self._recursive_json(j, base)
                if self.config.verbose: self.state.log(f"[cyan]Parsed __NEXT_DATA__ in {base}[/]")
            except: pass

        b_tag = soup.find("base")
        if b_tag and b_tag.get("href"):
            base = urljoin(base, b_tag.get("href"))

        for tag in soup.find_all(["a", "link", "script", "img", "form", "iframe"]):
            attr = "action" if tag.name == "form" else ("src" if tag.name in ["script", "img", "iframe"] else "href")
            val = tag.get(attr)
            
            if val:
                full = urljoin(base, val)
                await self.add_url(full, depth + 1)
                
                if tag.name == "form":
                    m = tag.get("method", "GET").upper()
                    self.state.add_asset("forms", f"{m} {full}", base, "html_form")
                elif tag.name == "script":
                    self.state.add_asset("files", val, base, "script_src")

    async def _regex_extract(self, text: str, source: str):
        matches = URL_PATTERN.findall(text)
        for group in matches:
            raw = group[0]
            if not raw or len(raw) < 4: continue
            clean = raw.strip("\"' ")
            if "{" in clean or " " in clean: continue
            
            full = urljoin(source, clean)
            
            if "/api/" in full or full.endswith(".json"):
                self.state.add_asset("api_endpoints", full, source, "regex_match")
            
            p = Path(urlparse(full).path)
            if p.suffix and p.suffix not in IGNORED_EXTENSIONS:
                self.state.add_asset("files", p.name, source, "regex_file")

        for mail in EMAIL_PATTERN.findall(text):
            self.state.add_asset("emails", mail, source, "regex_email")

    def _recursive_json(self, data, base):
        if isinstance(data, dict):
            for k, v in data.items():
                if k in ["page", "route", "asPath"] and isinstance(v, str):
                    full = urljoin(base, v)
                    self.state.add_asset("app_routes", full, base, "nextjs_hydration")
                self._recursive_json(v, base)
        elif isinstance(data, list):
            for item in data:
                self._recursive_json(item, base)

    def _extract_qs(self, url: str):
        q = urlparse(url).query
        for k in parse_qs(q):
            self.state.add_asset("parameters", k, url, "query_param")

async def main_async():
    parser = argparse.ArgumentParser(description="ReconMapper Pro - Advanced Asset Discovery")
    parser.add_argument("target", help="Domain or URL to scan")
    parser.add_argument("-t", "--threads", type=int, default=10)
    parser.add_argument("-d", "--depth", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("-o", "--output", help="Output JSON file")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--wayback", action="store_true")
    args = parser.parse_args()

    config = Configuration(
        input_target=args.target,
        threads=args.threads,
        timeout=args.timeout,
        max_depth=args.depth,
        output_file=Path(args.output) if args.output else None,
        verbose=args.verbose,
        use_wayback=args.wayback
    )

    state = StateManager(verbose=args.verbose)
    ui = InterfaceManager(state, config)
    crawler = ReconCrawler(config, state)

    with Live(ui.render(), refresh_per_second=4, screen=True) as live:
        async def update_ui():
            while True:
                live.update(ui.render())
                await asyncio.sleep(0.2)
        
        ui_task = asyncio.create_task(update_ui())
        try:
            await crawler.run()
        except Exception as e:
            state.log(f"[red]Fatal Error: {e}[/]", force=True)
        finally:
            ui_task.cancel()

    console = Console()
    console.print(f"\n[bold green]Finished in {state.get_duration()}[/]")
    console.print(f"Processed: {state.urls_processed} | Failed: {state.urls_failed}")

    res = {
        "target": config.input_target,
        "date": datetime.now().isoformat(),
        "summary": {k: len(v) for k, v in state.assets.items()},
        "assets": dict(state.assets)
    }

    if config.output_file:
        with open(config.output_file, "w") as f:
            json.dump(res, f, indent=2)
        console.print(f"[blue]Detailed report saved to {config.output_file}[/]")
    else:
        pass 

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nStopped by user.")

if __name__ == "__main__":
    main()
