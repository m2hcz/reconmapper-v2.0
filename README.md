<div align="center">

# A.S.I.A ReconMapper Studio

### Authorized web surface mapping with a Burp-inspired local operations console

[![Python](https://img.shields.io/badge/Python-3.11%2B-ffffff?style=flat-square&labelColor=050505&color=ffffff)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-ffffff?style=flat-square&labelColor=050505&color=ffffff)](https://fastapi.tiangolo.com/)
[![Tests](https://github.com/m2hcz/reconmapper-v2.0/actions/workflows/tests.yml/badge.svg)](https://github.com/m2hcz/reconmapper-v2.0/actions/workflows/tests.yml)
[![Version](https://img.shields.io/badge/version-2.1.1-ffffff?style=flat-square&labelColor=050505&color=ffffff)](#changelog)

ReconMapper is a passive, asynchronous web application mapper built for authorized security assessments. It crawls a defined scope, persists the observed surface in SQLite, and exposes the result through a local interface at `http://127.0.0.1:8080`.

</div>

<p align="center">
  <img src="docs/preview.png" alt="A.S.I.A ReconMapper Studio interface" width="100%">
</p>

> [!IMPORTANT]
> ReconMapper is intended only for systems you own or are explicitly authorized to assess. It performs passive `GET` navigation and cataloguing; it does not submit forms, brute-force credentials, exploit findings, or execute destructive actions.

## Overview

A.S.I.A ReconMapper Studio replaces the original terminal-only crawler with a modular local application composed of:

- an asynchronous crawl engine using `aiohttp`;
- a FastAPI service and WebSocket event stream;
- SQLite persistence with WAL mode;
- an A.S.I.A operations console inspired by Burp Suite workflows;
- a passive analysis pipeline for routes, forms, parameters, APIs, metadata, cookies, headers, technologies, and possible exposed secrets.

The interface is organized into Site Map, Request History, Inspector, and Findings views. Previous scans remain available after the service restarts.

## Core capabilities

| Area | Capabilities |
| --- | --- |
| Mapping | HTML links, assets, forms, query parameters, JavaScript routes, JSON/XML references, WebSockets, subdomains, and external resources |
| Discovery | `robots.txt`, sitemap XML, OpenAPI documents, inline scripts, comments, metadata, and common API paths |
| HTTP history | Status, MIME type, body size, latency, redirect chain, request headers, response headers, and response preview |
| Site Map | Hierarchical host, directory, endpoint, and query-string representation |
| Passive findings | Security headers, cookie flags, exposed metadata, technology fingerprints, and redacted secret candidates |
| Persistence | SQLite database with scan, request, artifact, and finding records |
| Live telemetry | WebSocket updates with polling fallback, counters, duration, queue state, and connection status |
| Export | Complete per-scan JSON export |
| Scope controls | Host/subdomain policy, depth, concurrency, delay, URL cap, TLS verification, and body-size cap |

## Safety model

ReconMapper intentionally does not:

- submit HTML forms;
- issue `POST`, `PUT`, `PATCH`, or `DELETE` requests;
- brute-force credentials or directories;
- bypass authentication;
- exploit vulnerabilities;
- follow redirects outside the configured scope;
- persist raw authorization tokens or cookie values in the request history.

Potential secrets are redacted and fingerprinted before persistence. Use test accounts and protect the SQLite database because it can still contain sensitive URLs, metadata, and response previews.

## Requirements

- Python 3.11 or newer
- Windows, Linux, or macOS
- Network access to the authorized target

## Quick start

### Windows

```powershell
git clone https://github.com/m2hcz/reconmapper-v2.0.git
cd reconmapper-v2.0
start_windows.bat
```

Or manually:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py
```

### Linux or macOS

```bash
git clone https://github.com/m2hcz/reconmapper-v2.0.git
cd reconmapper-v2.0
chmod +x start_linux.sh
./start_linux.sh
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py
```

Open:

```text
http://127.0.0.1:8080
```

## Configuration

The service accepts command-line arguments:

```bash
python run.py --host 127.0.0.1 --port 8080
```

Environment variables:

```env
RECONMAPPER_HOST=127.0.0.1
RECONMAPPER_PORT=8080
RECONMAPPER_DB=./reconmapper.db
```

Legacy `MAPCRAWLER_*` environment variables remain supported as fallbacks for migration from version 2.1.0.

### Authorized session headers

The settings panel accepts a JSON object containing headers for an authorized test session:

```json
{
  "Cookie": "session=AUTHORIZED_TEST_SESSION",
  "Authorization": "Bearer AUTHORIZED_TEST_TOKEN"
}
```

Blocked hop-by-hop headers are discarded, CR/LF injection is rejected, and sensitive values are redacted before persistence.

## Docker

```bash
docker build -t asia-reconmapper .
docker run --rm \
  -p 127.0.0.1:8080:8080 \
  -v "$PWD/data:/app/data" \
  -e RECONMAPPER_DB=/app/data/reconmapper.db \
  asia-reconmapper
```

## Interface shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl + K` | Focus target input |
| `Ctrl + ,` | Open settings |
| `/` | Focus HTTP History search |
| `↑` / `↓` | Navigate request history |
| `Alt + [` | Collapse or expand Site Map |
| `Alt + ]` | Collapse or expand Inspector |

Panel widths and collapsed states are stored locally in the browser.

## Local API

Interactive OpenAPI documentation:

```text
http://127.0.0.1:8080/api/docs
```

Main routes:

```text
POST /api/scans
POST /api/scans/{scan_id}/stop
GET  /api/scans
GET  /api/scans/{scan_id}
GET  /api/scans/{scan_id}/requests
GET  /api/scans/{scan_id}/requests/{request_id}
GET  /api/scans/{scan_id}/artifacts
GET  /api/scans/{scan_id}/findings
GET  /api/scans/{scan_id}/sitemap
GET  /api/scans/{scan_id}/export.json
WS   /ws/scans/{scan_id}
```

## Project structure

```text
reconmapper-v2.0/
├── reconmapper/
│   ├── app.py
│   ├── core/
│   │   ├── analyzer.py
│   │   ├── engine.py
│   │   ├── models.py
│   │   ├── scope.py
│   │   └── storage.py
│   └── web/
│       ├── static/
│       └── templates/
├── tests/
├── docs/
├── run.py
├── pyproject.toml
└── requirements.txt
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the execution and persistence model.

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The suite covers URL normalization, scope enforcement, host/port handling, non-submission of forms, parameterized-route cataloguing, secret redaction, and finding deduplication.

## Validation errors

Version 2.1.1 fixes the previous `[object Object]` notification. FastAPI validation errors are now rendered with the affected field and its actual message. Numeric settings are also validated client-side before a scan is created.

Example:

```text
max_urls: Input should be greater than or equal to 1
max_body_bytes: Input should be greater than or equal to 16384
```

## Limitations

ReconMapper is a crawler, not an intercepting proxy or a browser automation framework. Routes that require complex frontend state, human interaction, authenticated WebSocket flows, service workers, or browser-only execution may not be discovered.

Potential future integrations include HAR import and optional Playwright-assisted discovery while preserving the same storage and UI model.

## Responsible use

Use the project only under explicit authorization and within the agreed rules of engagement. The operator is responsible for target ownership, scope validation, rate limits, data handling, and compliance with applicable law.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening an issue or pull request. Security-sensitive reports should follow [`SECURITY.md`](SECURITY.md).

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md).

## Author

Developed by [m2hcz](https://github.com/m2hcz) under the A.S.I.A Security identity.
