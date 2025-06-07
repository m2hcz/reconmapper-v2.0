from __future__ import annotations
import argparse
import asyncio
import json
import logging
import re
import socket
import urllib.parse as up
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page

URL_REGEX = re.compile(r'[\'"\(](?P<url>/[a-zA-Z0-9_./-]*|https?://[a-zA-Z0-9_./-]+)[\'"\)]')
IGNORED_EXTENSIONS = {'.css', '.ico', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.pdf', '.zip', '.mp4', '.avi', '.mov'}

@dataclass(slots=True, frozen=True)
class Cfg:
    target: str
    threads: int = 10
    timeout: int = 15
    max_depth: int = 5
    out: Optional[str] = None
    summary: Optional[str] = None
    verbose: bool = False
    headless: bool = True

class ReconMapper:
    def __init__(self, cfg: Cfg) -> None:
        self.cfg = cfg
        self.base_host = up.urlparse(f"https://{cfg.target}").hostname
        self.in_scope = lambda h: h == self.base_host or h.endswith("." + self.base_host)
        
        self.queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        self.visited: Set[str] = set()
        
        self.results: Dict[str, Set[str]] = {
            "endpoints": set(),
            "files": set(),
            "subdomains": {self.base_host},
        }
        self.cms: Dict[str, str] = {}
        
        self.robot_parser = urllib.robotparser.RobotFileParser()
        self.out_lock = asyncio.Lock()
        self.out_file = open(cfg.out, "a", encoding="utf-8") if cfg.out else None
        self.log = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(self.__class__.__name__)
        if not logger.handlers:
            logger.setLevel(logging.DEBUG if self.cfg.verbose else logging.INFO)
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    async def emit(self, event_type: str, **data) -> None:
        record = {"ts": datetime.now(timezone.utc).isoformat(), "type": event_type, **data}
        line = json.dumps(record, ensure_ascii=False)
        async with self.out_lock:
            if self.cfg.verbose:
                print(line)
            if self.out_file:
                self.out_file.write(line + "\n")
                self.out_file.flush()

    def normalize_url(self, base: str, url: str) -> Optional[str]:
        try:
            full_url = up.urljoin(base, url.strip())
            parsed = up.urlparse(full_url)
            
            if parsed.scheme not in {"http", "https"}:
                return None

            path = re.sub(r'/+', '/', parsed.path) or '/'
            clean_url = up.urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", "")).rstrip('/')
            return clean_url
        except ValueError:
            return None

    async def fetch_robots(self):
        robots_url = f"https://{self.cfg.target}/robots.txt"
        self.log.info(f"Buscando {robots_url}")
        try:
            async with self.http_session.get(robots_url, timeout=self.cfg.timeout) as response:
                if response.status == 200:
                    content = await response.text()
                    self.robot_parser.parse(content.splitlines())
                    self.log.info("robots.txt processado com sucesso.")
                else:
                    self.log.warning("robots.txt não encontrado ou inacessível.")
        except Exception as e:
            self.log.error(f"Falha ao buscar robots.txt: {e}")

    async def discover_links(self, page: Page, base_url: str) -> Set[str]:
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        found_urls = set()

        for tag in soup.find_all(['a', 'link', 'script', 'img', 'iframe', 'form'], 
                                 href=True, src=True, action=True, **{'data-src': True}):
            for attr in ['href', 'src', 'action', 'data-src']:
                if url := tag.get(attr):
                    found_urls.add(url)
        
        for match in URL_REGEX.finditer(content):
            found_urls.add(match.group('url'))

        normalized_urls = {norm_url for url in found_urls if (norm_url := self.normalize_url(base_url, url))}
        return normalized_urls

    async def process_url(self, page: Page, url: str, depth: int):
        self.log.info(f"Processando [Profundidade: {depth}]: {url}")
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.cfg.timeout * 1000)
        except Exception as e:
            self.log.warning(f"Falha ao navegar para {url}: {type(e).__name__}")
            return

        if response is None or not response.ok:
            self.log.warning(f"Resposta não OK para {url}: Status {response.status if response else 'N/A'}")
            return

        parsed_url = up.urlparse(url)
        if Path(parsed_url.path).suffix:
            if url not in self.results["files"]:
                self.results["files"].add(url)
                await self.emit("file", url=url, status=response.status)
        else:
            if url not in self.results["endpoints"]:
                self.results["endpoints"].add(url)
                await self.emit("endpoint", url=url, status=response.status)

        if depth < self.cfg.max_depth:
            links = await self.discover_links(page, url)
            for link in links:
                parsed_link = up.urlparse(link)
                if parsed_link.hostname and self.in_scope(parsed_link.hostname) and link not in self.visited:
                    if self.robot_parser.can_fetch(self.http_session.headers.get("User-Agent"), link):
                        if Path(parsed_link.path).suffix.lower() not in IGNORED_EXTENSIONS:
                            await self.queue.put((link, depth + 1))
                    else:
                        self.log.info(f"Bloqueado por robots.txt: {link}")

    async def worker(self, browser: Browser):
        page = await browser.new_page()
        while True:
            url, depth = await self.queue.get()
            if url in self.visited:
                self.queue.task_done()
                continue
            
            self.visited.add(url)
            parsed_url = up.urlparse(url)
            if parsed_url.hostname:
                self.results["subdomains"].add(parsed_url.hostname)
            
            await self.process_url(page, url, depth)
            self.queue.task_done()

    async def run(self):
        headers = {"User-Agent": f"ReconMapper/2.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
        timeout = ClientTimeout(total=self.cfg.timeout)
        self.http_session = aiohttp.ClientSession(headers=headers, timeout=timeout)

        await self.fetch_robots()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.cfg.headless)
            start_url = self.normalize_url(f"https://{self.cfg.target}", "")
            await self.queue.put((start_url, 0))

            tasks = [asyncio.create_task(self.worker(browser)) for _ in range(self.cfg.threads)]

            await self.queue.join()

            for task in tasks:
                task.cancel()
            
            await asyncio.gather(*tasks, return_exceptions=True)
            await browser.close()

        await self.http_session.close()
        if self.out_file:
            self.out_file.close()

        if self.cfg.summary:
            summary_data = {k: sorted(v) for k, v in self.results.items()}
            summary_data["cms"] = self.cms
            summary_data["generated"] = datetime.now(timezone.utc).isoformat()
            Path(self.cfg.summary).write_text(json.dumps(summary_data, indent=2, ensure_ascii=False))

        self.log.info(f"FINALIZADO - Endpoints: {len(self.results['endpoints'])} | Arquivos: {len(self.results['files'])} | Subdomínios: {len(self.results['subdomains'])}")


def main():
    parser = argparse.ArgumentParser(description="ReconMapper v2.0 - Um crawler web avançado.")
    parser.add_argument("-t", "--target", required=True, help="O domínio alvo, sem 'https://'.")
    parser.add_argument("-T", "--threads", type=int, default=10, help="Número de workers paralelos.")
    parser.add_argument("--timeout", type=int, default=15, help="Timeout em segundos para cada requisição.")
    parser.add_argument("--max-depth", type=int, default=5, help="Profundidade máxima de rastreamento.")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True, help="Executar o navegador em modo headless (sem interface gráfica).")
    parser.add_argument("-o", "--out", help="Arquivo de saída para eventos JSON (streaming).")
    parser.add_argument("--summary", help="Arquivo JSON de saída com o resumo final.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Ativa logs detalhados e eventos na tela.")
    
    args = parser.parse_args()

    cfg = Cfg(
        target=args.target,
        threads=args.threads,
        timeout=args.timeout,
        max_depth=args.max_depth,
        out=args.out,
        summary=args.summary,
        verbose=args.verbose,
        headless=args.headless
    )
    
    try:
        asyncio.run(ReconMapper(cfg).run())
    except KeyboardInterrupt:
        print("\nVarredura interrompida pelo usuário.")
    except Exception as e:
        logging.getLogger(__name__).critical(f"Um erro fatal ocorreu: {e}", exc_info=True)

if __name__ == "__main__":
    main()