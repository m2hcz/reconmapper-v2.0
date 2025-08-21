# ReconMapper 2.0

[![python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#)
[![async](https://img.shields.io/badge/Async-aiohttp%20%7C%20asyncio-informational.svg)](#)
[![status](https://img.shields.io/badge/Status-alpha-success.svg)](#)
[![license](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

> High-performance, async **web attack-surface mapper** for security research and appsec recon.

ReconMapper crawls a target (domain or URL), normalizes & de-duplicates URLs, honors `robots.txt`/crawl delays, pulls **sitemaps** (and optional **Wayback** seeds), and extracts artifacts that matter:

- Pages, directories, files  
- Query **parameters**  
- **API** endpoints & **OpenAPI** docs  
- **GraphQL** hints  
- **WebSocket** / **SSE** endpoints  
- **Service workers**, **manifests**  
- **Forms** and form **inputs** (CSV export)  
- **Source maps** → original **source files**  
- Observed **subdomains**

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Install](#install)
- [Quick Start](#quick-start)
- [Usage / CLI](#usage--cli)
- [Outputs](#outputs)
- [Examples](#examples)
- [How It Works](#how-it-works)
- [Tuning](#tuning)
- [Ethics & Legality](#ethics--legality)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Fast & polite** – global concurrency, per-host caps, timeouts, optional politeness delay; honors `robots.txt` (incl. `Crawl-delay`) by default.  
- **Deep extraction**  
  - HTML: `href/src/action/srcset`, meta refresh, canonical  
  - JS: `fetch`, `axios.*`, `import`, `sourceMappingURL`, GraphQL hints, SW register, WS/SSE constructors  
  - XML sitemaps (`urlset` / `sitemapindex`)  
  - `Link` headers (`preload`, `prefetch`, `canonical`, `manifest`, `api`, `service`)
- **URL hygiene** – canonicalization + removal of common tracking params (`utm_*`, `gclid`, `fbclid`, …).
- **Rich artifact buckets** – de-duplicated sets: `pages`, `api_endpoints`, `graphql_endpoints`, `websocket_endpoints`, `sse_endpoints`, `manifests`, `openapi_docs`, `parameters`, `source_files`, `forms`, `inputs`, `directories`, `files`, `subdomains`.
- **Multiple outputs** – JSON (`--out`), edge-list graph (`--graph`), forms CSV (`--forms-csv`).

---

## Requirements

- **Python 3.10+**
- Packages: `aiohttp`, `beautifulsoup4`, `rich`

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -U aiohttp beautifulsoup4 rich

> Optionally add a requirements.txt:

aiohttp>=3.9
beautifulsoup4>=4.12
rich>=13.7




---

Install

Clone and run as a standalone script (file name can be reconmapper.py):

git clone https://github.com/youruser/reconmapper
cd reconmapper
python3 reconmapper.py --help


---

Quick Start

Crawl with sitemap + Wayback seeds, export forms and a simple graph:

python3 reconmapper.py \
  --target example.com \
  --threads 48 --per-host 8 --timeout 20 --max-depth 6 \
  --wayback --politeness-ms 150 \
  --out out.json --graph edges.csv --forms-csv forms.csv \
  --verbose

Target can be a domain (example.com) or a full URL (https://example.com). Use --scheme for bare hosts.


---

Usage / CLI

The CLI mirrors the internal Cfg dataclass.

Option	Type	Default	Description

--target	str	—	Target domain/URL (example.com or https://example.com)
--threads	int	24	Global concurrency (workers)
--per-host	int	8	Concurrent requests per host
--timeout	int	20	Request timeout (seconds)
--max-depth	int	6	Crawl depth heuristic
--max-urls	int	None	Hard cap on visited URLs
--scheme	str	https	Default scheme for targets w/o protocol
--out	path	None	Write machine-readable JSON with artifacts
--summary	path	None	Optional human summary
--graph	path	None	Write edge list CSV (source,target)
--forms-csv	path	None	Export forms CSV: page,method,action,inputs
--wayback	flag	False	Seed from Internet Archive CDX
--include-css	flag	False	Include .css fetching/parsing
--include-ext	csv	None	Extra extensions to include (e.g. js,css,json)
--ignore-ext	csv	None	Extensions to ignore (comma-separated)
--include-rx	regex	None	Only enqueue URLs matching regex
--exclude-rx	regex	None	Exclude URLs matching regex
--politeness-ms	int	0	Extra per-host delay (ms)
--obey-crawl-delay / --no-obey-crawl-delay	flag	True	Respect Crawl-delay from robots.txt
-v, --verbose	flag	False	Verbose logging


> Many binary/document types are ignored by default to stay fast; tune with --include-ext / --ignore-ext.




---

Outputs

JSON (--out out.json)

> Schema may evolve; rely on top-level keys shown below.



{
  "target": "example.com",
  "started_at": "2025-08-21T16:00:00Z",
  "artifacts": {
    "pages": ["https://example.com/"],
    "api_endpoints": ["https://example.com/api/v1/users"],
    "graphql_endpoints": ["https://example.com/graphql"],
    "parameters": ["token", "redirect", "lang"],
    "directories": ["/admin", "/static", "/.well-known"],
    "files": ["/robots.txt", "/manifest.webmanifest"],
    "websocket_endpoints": ["wss://example.com/ws"],
    "sse_endpoints": ["https://example.com/stream"],
    "manifests": ["https://example.com/manifest.webmanifest"],
    "openapi_docs": ["https://example.com/openapi.json"],
    "source_files": ["src/app.tsx", "src/api/users.ts"],
    "forms": ["POST:https://example.com/login", "GET:https://example.com/search"],
    "inputs": ["input:username:text", "input:password:password"],
    "subdomains": ["example.com", "api.example.com"]
  }
}

Forms CSV (--forms-csv forms.csv)

page,method,action,inputs
https://example.com/login,POST,https://example.com/login,"username,password,csrf"

Graph (--graph edges.csv)

Edge list (source,target) for graph tools (Gephi/Graphistry/Graphviz):

https://example.com/,https://example.com/app.js
https://example.com/app.js,https://example.com/app.js.map
https://example.com/,https://example.com/api/v1/users


---

Examples

Focus on API/GraphQL, ignore images & PDFs:

python3 reconmapper.py --target example.com \
  --include-rx '(api|graphql)' \
  --ignore-ext 'png,jpg,jpeg,gif,svg,webp,pdf' \
  --out api.json --graph api_edges.csv

Wayback seeding, polite rate, cap at 5k URLs:

python3 reconmapper.py --target example.com \
  --wayback --politeness-ms 200 --max-urls 5000

Include CSS to catch @import, font manifests and map hints:

python3 reconmapper.py --target example.com --include-css

Only crawl internal paths, skip crawl-delay:

python3 reconmapper.py --target example.com \
  --include-rx '^https?://[^/]+/internal/' \
  --no-obey-crawl-delay


---

How It Works

1. Bootstrap — target normalization; robots.txt load; sitemap discovery; optional Wayback seeds.


2. Queue — prioritized asyncio.PriorityQueue with depth heuristics & per-host politeness.


3. Fetch — aiohttp GET w/ redirects; content-type sniffing & size bounds.


4. Parse —

HTML: links, forms, meta refresh, canonical, srcset

JS: fetch/axios/import, source maps → sources, GraphQL hints, WS/SSE, SW registration

XML: sitemaps (urlset / sitemapindex)

Headers: Link relations



5. Classify & Canonicalize — de-dup into buckets, strip trackers, collect parameters.


6. Output — console progress, plus optional JSON / CSV / edge graph.




---

Tuning

Increase --threads for multi-host targets; keep --per-host modest for single hosts.

Use --include-rx / --exclude-rx to focus scope (e.g., only /api/).

Combine Wayback to surface historical paths; let live crawl de-dup.

Heavy JS sites? Consider --include-css to catch import chains and source maps.



---

Ethics & Legality

Only crawl targets you’re authorized to test.

robots.txt is respected by default; keep it courteous with --politeness-ms.

Tune limits to avoid harming third-party infrastructure.



---

Roadmap

Cookie/header auth support

NDJSON / SQLite outputs

Advanced robots/sitemap overrides

HTTP method heuristics & wordlists derived from forms
