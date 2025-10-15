#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import urllib.robotparser
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set, Tuple, TypeVar, Generic
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse, ParseResult

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table

T = TypeVar("T")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
DEFAULT_TIMEOUT = 15
MAX_ALLOWED_THREADS = 100
IGNORED_EXTENSIONS = {".css"}
URL_PATTERN = re.compile(r"[\"'()](?P<u>/(?!/)[\w./\-]*\??[\w=&\-]*|https?://[\w./\-]+\??[\w=&\-]*)[\"'()]")
ASSET_CATEGORIES = ("api_endpoints", "directories", "files", "parameters", "inputs", "source_files", "subdomains")


@dataclass(slots=True, frozen=True)
class Configuration(Generic[T]):
    netloc: T
    hostname: T
    base_path: T = "/"
    scheme: T = "https"
    threads: T = 10
    timeout: T = DEFAULT_TIMEOUT
    max_depth: T = 5
    output_file: Optional[T] = None
    summary_file: Optional[T] = None
    verbose: T = False
    use_wayback: T = False


class ReconMapper:
    def __init__(self, config: Configuration):
        self.config = config
        self.console = Console()
        self._setup_logging()
        self.scheme = config.scheme
        self.netloc = config.netloc
        self.base_domain = config.hostname
        self.start_path = config.base_path if config.base_path else "/"
        self.url_queue: asyncio.Queue[Tuple[str, int]] = asyncio.Queue()
        self.visited_urls: Set[str] = set()
        self.discovered_assets: Dict[str, Set[str]] = {category: set() for category in ASSET_CATEGORIES}
        if self.base_domain:
            self.discovered_assets["subdomains"].add(self.base_domain)
        self.robots_parser = urllib.robotparser.RobotFileParser()
        self.semaphore = asyncio.Semaphore(config.threads)

    def _setup_logging(self):
        logging.basicConfig(
            level="NOTSET",
            format="%(message)s",
            handlers=[RichHandler(console=self.console, show_time=False, show_path=False)]
        )
        self.logger = logging.getLogger("ReconMapper")
        self.logger.setLevel(logging.DEBUG if self.config.verbose else logging.INFO)

    async def run(self):
        if self.config.output_file:
            Path(self.config.output_file).write_text("")
        await self._initialize_crawl()
        await self._execute_crawl()
        self._display_results()

    async def _initialize_crawl(self):
        async with self._create_session() as session:
            await self._fetch_robots_txt(session)
            if self.config.use_wayback and self.base_domain:
                await self._fetch_wayback_urls(session)
        start_url = urlunparse((self.scheme, self.netloc, self.start_path, "", "", ""))
        await self._add_to_queue(start_url, 0)

    async def _fetch_robots_txt(self, session: aiohttp.ClientSession):
        robots_url = urlunparse((self.scheme, self.netloc, "/robots.txt", "", "", ""))
        self.robots_parser.set_url(robots_url)
        try:
            async with session.get(robots_url) as response:
                if response.ok:
                    content = await response.text()
                    self.robots_parser.parse(content.splitlines())
                    for sitemap_url in self.robots_parser.sitemaps or []:
                        await self._process_sitemap(session, sitemap_url)
        except Exception:
            pass

    async def _process_sitemap(self, session: aiohttp.ClientSession, sitemap_url: str):
        try:
            async with session.get(sitemap_url) as response:
                if response.status != 200:
                    return
                content = await response.text()
                namespaces = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                root = ET.fromstring(content)
                for url_element in root.findall("ns:url", namespaces):
                    location = url_element.findtext("ns:loc", default="", namespaces=namespaces)
                    if location:
                        await self._add_to_queue(location.strip(), 0)
        except Exception:
            pass

    async def _fetch_wayback_urls(self, session: aiohttp.ClientSession):
        wayback_url = f"http://web.archive.org/cdx/search/cdx?url=*.{self.base_domain}/*&output=json&fl=original&collapse=urlkey"
        try:
            async with session.get(wayback_url) as response:
                if response.status != 200:
                    return
                results = await response.json()
                for item in results[1:]:
                    await self._add_to_queue(item[0], 0)
        except Exception:
            pass

    async def _execute_crawl(self):
        workers = [asyncio.create_task(self._worker()) for _ in range(self.config.threads)]
        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            BarColumn(),
            TextColumn("[cyan]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("Crawling", total=None)
            await self.url_queue.join()
            for _ in workers:
                await self.url_queue.put(("", -1))
            await asyncio.gather(*workers, return_exceptions=True)
            progress.update(task, description="✔ Done", total=1, completed=1)

    async def _worker(self):
        async with self._create_session() as session:
            while True:
                url, depth = await self.url_queue.get()
                if depth < 0:
                    self.url_queue.task_done()
                    break
                try:
                    async with self.semaphore:
                        if depth < self.config.max_depth:
                            if await self._is_html_resource(session, url):
                                await self._process_html_page(session, url, depth)
                            else:
                                await self._process_static_resource(session, url)
                finally:
                    self.url_queue.task_done()

    async def _is_html_resource(self, session: aiohttp.ClientSession, url: str) -> bool:
        try:
            async with session.head(url, allow_redirects=True, timeout=ClientTimeout(total=5)) as response:
                content_type = response.headers.get("content-type", "")
                return "text/html" in content_type
        except Exception:
            return True

    async def _process_html_page(self, session: aiohttp.ClientSession, url: str, depth: int):
        try:
            async with session.get(url, allow_redirects=True) as response:
                if not response.ok:
                    return
                content_type = response.headers.get("content-type", "").lower()
                if "application/json" in content_type:
                    self._register_asset("api_endpoints", str(response.url))
                    return
                html_content = await response.text()
                discovered_links = await self._extract_links(html_content, str(response.url))
                for link in discovered_links:
                    await self._add_to_queue(link, depth + 1)
        except Exception:
            return

    async def _process_static_resource(self, session: aiohttp.ClientSession, url: str):
        try:
            async with session.get(url) as response:
                if not response.ok:
                    return
                content_type = response.headers.get("content-type", "").lower()
                if "application/json" in content_type:
                    self._register_asset("api_endpoints", str(response.url))
                    return
                if "javascript" in content_type:
                    javascript_content = await response.text()
                    await self._extract_urls_from_javascript(javascript_content, url)
                    await self._fetch_source_map(session, url)
        except Exception:
            pass

    async def _extract_urls_from_javascript(self, javascript: str, base_url: str):
        for match in URL_PATTERN.finditer(javascript):
            extracted_url = match.group("u")
            full_url = urljoin(base_url, extracted_url)
            await self._add_to_queue(full_url, 0)

    async def _fetch_source_map(self, session: aiohttp.ClientSession, javascript_url: str):
        source_map_url = f"{javascript_url}.map"
        try:
            async with session.get(source_map_url) as response:
                if response.status == 200:
                    source_map_data = await response.json()
                    sources = source_map_data.get("sources", [])
                    for source in sources:
                        self._register_asset("source_files", source)
        except Exception:
            pass

    async def _extract_links(self, html: str, base_url: str) -> Set[str]:
        soup = BeautifulSoup(html, "html.parser")
        links = set()
        self._extract_form_inputs(soup)
        raw_urls = self._extract_raw_urls(soup, html)
        for url in raw_urls:
            full_url = urljoin(base_url, url.strip())
            self._process_url_components(full_url)
            links.add(full_url)
        return links

    def _extract_form_inputs(self, soup: BeautifulSoup):
        for tag in soup.find_all(["input", "textarea", "select", "form"]):
            name = tag.get("name") or tag.get("id")
            if name:
                tag_type = tag.get("type") if tag.name == "input" else tag.name
                identifier = f"{tag.name}:{name}:{tag_type}"
                self._register_asset("inputs", identifier)

    def _extract_raw_urls(self, soup: BeautifulSoup, html: str) -> Set[str]:
        raw_urls = set()
        for tag in soup.find_all(True):
            for attribute in ("href", "src", "action", "data-src"):
                value = tag.get(attribute)
                if value:
                    raw_urls.add(value)
        for match in URL_PATTERN.finditer(html):
            raw_urls.add(match.group("u"))
        return raw_urls

    def _process_url_components(self, url: str):
        parsed = urlparse(url)
        for parameter in parse_qs(parsed.query):
            self._register_asset("parameters", parameter)
        path = parsed.path or "/"
        if path != "/" and Path(path).suffix:
            self._register_asset("files", path)
        for directory in Path(path).parents:
            if str(directory) != ".":
                self._register_asset("directories", str(directory))

    async def _add_to_queue(self, url: str, depth: int):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return
        if not self._is_same_domain(parsed.hostname):
            return
        if self._is_ignored_extension(parsed.path):
            return
        if not self._is_allowed_by_robots(url):
            return
        normalized_url = self._normalize_url(parsed)
        if normalized_url in self.visited_urls:
            return
        self.visited_urls.add(normalized_url)
        self.url_queue.put_nowait((url, depth))
        if self.config.verbose:
            self.logger.debug(f"[queue] D={depth} {url}")

    def _is_same_domain(self, hostname: Optional[str]) -> bool:
        if not hostname or not self.base_domain:
            return False
        return hostname == self.base_domain or hostname.endswith("." + self.base_domain)

    def _is_ignored_extension(self, path: str) -> bool:
        return Path(path).suffix.lower() in IGNORED_EXTENSIONS

    def _is_allowed_by_robots(self, url: str) -> bool:
        return self.robots_parser.can_fetch(USER_AGENT, url) is not False

    def _normalize_url(self, parsed: ParseResult) -> str:
        normalized_path = re.sub(r"/+", "/", parsed.path) or "/"
        normalized_netloc = parsed.netloc.lower()
        return urlunparse((parsed.scheme, normalized_netloc, normalized_path, "", "", ""))

    def _register_asset(self, category: str, value: str):
        if value not in self.discovered_assets[category]:
            self.discovered_assets[category].add(value)
            if self.config.verbose:
                self.logger.debug(f"[{category}] {value}")

    def _display_results(self):
        if self.config.summary_file:
            self._save_summary()
        self._print_summary_table()

    def _save_summary(self):
        summary_data = {
            category: sorted(self.discovered_assets[category])
            for category in ASSET_CATEGORIES
            if self.discovered_assets[category]
        }
        summary_data["generated_at"] = datetime.now(timezone.utc).isoformat()
        json_output = json.dumps(summary_data, ensure_ascii=False, indent=2)
        Path(self.config.summary_file).write_text(json_output)

    def _print_summary_table(self):
        table = Table(title="ReconMapper Summary")
        table.add_column("Asset")
        table.add_column("Count", justify="right")
        for category in ASSET_CATEGORIES:
            count = len(self.discovered_assets[category])
            table.add_row(category, str(count))
        self.console.print(table)

    def _create_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            headers={"User-Agent": USER_AGENT},
            timeout=ClientTimeout(total=self.config.timeout)
        )


def parse_arguments() -> Configuration:
    parser = argparse.ArgumentParser(description="ReconMapper async crawler")
    parser.add_argument("-t", "--target", required=True)
    parser.add_argument("-T", "--threads", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("-o", "--out")
    parser.add_argument("--summary")
    parser.add_argument("--wayback", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    if not (1 <= args.threads <= MAX_ALLOWED_THREADS):
        args.threads = 10
    raw_target = args.target.strip()
    parsed = urlparse(raw_target if "://" in raw_target else f"https://{raw_target}")
    hostname = parsed.hostname or ""
    if not hostname:
        raise SystemExit("Invalid target")
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or hostname
    base_path = parsed.path or "/"
    if not base_path.startswith("/"):
        base_path = "/" + base_path
    return Configuration(
        netloc=netloc,
        hostname=hostname,
        base_path=base_path,
        scheme=scheme,
        threads=args.threads,
        timeout=args.timeout,
        max_depth=args.max_depth,
        output_file=args.out,
        summary_file=args.summary,
        verbose=args.verbose,
        use_wayback=args.wayback
    )


def main():
    config = parse_arguments()
    try:
        asyncio.run(ReconMapper(config).run())
    except KeyboardInterrupt:
        print("Interrupted")


if __name__ == "__main__":
    main()  
