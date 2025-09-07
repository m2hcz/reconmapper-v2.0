<div align="center">

# ReconMapper 2.0

[![python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#)
[![async](https://img.shields.io/badge/Async-aiohttp%20%7C%20asyncio-informational.svg)](#)
[![status](https://img.shields.io/badge/Status-alpha-success.svg)](#)

**High‑performance, async web attack‑surface mapper** for security research and appsec recon.

</div>

> Operator‑first design: fast by default, polite by choice. Crawls ➝ extracts ➝ classifies ➝ exports.

---

## Table of Contents

* [Highlights](#highlights)
* [Requirements](#requirements)
* [Installation](#installation)
* [Quick Start](#quick-start)
* [CLI Usage](#cli-usage)
* [Outputs](#outputs)
* [Examples](#examples)
* [How It Works](#how-it-works)
* [Tuning & Performance](#tuning--performance)
* [Logging & Telemetry](#logging--telemetry)
* [Ethics & Legality](#ethics--legality)
* [Roadmap](#roadmap)
* [Contributing](#contributing)
* [License](#license)

---

## Highlights

* **Fast & polite** — global concurrency, per‑host caps, timeouts, optional politeness delay; honors `robots.txt` and `Crawl-delay` by default.
* **Deep extraction**

  * **HTML**: `href/src/action/srcset`, meta refresh, canonical
  * **JS**: `fetch`, `axios.*`, `import`, `sourceMappingURL`, GraphQL hints, Service Worker register, WS/SSE constructors
  * **XML**: sitemaps (`urlset` / `sitemapindex`)
  * **Headers**: `Link` relations (`preload`, `prefetch`, `canonical`, `manifest`, `api`, `service`)
* **URL hygiene** — canonicalization + tracker stripping (`utm_*`, `gclid`, `fbclid`, …).
* **Rich artifact buckets** — de‑duplicated sets: `pages`, `api_endpoints`, `openapi_docs`, `graphql_endpoints`, `websocket_endpoints`, `sse_endpoints`, `manifests`, `parameters`, `source_files`, `forms`, `inputs`, `directories`, `files`, `subdomains`.
* **Multiple outputs** — JSON (`--out`), edge‑list graph (`--graph`), forms CSV (`--forms-csv`).
* **Seed options** — XML sitemaps + optional **Wayback** seeds.

---

## Requirements

* **Python 3.10+**
* Packages: `aiohttp`, `beautifulsoup4`, `rich`

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -U aiohttp beautifulsoup4 rich
```

> Optional (recommended for speed/robust parsing): `lxml`.

---

## Installation

Clone and run as a standalone script (file name can be `reconmapper.py`):

```bash
git clone https://github.com/youruser/reconmapper
cd reconmapper
python3 reconmapper.py --help
```

> Prefer isolation? Use `pipx run` or a virtualenv.

---

## Quick Start

Crawl with sitemap + Wayback seeds, export forms and a simple graph:

```bash
python3 reconmapper.py \
  --target example.com \
  --threads 48 --per-host 8 --timeout 20 --max-depth 6 \
  --wayback --politeness-ms 150 \
  --out out.json --graph edges.csv --forms-csv forms.csv \
  --verbose
```

Target can be a domain (`example.com`) or a full URL (`https://example.com`). Use `--scheme` for bare hosts.

---

## CLI Usage

The CLI mirrors the internal `Cfg` dataclass.

```
Usage: reconmapper.py [options]

  --target <str>           Target domain/URL (example.com or https://example.com)
  --threads <int>          Global concurrency (workers)               [default: 24]
  --per-host <int>         Concurrent requests per host               [default: 8]
  --timeout <int>          Request timeout (seconds)                  [default: 20]
  --max-depth <int>        Crawl depth heuristic                      [default: 6]
  --max-urls <int>         Hard cap on visited URLs                   [default: none]
  --scheme <str>           Default scheme for targets w/o protocol    [default: https]
  --out <path>             Write machine‑readable JSON with artifacts
  --summary <path>         Optional human summary (markdown)
  --graph <path>           Write edge list CSV (source,target)
  --forms-csv <path>       Export forms CSV: page,method,action,inputs
  --wayback                Seed from Internet Archive CDX
  --include-css            Include .css fetching/parsing
  --include-ext <csv>      Extra extensions to include (e.g., js,css,json)
  --ignore-ext <csv>       Extensions to ignore (comma‑separated)
  --include-rx <regex>     Only enqueue URLs matching regex
  --exclude-rx <regex>     Exclude URLs matching regex
  --politeness-ms <int>    Extra per‑host delay (ms)                   [default: 0]
  --obey-crawl-delay       Respect Crawl‑delay from robots.txt         [default]
  --no-obey-crawl-delay    Ignore Crawl‑delay
  -v, --verbose            Verbose logging
  -h, --help               Show help
```

> Many binary/document types are ignored by default to stay fast; tune with `--include-ext` / `--ignore-ext`.

---

## Outputs

### JSON (`--out out.json`)

Schema may evolve; rely on top‑level keys shown below.

```json
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
```

### Forms CSV (`--forms-csv forms.csv`)

```
page,method,action,inputs
https://example.com/login,POST,https://example.com/login,"username,password,csrf"
```

### Graph (`--graph edges.csv`)

Edge list (source,target) for graph tools (Gephi/Graphistry/Graphviz):

```
https://example.com/,https://example.com/app.js
https://example.com/app.js,https://example.com/app.js.map
https://example.com/,https://example.com/api/v1/users
```

---

## Examples

Focus on API/GraphQL, ignore images & PDFs:

```bash
python3 reconmapper.py --target example.com \
  --include-rx '(api|graphql)' \
  --ignore-ext 'png,jpg,jpeg,gif,svg,webp,pdf' \
  --out api.json --graph api_edges.csv
```

Wayback seeding, polite rate, cap at 5k URLs:

```bash
python3 reconmapper.py --target example.com \
  --wayback --politeness-ms 200 --max-urls 5000
```

Include CSS to catch `@import`, font manifests and map hints:

```bash
python3 reconmapper.py --target example.com --include-css
```

Only crawl internal paths, skip crawl‑delay:

```bash
python3 reconmapper.py --target example.com \
  --include-rx '^https?://[^/]+/internal/' \
  --no-obey-crawl-delay
```

---

## How It Works

```
[Bootstrap]
  ├─ normalize target
  ├─ load robots.txt
  ├─ discover sitemaps
  └─ (opt) wayback seeds

[Queue]
  └─ asyncio.PriorityQueue (depth heuristic, per‑host politeness)

[Fetch]
  └─ aiohttp GET (redirects, content‑type sniff, size bounds)

[Parse]
  ├─ HTML (links, forms, meta refresh, canonical, srcset)
  ├─ JS   (fetch/axios/import, source maps → sources, GraphQL hints, WS/SSE, SW)
  ├─ XML  (sitemaps: urlset/sitemapindex)
  └─ Headers (Link relations)

[Classify & Canonicalize]
  └─ de‑dup buckets, strip trackers, collect parameters

[Output]
  └─ progress (console) + JSON/CSV/graph
```

---

## Tuning & Performance

* **Threads**: Increase `--threads` for multi‑host targets; keep `--per-host` modest on single hosts.
* **Focus**: Use `--include-rx` / `--exclude-rx` to restrict scope (e.g., only `/api/`).
* **History**: Combine `--wayback` to surface historical paths, let live crawl de‑dup.
* **Heavy JS**: Consider `--include-css` to catch imports and sourcemaps.
* **Timeouts**: Keep `--timeout` realistic (10–30s), use `--max-urls` for guardrails.

---

## Logging & Telemetry

* **Rich** progress bars and colored log levels when `--verbose` is enabled.
* Structured logs in JSON (optional) — *planned*.

---

## Ethics & Legality

Only crawl targets you’re **authorized** to test. `robots.txt` is respected by default; stay courteous with `--politeness-ms`. Tune limits to avoid harming third‑party infrastructure. Follow coordinated/ responsible disclosure.

---

## Roadmap

* Cookie/header auth support
* NDJSON / SQLite outputs
* Advanced robots/sitemap overrides
* HTTP method heuristics & wordlists derived from forms
* Structured JSON logs

> Have an idea? Open an issue with a minimal repro and a clear proposal.

---

## Contributing

PRs welcome! Please run `ruff`/`black` (if configured) and include:

* A focused change set (one concern per PR)
* Tests or a reproducible example
* Docs updates where applicable

---

## License

MIT — see [LICENSE](LICENSE).
