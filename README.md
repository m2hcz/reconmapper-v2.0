Abaixo está uma versão mais consistente, objetiva e “GitHub-ready” do seu README, com linguagem mais precisa, seções bem separadas e já refletindo o **`-f/--filter`** e o conceito de **mapear tudo (por categoria)**. Mantive o seu estilo (badges + TUI + JSON export) e removi claims que podem soar específicos demais (ex.: “Next.js aware”) a menos que você realmente tenha esse parsing no código atual.

Você pode copiar e colar como está.

---

````md
<div align="center">

# ReconMapper Pro v2.1

[![python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#)
[![async](https://img.shields.io/badge/Async-aiohttp%20%7C%20asyncio-informational.svg)](#)
[![ui](https://img.shields.io/badge/TUI-rich%20terminal-lightgrey.svg)](#)
[![status](https://img.shields.io/badge/Status-beta-success.svg)](#)

**Async, single-scope recon & asset mapper** with a Rich TUI, sitemap/robots discovery and optional Wayback seeding.

</div>

> Crawl → extract → classify → export (JSON)

---

## Table of Contents

- [Overview](#overview)
- [Highlights](#highlights)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Usage](#cli-usage)
- [Filters](#filters)
- [Output](#output)
- [TUI Overview](#tui-overview)
- [How It Works](#how-it-works)
- [Notes & Limitations](#notes--limitations)
- [Ethics & Legality](#ethics--legality)
- [License](#license)

---

## Overview

ReconMapper Pro is an asynchronous crawler designed to map a target’s application surface within a single scope.  
It discovers endpoints and assets, extracts useful recon artifacts, and exports everything to JSON for analysis and triage.

Typical use-cases:
- Attack surface mapping (paths, endpoints, parameters, forms)
- Asset discovery (scripts, files, directories)
- Low-noise recon with scope locking and configurable depth

---

## Highlights

- **Async crawler**
  - `aiohttp` + `asyncio` worker pool
  - Central queue with depth tracking (`--depth`)
- **Scope locking**
  - Pre-flight request follows redirects and locks on the effective root domain
  - Records subdomains discovered during crawl
- **HTML-aware extraction**
  - Parses `a[href]`, `link[href]`, `script[src]`, `img[src]`, `iframe[src]`, `form`
  - Respects `<base href>` for correct URL resolution
- **Discovery beyond DOM**
  - Regex discovery of URLs/paths inside HTML/JS/JSON blobs
  - Extracts querystring keys and form field names
- **Special endpoints**
  - Optional `/robots.txt` and `/sitemap.xml` discovery (toggleable)
  - Optional Wayback Machine seeding for historical URLs
- **Rich TUI**
  - Live stats: processed / failed / queue / current URL
  - Per-category counters
  - Rolling log output
- **JSON export**
  - Full findings with sources and timestamps
  - Single output file with summary and categorized artifacts

---

## Requirements

- **Python 3.10+**

Dependencies:
- `aiohttp`
- `beautifulsoup4`
- `rich`

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -U aiohttp beautifulsoup4 rich
````

---

## Quick Start

Scan a domain with default settings:

```bash
python3 reconmapper.py example.com
```

Deeper scan, more concurrency, export JSON:

```bash
python3 reconmapper.py example.com -d 4 -t 30 -o out.json
```

---

## CLI Usage

```bash
python3 reconmapper.py <target> [options]
```

Common options:

* `-t, --threads <int>`: concurrency (default: 15)
* `-d, --depth <int>`: max crawl depth (default: 3)
* `-o, --output <path>`: export findings as JSON
* `--proxy <url>`: upstream proxy (e.g., `http://127.0.0.1:8080`)
* `--wayback`: enable Wayback seeding
* `--jitter <float>`: random delay between requests
* `--no-sitemap`: disable robots/sitemap discovery
* `-v, --verbose`: more logging
* `-f, --filter <list>`: restrict output to specific categories (see below)

---

## Filters

Use `-f` / `--filter` to focus your mapping and reduce noise.
You can pass a comma-separated list and/or repeat the flag.

Examples:

Map only files:

```bash
python3 reconmapper.py example.com -f files -o out.json
```

Map endpoints + API endpoints + params:

```bash
python3 reconmapper.py example.com -f endpoint,params -o out.json
```

Map directories and inputs:

```bash
python3 reconmapper.py example.com -f directories -f inputs -o out.json
```

Supported categories (may vary by version):

* `endpoints` (in-scope URLs)
* `api_endpoints` (e.g., `/api/...` patterns)
* `external_endpoints` (out-of-scope URLs observed)
* `directories`
* `files`
* `inputs`
* `params`
* `forms`
* `emails`
* `cloud_buckets`
* `secrets`
* `subdomains`
* `comments`
* `tech`

Alias shortcuts:

* `endpoint` → includes `endpoints` + `api_endpoints`
* `dirs` / `dir` → `directories`
* `files` / `file` → `files`
* `params` / `param` → `params`

Tip: use `-f all` (or omit `-f`) to map everything.

---

## Output

When `-o/--output` is provided, ReconMapper writes a single JSON file containing:

* `target`, `scan_time`, `duration`
* `stats` (processed / failed)
* `technologies` (best-effort detection)
* `findings` per category:

  * `value`: the discovered artifact
  * `source`: where it was found
  * `timestamp`: discovery time

---

## TUI Overview

The Rich interface displays:

* Current status and runtime
* Crawl counters (processed/failed/queue)
* Current URL being processed
* Tech stack (best-effort)
* Findings summary by category
* Rolling log feed (important events + debug in verbose)

---

## How It Works

1. Resolves the target and locks the scope to the effective domain
2. Seeds the queue with the initial URL (+ optional sitemap/robots and Wayback)
3. Crawls asynchronously using a worker pool
4. Extracts:

   * DOM links/assets/forms
   * URLs and paths from inlined content via regex
   * parameters from querystrings and form field names
5. Deduplicates findings and exports results (optional)

---

## Notes & Limitations

* Intended for **single-scope** mapping (root domain + subdomains)
* JS-heavy apps may require deeper crawling and script fetching to maximize coverage
* Some assets are ignored by extension (images, fonts, archives, media) to reduce noise
* This tool does not attempt browser automation; it is a crawler, not a headless browser

---

## Ethics & Legality

Use only on targets you own or have explicit authorization to test.
You are responsible for compliance with applicable laws, rules of engagement, and program scope.

---

```
