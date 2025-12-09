#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import asyncio
import json
import re
import random
import ssl
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple, Any
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse, unquote

try:
    import aiohttp
    from aiohttp import ClientSession, TCPConnector, ClientTimeout
    from bs4 import BeautifulSoup
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install aiohttp beautifulsoup4 rich")
    sys.exit(1)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

IGNORED_EXTENSIONS = {
    ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".pdf", ".zip", ".gz", ".tar", ".rar",
    ".webp", ".xml", ".bmp", ".tiff", ".otf", ".mov", ".avi", ".wmv", ".flv"
}

URL_REGEX = re.compile(
    r"""(?:"|'|`)(((?:[a-zA-Z]{1,10}://|//)[^"'`\s]{1,}\.[a-zA-Z]{2,}[^"'`\s]*)|((?:/|\.\./|\./)[^"'`\s]*?))(?:"|'|`)""",
    re.IGNORECASE
)

PATH_REGEX = re.compile(r'(?:href|src|action|data-url|data-src)=["\']([^"\']+)["\']', re.IGNORECASE)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

API_REGEX = re.compile(r'["\'](/api/[^"\']+)["\']', re.IGNORECASE)

SECRET_PATTERNS = [
    (re.compile(r'(?:api[_-]?key|apikey)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{20,})["\']', re.I), "api_key"),
    (re.compile(r'(?:secret|token|password|passwd|pwd)["\']?\s*[:=]\s*["\']([^"\']{8,})["\']', re.I), "secret"),
    (re.compile(r'(?:aws_access_key_id)["\']?\s*[:=]\s*["\']([A-Z0-9]{20})["\']', re.I), "aws_key"),
]


@dataclass
class Config:
    target: str
    threads: int = 15
    timeout: int = 15
    max_depth: int = 4
    output_file: Optional[Path] = None
    verbose: bool = False
    use_wayback: bool = False
    headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.headers:
            self.headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": random.choice(USER_AGENTS),
                "Cache-Control": "no-cache",
            }


class StateManager:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.urls_processed = 0
        self.urls_failed = 0
        self.queue_size = 0
        self.current_url = "Initializing..."
        self.start_time = datetime.now()
        self.assets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.seen_values: Dict[str, Set[str]] = defaultdict(set)
        self.logs: List[str] = []
        self.root_domain: str = ""
        self.is_running = True
        self.lock = asyncio.Lock()

    async def add_asset(self, category: str, value: str, source: str, context: str = ""):
        if not value or len(value) > 1000:
            return

        value = value.strip()
        if not value:
            return

        async with self.lock:
            if value in self.seen_values[category]:
                return

            self.seen_values[category].add(value)
            self.assets[category].append({
                "value": value,
                "source": source,
                "context": context,
                "timestamp": datetime.now().isoformat()
            })

            if category in ["api_endpoints", "secrets", "subdomains", "forms"]:
                display = value[:60] + "..." if len(value) > 60 else value
                self.log(f"[green]+[/] {category}: {display}")

    def log(self, message: str, force: bool = False):
        if not self.verbose and not force and "[dim]" in message:
            return

        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[dim]{ts}[/] {message}"
        self.logs.append(entry)
        if len(self.logs) > 12:
            self.logs.pop(0)

    def get_duration(self) -> str:
        diff = datetime.now() - self.start_time
        secs = int(diff.total_seconds())
        return f"{secs // 60:02d}:{secs % 60:02d}"

    def get_stats(self) -> Dict[str, int]:
        return {cat: len(items) for cat, items in self.assets.items()}


class UIManager:
    def __init__(self, state: StateManager, config: Config):
        self.state = state
        self.config = config
        self.console = Console()

    def create_layout(self) -> Layout:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="logs", size=14)
        )
        layout["body"].split_row(
            Layout(name="stats", ratio=1),
            Layout(name="findings", ratio=1)
        )
        return layout

    def render(self) -> Layout:
        layout = self.create_layout()

        target = self.state.root_domain or self.config.target
        status_color = "green" if self.state.is_running else "yellow"
        header_style = "bold white on blue"
        if self.state.urls_failed > 100:
            header_style = "bold white on red"

        layout["header"].update(
            Panel(
                f"[bold]ReconMapper Pro[/] | Target: [cyan]{target}[/] | Status: [{status_color}]{'Running' if self.state.is_running else 'Done'}[/]",
                style=header_style
            )
        )

        stats_table = Table(show_header=False, box=None, expand=True, padding=(0, 1))
        stats_table.add_column("Key", style="bold")
        stats_table.add_column("Value")

        stats_table.add_row("Duration", f"[cyan]{self.state.get_duration()}[/]")
        stats_table.add_row("Processed", f"[green]{self.state.urls_processed}[/]")
        stats_table.add_row("Failed", f"[red]{self.state.urls_failed}[/]")
        stats_table.add_row("Queue", f"[yellow]{self.state.queue_size}[/]")
        stats_table.add_row("Threads", f"{self.config.threads}")

        current = self.state.current_url
        if len(current) > 45:
            current = current[:42] + "..."
        stats_table.add_row("Current", f"[dim]{current}[/]")

        layout["stats"].update(Panel(stats_table, title="Status", border_style="blue"))

        findings_table = Table(show_header=True, expand=True, header_style="bold magenta")
        findings_table.add_column("Category", style="cyan")
        findings_table.add_column("Count", justify="right", style="green")

        total = 0
        categories = [
            "subdomains", "api_endpoints", "forms", "parameters",
            "files", "emails", "secrets", "app_routes", "urls"
        ]

        for cat in categories:
            count = len(self.state.assets.get(cat, []))
            if count > 0:
                findings_table.add_row(cat.replace("_", " ").title(), str(count))
                total += count

        findings_table.add_row("─" * 15, "─" * 5, style="dim")
        findings_table.add_row("[bold]Total[/]", f"[bold]{total}[/]")

        layout["findings"].update(Panel(findings_table, title="Findings", border_style="magenta"))

        log_content = "\n".join(self.state.logs) if self.state.logs else "[dim]Waiting for events...[/]"
        layout["logs"].update(Panel(log_content, title="Activity Log", border_style="dim"))

        return layout


class Crawler:
    def __init__(self, config: Config, state: StateManager):
        self.config = config
        self.state = state
        self.queue: asyncio.Queue[Tuple[str, int]] = asyncio.Queue()
        self.visited: Set[str] = set()
        self.base_domain: str = ""
        self.base_url: str = ""
        self.session: Optional[ClientSession] = None
        self.running = True

    def normalize_url(self, url: str, base: str = "") -> Optional[str]:
        try:
            url = url.strip()
            if not url:
                return None

            if url.startswith("javascript:") or url.startswith("mailto:") or url.startswith("data:"):
                return None

            if url.startswith("//"):
                url = "https:" + url
            elif not url.startswith(("http://", "https://")):
                if base:
                    url = urljoin(base, url)
                else:
                    return None

            parsed = urlparse(url)
            if not parsed.netloc:
                return None

            path = parsed.path or "/"
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                path,
                "",
                parsed.query,
                ""
            ))

            return normalized

        except Exception:
            return None

    def is_in_scope(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower().replace("www.", "")

            if not self.base_domain:
                return False

            return netloc == self.base_domain or netloc.endswith("." + self.base_domain)

        except Exception:
            return False

    def is_valid_path(self, path: str) -> bool:
        if not path:
            return True

        suffix = Path(path).suffix.lower()
        return suffix not in IGNORED_EXTENSIONS

    async def initialize(self):
        target = self.config.target
        if not target.startswith(("http://", "https://")):
            target = "https://" + target

        self.state.log(f"Initializing scan for: {target}", force=True)

        try:
            async with self.session.get(target, allow_redirects=True, timeout=ClientTimeout(total=20)) as resp:
                final_url = str(resp.url)
                parsed = urlparse(final_url)

                self.base_domain = parsed.netloc.lower().replace("www.", "")
                self.base_url = f"{parsed.scheme}://{parsed.netloc}"
                self.state.root_domain = self.base_domain

                self.state.log(f"[green]Connected![/] Base: {self.base_domain}", force=True)

                await self.enqueue(final_url, 0)

                try:
                    html = await resp.text(errors="ignore")
                    await self.extract_from_html(html, final_url, 0)
                except Exception:
                    pass

        except Exception as e:
            self.state.log(f"[red]Connection failed: {e}[/]", force=True)
            parsed = urlparse(target)
            self.base_domain = parsed.netloc.lower().replace("www.", "")
            self.base_url = f"{parsed.scheme}://{parsed.netloc}"
            self.state.root_domain = self.base_domain
            await self.enqueue(target, 0)

    async def enqueue(self, url: str, depth: int):
        if depth > self.config.max_depth:
            return

        normalized = self.normalize_url(url)
        if not normalized:
            return

        if not self.is_in_scope(normalized):
            return

        parsed = urlparse(normalized)
        if not self.is_valid_path(parsed.path):
            return

        key = normalized.split("?")[0]
        if key in self.visited:
            return

        self.visited.add(key)
        await self.queue.put((normalized, depth))
        self.state.queue_size = self.queue.qsize()

        netloc = parsed.netloc.lower().replace("www.", "")
        if netloc != self.base_domain and netloc.endswith("." + self.base_domain):
            await self.state.add_asset("subdomains", netloc, url, "discovered")

    async def fetch_wayback(self):
        if not self.base_domain:
            return

        self.state.log("Fetching Wayback Machine archives...", force=True)

        url = f"https://web.archive.org/cdx/search/cdx?url=*.{self.base_domain}/*&output=json&fl=original&collapse=urlkey&limit=500"

        try:
            async with self.session.get(url, timeout=ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return

                data = await resp.json()
                count = 0

                for item in data[1:]:
                    if count >= 300:
                        break
                    try:
                        archived_url = item[0]
                        await self.enqueue(archived_url, 1)
                        count += 1
                    except Exception:
                        continue

                self.state.log(f"[green]Wayback:[/] Added {count} URLs", force=True)

        except Exception as e:
            self.state.log(f"[yellow]Wayback failed: {e}[/]")

    async def worker(self, worker_id: int):
        while self.running:
            try:
                url, depth = await asyncio.wait_for(self.queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                if self.queue.empty():
                    await asyncio.sleep(0.5)
                continue
            except asyncio.CancelledError:
                break

            self.state.current_url = url
            self.state.queue_size = self.queue.qsize()

            try:
                await self.process_url(url, depth)
                self.state.urls_processed += 1
            except Exception as e:
                self.state.urls_failed += 1
                if self.config.verbose:
                    self.state.log(f"[red]Error:[/] {str(e)[:50]}")
            finally:
                self.queue.task_done()

    async def process_url(self, url: str, depth: int):
        timeout = ClientTimeout(total=self.config.timeout)

        async with self.session.get(url, allow_redirects=True, timeout=timeout) as resp:
            if self.config.verbose:
                color = "green" if resp.status < 300 else ("yellow" if resp.status < 400 else "red")
                self.state.log(f"[{color}]{resp.status}[/] {url[:60]}")

            content_type = resp.headers.get("Content-Type", "").lower()

            self.extract_params(str(resp.url))

            if resp.status >= 400:
                return

            if "text/html" in content_type or "application/xhtml" in content_type:
                try:
                    html = await resp.text(errors="ignore")
                    await self.extract_from_html(html, str(resp.url), depth)
                except Exception:
                    pass

            elif "javascript" in content_type or "application/json" in content_type:
                try:
                    text = await resp.text(errors="ignore")
                    await self.extract_from_text(text, str(resp.url))
                except Exception:
                    pass

    async def extract_from_html(self, html: str, source: str, depth: int):
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return

        base_tag = soup.find("base", href=True)
        base = base_tag["href"] if base_tag else source

        for script in soup.find_all("script"):
            src = script.get("src")
            if src:
                full_url = self.normalize_url(src, base)
                if full_url:
                    await self.state.add_asset("files", full_url, source, "script")
                    await self.enqueue(full_url, depth + 1)

            if script.string:
                await self.extract_from_text(script.string, source)

        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            full_url = self.normalize_url(href, base)
            if full_url and self.is_in_scope(full_url):
                await self.enqueue(full_url, depth + 1)

        for tag in soup.find_all(["link", "img", "iframe", "embed", "source"], src=True):
            src = tag.get("src") or tag.get("href")
            if src:
                full_url = self.normalize_url(src, base)
                if full_url:
                    await self.state.add_asset("files", full_url, source, tag.name)

        for form in soup.find_all("form"):
            action = form.get("action", "")
            method = form.get("method", "GET").upper()
            full_url = self.normalize_url(action, base) if action else source

            if full_url:
                form_str = f"{method} {full_url}"
                await self.state.add_asset("forms", form_str, source, "html_form")

                for inp in form.find_all(["input", "select", "textarea"]):
                    name = inp.get("name")
                    if name:
                        await self.state.add_asset("parameters", name, full_url, "form_input")

        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data and next_data.string:
            try:
                data = json.loads(next_data.string)
                await self.extract_from_json(data, source)
            except Exception:
                pass

        await self.extract_from_text(html, source)

    async def extract_from_text(self, text: str, source: str):
        for match in URL_REGEX.finditer(text):
            try:
                raw = match.group(1)
                if not raw or len(raw) < 3:
                    continue

                raw = raw.strip("\"'` ")

                if any(c in raw for c in ["{", "}", "$", "{{", "}}"]):
                    continue

                full_url = self.normalize_url(raw, source)
                if full_url:
                    if self.is_in_scope(full_url):
                        await self.state.add_asset("urls", full_url, source, "regex")

                    if "/api/" in full_url or "api." in full_url:
                        await self.state.add_asset("api_endpoints", full_url, source, "regex")

            except Exception:
                continue

        for match in API_REGEX.finditer(text):
            try:
                path = match.group(1)
                full_url = self.normalize_url(path, source)
                if full_url:
                    await self.state.add_asset("api_endpoints", full_url, source, "api_pattern")
            except Exception:
                continue

        for email in EMAIL_REGEX.findall(text):
            if len(email) < 100:
                await self.state.add_asset("emails", email, source, "regex")

        for pattern, secret_type in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    secret = match.group(1)
                    if len(secret) < 200:
                        await self.state.add_asset("secrets", f"{secret_type}: {secret[:50]}...", source, secret_type)
                except Exception:
                    continue

    async def extract_from_json(self, data: Any, source: str, prefix: str = ""):
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ["page", "route", "asPath", "pathname", "href", "url"]:
                    if isinstance(value, str) and value.startswith("/"):
                        full = self.normalize_url(value, source)
                        if full:
                            await self.state.add_asset("app_routes", full, source, "json_extract")

                await self.extract_from_json(value, source, f"{prefix}.{key}")

        elif isinstance(data, list):
            for item in data:
                await self.extract_from_json(item, source, prefix)

        elif isinstance(data, str):
            if data.startswith("/") and len(data) > 1:
                full = self.normalize_url(data, source)
                if full and self.is_in_scope(full):
                    await self.state.add_asset("app_routes", full, source, "json_string")

    def extract_params(self, url: str):
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            for key in params.keys():
                asyncio.create_task(self.state.add_asset("parameters", key, url, "query_string"))

        except Exception:
            pass

    async def run(self):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        connector = TCPConnector(
            limit=self.config.threads * 2,
            limit_per_host=self.config.threads,
            ssl=ssl_ctx,
            enable_cleanup_closed=True
        )

        timeout = ClientTimeout(total=self.config.timeout, connect=10)

        async with ClientSession(
            connector=connector,
            headers=self.config.headers,
            timeout=timeout,
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        ) as session:
            self.session = session

            await self.initialize()

            if self.config.use_wayback:
                asyncio.create_task(self.fetch_wayback())

            workers = []
            for i in range(self.config.threads):
                worker = asyncio.create_task(self.worker(i))
                workers.append(worker)

            await self.queue.join()

            self.running = False
            self.state.is_running = False

            for w in workers:
                w.cancel()

            await asyncio.gather(*workers, return_exceptions=True)


async def run_scan(config: Config):
    state = StateManager(verbose=config.verbose)
    ui = UIManager(state, config)
    crawler = Crawler(config, state)

    async def update_display(live: Live):
        while state.is_running:
            try:
                live.update(ui.render())
                await asyncio.sleep(0.25)
            except Exception:
                pass

    console = Console()

    try:
        with Live(ui.render(), console=console, refresh_per_second=4, screen=True) as live:
            ui_task = asyncio.create_task(update_display(live))

            try:
                await crawler.run()
            except Exception as e:
                state.log(f"[red]Fatal: {e}[/]", force=True)

            await asyncio.sleep(1)
            ui_task.cancel()

    except Exception:
        pass

    console.print()
    console.print(Panel(f"[bold green]Scan Complete[/] | Duration: {state.get_duration()}", style="green"))
    console.print(f"[bold]Processed:[/] {state.urls_processed} | [bold]Failed:[/] {state.urls_failed}")
    console.print()

    stats = state.get_stats()
    if stats:
        table = Table(title="Summary", show_header=True, header_style="bold cyan")
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="green")

        for cat, count in sorted(stats.items(), key=lambda x: -x[1]):
            if count > 0:
                table.add_row(cat.replace("_", " ").title(), str(count))

        console.print(table)
        console.print()

    result = {
        "target": config.target,
        "base_domain": state.root_domain,
        "scan_date": datetime.now().isoformat(),
        "duration": state.get_duration(),
        "stats": {
            "processed": state.urls_processed,
            "failed": state.urls_failed
        },
        "summary": stats,
        "assets": {k: v for k, v in state.assets.items()}
    }

    if config.output_file:
        try:
            with open(config.output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            console.print(f"[green]Report saved:[/] {config.output_file}")
        except Exception as e:
            console.print(f"[red]Failed to save report: {e}[/]")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="ReconMapper Pro - Web Asset Discovery Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("target", help="Target domain or URL")
    parser.add_argument("-t", "--threads", type=int, default=15, help="Number of concurrent threads")
    parser.add_argument("-d", "--depth", type=int, default=4, help="Maximum crawl depth")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--wayback", action="store_true", help="Include Wayback Machine URLs")

    args = parser.parse_args()

    config = Config(
        target=args.target,
        threads=args.threads,
        timeout=args.timeout,
        max_depth=args.depth,
        output_file=Path(args.output) if args.output else None,
        verbose=args.verbose,
        use_wayback=args.wayback
    )

    try:
        asyncio.run(run_scan(config))
    except KeyboardInterrupt:
        print("\n[!] Scan interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
