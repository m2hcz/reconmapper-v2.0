#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse
import asyncio
import json
import re
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple, Any, Iterable
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl

try:
    import aiohttp
    from aiohttp import ClientSession, TCPConnector, ClientTimeout
    from bs4 import BeautifulSoup, Comment
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    sys.exit(1)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
]

IGNORED_EXTENSIONS = {
    ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".pdf", ".zip", ".gz", ".tar", ".rar",
    ".webp", ".bmp", ".tiff", ".otf", ".mov", ".avi", ".wmv", ".flv", ".iso", ".bin"
}
VALID_CATEGORIES: Set[str] = {
    "endpoints",
    "external_endpoints",
    "api_endpoints",
    "directories",
    "files",
    "inputs",
    "params",
    "forms",
    "emails",
    "cloud_buckets",
    "secrets",
    "subdomains",
    "comments",
    "tech",
}
FILTER_ALIASES: Dict[str, List[str]] = {
    "all": [], 
    "*": [],
    "endpoint": ["endpoints", "api_endpoints"],
    "endpoints": ["endpoints", "api_endpoints"],
    "api": ["api_endpoints"],
    "dir": ["directories"],
    "dirs": ["directories"],
    "directories": ["directories"],
    "file": ["files"],
    "files": ["files"],
    "input": ["inputs"],
    "inputs": ["inputs"],
    "param": ["params"],
    "params": ["params"],
    "form": ["forms"],
    "forms": ["forms"],
    "email": ["emails"],
    "emails": ["emails"],
    "bucket": ["cloud_buckets"],
    "buckets": ["cloud_buckets"],
    "cloud": ["cloud_buckets"],
    "cloud_buckets": ["cloud_buckets"],
    "secret": ["secrets"],
    "secrets": ["secrets"],
    "subdomain": ["subdomains"],
    "subdomains": ["subdomains"],
    "comment": ["comments"],
    "comments": ["comments"],
    "tech": ["tech"],
    "external": ["external_endpoints"],
    "external_endpoints": ["external_endpoints"],
}

REGEX_PATTERNS = {
    "url": re.compile(
        r"""(?:"|'|`)(((?:[a-zA-Z]{1,10}://|//)[^"'`\s]{1,}\.[a-zA-Z]{2,}[^"'`\s]*)|((?:/|\.\./|\./)[^"'`\s]*?))(?:"|'|`)""",
        re.IGNORECASE,
    ),
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}"),
    "s3_bucket": re.compile(r"[a-z0-9.-]+\.s3\.amazonaws\.com|[a-z0-9.-]+\.s3-[a-z0-9-]+\.amazonaws\.com|s3://[a-z0-9.-]+"),
    "google_cloud": re.compile(r"storage\.googleapis\.com/[a-z0-9.-]+"),
    "azure_blob": re.compile(r"[a-z0-9.-]+\.blob\.core\.windows\.net"),
}

SECRET_PATTERNS = [
    (re.compile(r'(?:api[_-]?key|apikey|x-api-key)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{20,})["\']', re.I), "Generic API Key"),
    (re.compile(r'AIza[0-9A-Za-z-_]{35}', re.I), "Google API Key"),
    (re.compile(r'xox[baprs]-([0-9a-zA-Z]{10,48})', re.I), "Slack Token"),
    (re.compile(r'https://hooks\.slack\.com/services/T[a-zA-Z0-9_]+/B[a-zA-Z0-9_]+/[a-zA-Z0-9_]+', re.I), "Slack Webhook"),
    (re.compile(r'gh[pous]_[0-9a-zA-Z]{36}', re.I), "GitHub Token"),
    (re.compile(r'(?:aws_access_key_id|aws_secret_access_key)["\']?\s*[:=]\s*["\']([A-Z0-9]{20})["\']', re.I), "AWS Access Key"),
    (re.compile(r'-----BEGIN ((?:RSA|DSA|EC|PGP) )?PRIVATE KEY-----', re.I), "Private Key"),
    (re.compile(r'(?:password|passwd|pwd|secret|token)["\']?\s*[:=]\s*["\']([^"\']{8,})["\']', re.I), "Generic Secret"),
]

@dataclass
class Config:
    target: str
    threads: int = 20
    timeout: int = 15
    max_depth: int = 3
    output_file: Optional[Path] = None
    verbose: bool = False
    use_wayback: bool = False
    proxy: Optional[str] = None
    jitter: float = 0.0
    check_sitemap: bool = True
    headers: Dict[str, str] = field(default_factory=dict)
    filters: Optional[Set[str]] = None

    def __post_init__(self):
        if not self.headers:
            self.headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": random.choice(USER_AGENTS),
                "Cache-Control": "no-cache",
            }

class StateManager:
    def __init__(self, verbose: bool = False, filters: Optional[Set[str]] = None):
        self.verbose = verbose
        self.filters = filters 
        self.start_time = datetime.now()
        self.urls_processed = 0
        self.urls_failed = 0
        self.queue_size = 0
        self.assets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.seen_values: Dict[str, Set[str]] = defaultdict(set)
        self.technologies: Set[str] = set()
        self.logs: List[str] = []
        self.root_domain: str = ""
        self.current_url: str = "Initializing..."
        self.is_running = True
        self.lock = asyncio.Lock()

    def allowed(self, category: str) -> bool:
        if self.filters is None:
            return True
        return category in self.filters

    async def add_asset(self, category: str, value: str, source: str):
        if not self.allowed(category):
            return
        if not value or len(value) > 2000:
            return
        value = value.strip()
        dedup_key = f"{category}:{value}"
        async with self.lock:
            if dedup_key in self.seen_values[category]:
                return
            self.seen_values[category].add(dedup_key)
            self.assets[category].append({
                "value": value,
                "source": source,
                "timestamp": datetime.now().isoformat()
            })
            if category in ["secrets", "cloud_buckets", "subdomains"]:
                self.log(f"[bold red]![/] {category.upper()}: [cyan]{value[:60]}[/]", force=True)

    async def add_tech(self, tech: str):
        if not self.allowed("tech"):
            return
        async with self.lock:
            self.technologies.add(tech)

    def log(self, message: str, force: bool = False):
        if not self.verbose and not force and "[dim]" in message:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[dim]{ts}[/] {message}")
        if len(self.logs) > 15:
            self.logs.pop(0)

    def get_duration(self) -> str:
        diff = datetime.now() - self.start_time
        return str(diff).split('.')[0]

class UIManager:
    def __init__(self, state: StateManager, config: Config):
        self.state = state
        self.config = config

    def create_layout(self) -> Layout:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=10)
        )
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )
        layout["left"].split(
            Layout(name="stats", size=9),
            Layout(name="tech", ratio=1)
        )
        layout["right"].split(
            Layout(name="findings", ratio=2),
            Layout(name="logs", ratio=1)
        )
        return layout

    def render(self) -> Layout:
        layout = self.create_layout()
        target = self.state.root_domain or self.config.target
        status_style = "bold white on green" if self.state.is_running else "bold white on blue"
        layout["header"].update(Panel(
            f"ReconMapper Pro | Target: [cyan]{target}[/]",
            style=status_style, subtitle=f"Time: {self.state.get_duration()}"
        ))

        stats = Table.grid(expand=True, padding=(0,1))
        stats.add_column(style="bold cyan")
        stats.add_column(justify="right")
        stats.add_row("Processed", f"[green]{self.state.urls_processed}[/]")
        stats.add_row("Failed", f"[red]{self.state.urls_failed}[/]")
        stats.add_row("Queue", f"[yellow]{self.state.queue_size}[/]")
        stats.add_row("Threads", f"{self.config.threads}")
        current = self.state.current_url[:45] + "..." if len(self.state.current_url) > 45 else self.state.current_url
        stats.add_row("Current", f"[dim]{current}[/]")
        layout["stats"].update(Panel(stats, title="Statistics", border_style="blue"))

        tech_list = "\n".join([f"• {t}" for t in sorted(self.state.technologies)]) or "[dim]Scanning...[/]"
        layout["tech"].update(Panel(tech_list, title="Tech Stack", border_style="cyan"))

        f_table = Table(show_header=True, expand=True, box=None)
        f_table.add_column("Category", style="magenta")
        f_table.add_column("Count", justify="right", style="green")

        priority_order = [
            "secrets", "cloud_buckets", "subdomains",
            "api_endpoints", "endpoints",
            "directories", "files", "params", "inputs",
            "emails", "forms", "comments", "external_endpoints",
        ]

        total = 0
        shown = set()
        for cat in priority_order:
            if self.config.filters is not None and cat not in self.config.filters:
                continue
            count = len(self.state.assets.get(cat, []))
            if count > 0:
                f_table.add_row(cat.replace("_", " ").title(), str(count))
                total += count
                shown.add(cat)

        others = sum(len(v) for k, v in self.state.assets.items() if k not in shown)
        if others > 0:
            f_table.add_row("Others", str(others))
            total += others

        layout["findings"].update(Panel(f_table, title=f"Findings (Total: {total})", border_style="magenta"))

        log_text = "\n".join(self.state.logs)
        layout["logs"].update(Panel(log_text, title="Log", border_style="dim"))
        return layout

class Analyzers:
    @staticmethod
    async def extract_technologies(headers: Dict, html_content: str, state: StateManager):
        server = headers.get('Server')
        powered = headers.get('X-Powered-By')
        if server:
            await state.add_tech(f"Server: {server}")
        if powered:
            await state.add_tech(f"Framework: {powered}")
        low = html_content.lower()
        if "wp-content" in low:
            await state.add_tech("CMS: WordPress")
        if "react" in low:
            await state.add_tech("JS: React")
        if "vue" in low:
            await state.add_tech("JS: Vue.js")
        if "bootstrap" in low:
            await state.add_tech("UI: Bootstrap")

    @staticmethod
    def normalize_url(url: str, base: str = "") -> Optional[str]:
        try:
            url = url.strip()
            if not url or url.startswith(("javascript:", "mailto:", "data:", "tel:", "#")):
                return None
            if url.startswith("//"):
                url = "https:" + url
            elif not url.startswith(("http://", "https://")):
                if base:
                    url = urljoin(base, url)
                else:
                    return None
            parsed = urlparse(url)
            clean = urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path, parsed.params, parsed.query, ""))
            return clean
        except Exception:
            return None

    @staticmethod
    def extract_query_params(url: str) -> Set[str]:
        try:
            parsed = urlparse(url)
            return {k for k, _ in parse_qsl(parsed.query, keep_blank_values=True)}
        except Exception:
            return set()

    @staticmethod
    def extract_directories(url: str) -> Set[str]:
        dirs: Set[str] = set()
        try:
            parsed = urlparse(url)
            path = parsed.path or "/"
            if not path.startswith("/"):
                path = "/" + path

            if path.endswith("/"):
                base_path = path
            else:
                base_path = path.rsplit("/", 1)[0] + "/"
                if base_path == "//":
                    base_path = "/"

            parts = [p for p in base_path.split("/") if p]
            cur = "/"
            for p in parts:
                cur = cur + p + "/"
                dirs.add(cur)
        except Exception:
            pass
        return dirs

class Crawler:
    def __init__(self, config: Config, state: StateManager):
        self.config = config
        self.state = state
        self.queue: asyncio.Queue[Tuple[str, int, str]] = asyncio.Queue()
        self.visited: Set[str] = set()
        self.base_domain: str = ""
        self.session: Optional[ClientSession] = None
        self.analyzers = Analyzers()

    def is_in_scope(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            return netloc == self.base_domain or netloc.endswith("." + self.base_domain)
        except Exception:
            return False

    def is_valid_asset(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return not any(path.endswith(ext) for ext in IGNORED_EXTENSIONS)

    async def add_url_derivatives(self, url: str, source: str):
        # directories
        for d in self.analyzers.extract_directories(url):
            await self.state.add_asset("directories", d, source)

        # params (querystring)
        for p in self.analyzers.extract_query_params(url):
            await self.state.add_asset("params", p, source)

    async def enqueue(self, url: str, depth: int, source: str = "discovery"):
        if depth > self.config.max_depth:
            return
        normalized = self.analyzers.normalize_url(url)
        if not normalized:
            return

        # Sempre registra endpoints (internos/externos) conforme escopo
        if self.is_in_scope(normalized):
            await self.state.add_asset("endpoints", normalized.split("#")[0], source)
            await self.add_url_derivatives(normalized, source)
        else:
            await self.state.add_asset("external_endpoints", normalized.split("#")[0], source)

        if not self.is_in_scope(normalized):
            return

        clean_url = normalized.split("#")[0]
        if clean_url in self.visited:
            return
        self.visited.add(clean_url)

        if not self.is_valid_asset(clean_url):
            await self.state.add_asset("files", clean_url, source)
            await self.add_url_derivatives(clean_url, source)
            return

        await self.queue.put((clean_url, depth, source))
        self.state.queue_size = self.queue.qsize()

        parsed = urlparse(clean_url)
        netloc = parsed.netloc
        if netloc != self.base_domain and netloc.endswith("." + self.base_domain):
            await self.state.add_asset("subdomains", netloc, clean_url)

    async def fetch(self, url: str) -> Tuple[Optional[str], Dict, int]:
        if self.config.jitter > 0:
            await asyncio.sleep(random.uniform(0.1, self.config.jitter))
        try:
            async with self.session.get(url, allow_redirects=True, ssl=False, proxy=self.config.proxy) as response:
                text = ""
                ct = response.headers.get("Content-Type", "").lower()
                if "text" in ct or "json" in ct or "javascript" in ct or "xml" in ct:
                    text = await response.text(errors="ignore")
                return text, dict(response.headers), response.status
        except Exception:
            return None, {}, 0

    async def process_page(self, url: str, html_content: str, headers: Dict, depth: int):
        await self.analyzers.extract_technologies(headers, html_content, self.state)
        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception:
            soup = None

        base_url = url
        if soup:
            base_tag = soup.find("base", href=True)
            base_url = base_tag["href"] if base_tag else url
            for tag in soup.find_all(href=True):
                full = self.analyzers.normalize_url(tag.get('href', ''), base_url)
                if not full:
                    continue
                await self.enqueue(full, depth + 1, source=url)

            # src files (+ scripts como “páginas” para scan)
            for tag in soup.find_all(src=True):
                full = self.analyzers.normalize_url(tag.get('src', ''), base_url)
                if not full:
                    continue
                await self.state.add_asset("files", full, url)
                await self.add_url_derivatives(full, url)
                if tag.name == "script":
                    await self.enqueue(full, depth + 1, source=url)

            # forms / inputs / params
            for form in soup.find_all("form"):
                action = form.get("action")
                method = form.get("method", "GET").upper()
                target = self.analyzers.normalize_url(action, base_url) if action else url
                if target:
                    await self.enqueue(target, depth + 1, source=url)
                    inputs = []
                    for i in form.find_all(['input', 'textarea', 'select']):
                        name = i.get('name')
                        if not name:
                            continue
                        inputs.append(name)
                        await self.state.add_asset("inputs", name, url)
                        await self.state.add_asset("params", name, url)

                    await self.state.add_asset("forms", f"{method} {target} Params: {inputs}", url)

            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                c = (comment or "").strip()
                if 4 < len(c) < 300:
                    await self.state.add_asset("comments", c, url)

        await self.scan_text_content(html_content, url)

    async def scan_text_content(self, text: str, source_url: str):
        for mail in REGEX_PATTERNS["email"].findall(text):
            await self.state.add_asset("emails", mail, source_url)
        for match in REGEX_PATTERNS["s3_bucket"].findall(text):
            await self.state.add_asset("cloud_buckets", f"AWS: {match}", source_url)
        for match in REGEX_PATTERNS["google_cloud"].findall(text):
            await self.state.add_asset("cloud_buckets", f"GCP: {match}", source_url)
        for match in REGEX_PATTERNS["azure_blob"].findall(text):
            await self.state.add_asset("cloud_buckets", f"AZURE: {match}", source_url)

        if "/api/" in text or "api." in text:
            paths = re.findall(r'["\'](/api/[^"\']+)["\']', text)
            for p in paths:
                await self.state.add_asset("api_endpoints", p, source_url)

        for pattern, name in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                val = match.group(1) if match.lastindex else match.group(0)
                await self.state.add_asset("secrets", f"{name}: {val}", source_url)

        for m in REGEX_PATTERNS["url"].finditer(text):
            raw = m.group(1)
            full = self.analyzers.normalize_url(raw, source_url)
            if not full:
                continue

            await self.enqueue(full, depth=self.config.max_depth, source=source_url)

    async def worker(self):
        while True:
            try:
                url, depth, src = await self.queue.get()
            except asyncio.CancelledError:
                return
            self.state.current_url = url
            self.state.queue_size = self.queue.qsize()
            try:
                content, headers, status = await self.fetch(url)
                if status >= 400 or status == 0:
                    self.state.urls_failed += 1
                else:
                    self.state.urls_processed += 1
                if content:
                    await self.process_page(url, content, headers, depth)
            except Exception:
                self.state.urls_failed += 1
            finally:
                self.queue.task_done()
                self.state.queue_size = self.queue.qsize()

    async def init_scan(self):
        target = self.config.target
        if not target.startswith(("http://", "https://")):
            target = "https://" + target

        self.state.log(f"Starting: {target}", force=True)
        try:
            async with self.session.get(target, timeout=10, ssl=False, proxy=self.config.proxy) as resp:
                final_url = str(resp.url)
                parsed = urlparse(final_url)
                self.base_domain = parsed.netloc.replace("www.", "")
                self.state.root_domain = self.base_domain
                await self.enqueue(final_url, 0, source="seed")
                if self.config.check_sitemap:
                    await self.check_specials(f"{parsed.scheme}://{parsed.netloc}")
        except Exception as e:
            self.state.log(f"[red]Init Error: {e}[/]", force=True)
            return False
        return True

    async def check_specials(self, base_url: str):
        r_url = urljoin(base_url, "/robots.txt")
        txt, _, s = await self.fetch(r_url)
        if s == 200 and txt:
            for line in txt.splitlines():
                if "Allow:" in line or "Disallow:" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        path = parts[1].strip()
                        if "*" not in path:
                            await self.enqueue(urljoin(base_url, path), 1, source=r_url)

        s_url = urljoin(base_url, "/sitemap.xml")
        xml, _, s = await self.fetch(s_url)
        if s == 200 and xml:
            locs = re.findall(r'<loc>(.*?)</loc>', xml)
            self.state.log(f"Sitemap: {len(locs)} URLs", force=True)
            for loc in locs:
                await self.enqueue(loc, 1, source=s_url)

    async def run_wayback(self):
        if not self.base_domain:
            return
        self.state.log("Fetching Wayback...", force=True)
        url = f"https://web.archive.org/cdx/search/cdx?url=*.{self.base_domain}/*&output=json&fl=original&collapse=urlkey&limit=500"
        try:
            async with self.session.get(url, timeout=30, proxy=self.config.proxy) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data[1:]:
                        if len(item) > 0:
                            await self.enqueue(item[0], 2, source="wayback")
        except Exception:
            pass

    async def start(self):
        connector = TCPConnector(limit=self.config.threads * 2, ssl=False)
        async with ClientSession(
            connector=connector,
            headers=self.config.headers,
            timeout=ClientTimeout(total=self.config.timeout)
        ) as session:
            self.session = session
            if not await self.init_scan():
                return
            if self.config.use_wayback:
                asyncio.create_task(self.run_wayback())
            workers = [asyncio.create_task(self.worker()) for _ in range(self.config.threads)]
            await self.queue.join()
            for w in workers:
                w.cancel()

def generate_report(config: Config, state: StateManager):
    if not config.output_file:
        return

    findings = dict(state.assets)
    if config.filters is not None:
        findings = {k: v for k, v in findings.items() if k in config.filters}

    data = {
        "target": config.target,
        "scan_time": datetime.now().isoformat(),
        "duration": state.get_duration(),
        "technologies": list(state.technologies) if (config.filters is None or "tech" in config.filters) else [],
        "stats": {
            "processed": state.urls_processed,
            "failed": state.urls_failed
        },
        "filters": sorted(list(config.filters)) if config.filters is not None else None,
        "findings": findings
    }

    try:
        if config.output_file.parent:
            config.output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config.output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[+] Report saved to: {config.output_file}")
    except Exception as e:
        print(f"[!] Error saving report: {e}")

def parse_filters(raw_filters: Optional[List[str]], parser: argparse.ArgumentParser) -> Optional[Set[str]]:
    if not raw_filters:
        return None

    selected: Set[str] = set()
    tokens: List[str] = []
    for item in raw_filters:
        tokens.extend([p.strip().lower() for p in item.split(",") if p.strip()])

    if any(t in ("all", "*") for t in tokens):
        return None

    unknown: List[str] = []
    for t in tokens:
        if t in FILTER_ALIASES:
            selected.update(FILTER_ALIASES[t])
        elif t in VALID_CATEGORIES:
            selected.add(t)
        else:
            unknown.append(t)

    if unknown:
        parser.error(f"Unknown -f/--filter category(es): {', '.join(unknown)}. Valid: {', '.join(sorted(VALID_CATEGORIES))} (aliases: endpoint, dirs, etc.)")
    return selected or None

async def main_async():
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("-t", "--threads", type=int, default=15)
    parser.add_argument("-d", "--depth", type=int, default=3)
    parser.add_argument("-o", "--output")
    parser.add_argument("--proxy")
    parser.add_argument("--wayback", action="store_true")
    parser.add_argument("--jitter", type=float, default=0.0)
    parser.add_argument("--no-sitemap", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "-f", "--filter",
        dest="filters",
        action="append",
        help=(
            "Filter categories (comma-separated, can repeat). Examples: "
            "-f endpoint,files,params or -f directories -f inputs. "
            f"Valid: {', '.join(sorted(VALID_CATEGORIES))} (aliases: endpoint, dirs, etc.). "
            "Use 'all' to disable filtering."
        ),
    )

    args = parser.parse_args()
    filters = parse_filters(args.filters, parser)

    config = Config(
        target=args.target,
        threads=args.threads,
        max_depth=args.depth,
        output_file=Path(args.output) if args.output else None,
        proxy=args.proxy,
        use_wayback=args.wayback,
        jitter=args.jitter,
        check_sitemap=not args.no_sitemap,
        verbose=args.verbose,
        filters=filters,
    )

    state = StateManager(verbose=args.verbose, filters=filters)
    ui = UIManager(state, config)
    crawler = Crawler(config, state)
    console = Console()

    try:
        with Live(ui.render(), console=console, refresh_per_second=4, screen=True) as live:
            async def update_ui():
                while state.is_running:
                    live.update(ui.render())
                    await asyncio.sleep(0.2)
            ui_task = asyncio.create_task(update_ui())
            await crawler.start()
            state.is_running = False
            await ui_task
    except KeyboardInterrupt:
        state.is_running = False
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
    finally:
        console.print(f"\n[bold green]Done![/] Duration: {state.get_duration()}")
        if config.output_file:
            generate_report(config, state)

def main():
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
