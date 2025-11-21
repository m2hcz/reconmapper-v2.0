<div align="center">

# ReconMapper Pro v2.1

[![python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#)
[![async](https://img.shields.io/badge/Async-aiohttp%20%7C%20asyncio-informational.svg)](#)
[![ui](https://img.shields.io/badge/UI-rich%20terminal-lightgrey.svg)](#)
[![status](https://img.shields.io/badge/Status-beta-success.svg)](#)

Async, single-domain **recon & asset mapper** with a Rich TUI and optional Wayback seeding.

</div>

> Crawls ➝ extracts ➝ classifies ➝ exports JSON (assets + summary).

---

## Table of Contents

- [Highlights](#highlights)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Usage](#cli-usage)
- [Outputs](#outputs)
- [TUI Overview](#tui-overview)
- [How It Works](#how-it-works)
- [Notes & Limitations](#notes--limitations)
- [Ethics & Legality](#ethics--legality)
- [License](#license)

---

## Highlights

- **Async crawler**
  - `aiohttp` + `asyncio` worker pool (`--threads`)
  - Central async queue with per-URL depth tracking
- **Scope locking**
  - Pre-flight GET follows redirects once
  - Locks scope to the effective root domain: `*.rootdomain`
  - External hosts containing the root domain are recorded as `subdomains`
- **HTML-aware extraction**
  - Parses `a`, `link`, `script`, `img`, `iframe`, `form`
  - Respects `<base href>` for correct URL resolution
  - Captures forms (`METHOD URL`) and script references
- **Next.js aware**
  - Parses `__NEXT_DATA__` JSON
  - Extracts `page`, `route`, `asPath` as `app_routes`
- **Regex-based discovery**
  - URL patterns inside HTML/JS blobs
  - `/api/` and `.json` → `api_endpoints`
  - Files (non-ignored extensions) → `files`
  - Emails → `emails`
- **Parameter discovery**
  - Query string keys from all visited URLs → `parameters`
- **Wayback Machine seeding (optional)**
  - CDX API for `*.rootdomain/*`
  - Enqueues a capped set of historical URLs
- **Rich TUI**
  - Live statistics (processed / failed / queue / current URL)
  - Per-category unique asset count
  - Rolling event log
- **JSON export**
  - Full asset list + per-category summary in a single JSON file

---

## Requirements

- **Python 3.10+**

Python packages:

- `aiohttp`
- `beautifulsoup4`
- `rich`

Minimal setup:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -U aiohttp beautifulsoup4 rich
