<div align="center">
  <p><sub>A.S.I.A SECURITY · OFFENSIVE SECURITY TOOLING</sub></p>
  <h1>ReconMapper Studio</h1>
  <p>
    <strong>Passive web surface mapping for authorized security assessments.</strong><br />
    Crawl, inspect, persist, and export application surfaces from a local operations console.
  </p>
  <p>
    <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-FFFFFF?style=flat-square&labelColor=050505&color=FFFFFF">
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.116.1-FFFFFF?style=flat-square&labelColor=050505&color=FFFFFF">
    <img alt="SQLite" src="https://img.shields.io/badge/Storage-SQLite-FFFFFF?style=flat-square&labelColor=050505&color=FFFFFF">
    <img alt="Version 2.1.1" src="https://img.shields.io/badge/Version-2.1.1-FFFFFF?style=flat-square&labelColor=050505&color=FFFFFF">
    <img alt="Authorized use only" src="https://img.shields.io/badge/Use-Authorized%20Targets%20Only-FFFFFF?style=flat-square&labelColor=050505&color=FFFFFF">
  </p>
</div>

> [!IMPORTANT]
> ReconMapper is designed exclusively for systems you own or are explicitly authorized to assess. It performs passive `GET`-based navigation and cataloguing. It does not submit forms, brute-force credentials, exploit findings, or execute destructive actions.

## What ReconMapper does

ReconMapper Studio maps the observable surface of a web application and presents the collected evidence in a local, Burp-inspired workspace. The crawler runs asynchronously, keeps the scan inside a defined scope, stores results in SQLite, and streams progress to the interface in real time.

The workspace is organized around four operational views:

- **Site Map** — hosts, directories, endpoints, files, and query-string structure.
- **HTTP History** — status, MIME type, response size, latency, and redirect information.
- **Message Inspector** — request headers, response headers, body preview, and metadata.
- **Findings** — passive observations such as missing security headers, cookie issues, exposed metadata, technology fingerprints, and redacted secret candidates.

## Why it is different

ReconMapper is not a wrapper around a single scanner. It combines crawling, passive analysis, persistence, and inspection into one local application.

- **Application-aware discovery:** HTML, forms, JavaScript routes, JSON/XML references, WebSockets, OpenAPI documents, `robots.txt`, and sitemap XML.
- **Evidence-first history:** every fetched resource can be inspected after the scan, including previous sessions.
- **Strict scope enforcement:** internal redirects are followed; out-of-scope redirects are recorded but not requested.
- **Safe authenticated mapping:** authorized session headers can be supplied, while sensitive values are redacted before persistence.
- **Operational interface:** resizable panels, keyboard navigation, live counters, WebSocket updates, and polling fallback.
- **Portable output:** full per-scan JSON export for triage, reporting, or downstream processing.

## Quick start

### Windows

```powershell
git clone https://github.com/m2hcz/reconmapper-v2.0.git
cd reconmapper-v2.0
start_windows.bat
```

Manual installation:

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

Manual installation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py
```

Open the local console:

```text
http://127.0.0.1:8080
```

## Mapping capabilities

### Surface discovery

- Links, scripts, stylesheets, images, iframes, and other referenced assets.
- Form actions, methods, field names, input types, and parameters.
- Query-string keys and hierarchical directory paths.
- JavaScript routes, API paths, WebSocket URLs, and inline references.
- Subdomains and external resources observed during the crawl.
- `robots.txt`, sitemap XML, OpenAPI/Swagger documents, metadata, and comments.

### Passive analysis

- Missing or permissive security headers.
- Cookie attributes such as `Secure`, `HttpOnly`, and `SameSite`.
- Technology and framework fingerprints.
- Cloud storage references and exposed email addresses.
- Potential credentials or tokens, redacted and fingerprinted before storage.
- Error responses and crawl failures with their source URLs.

### Scan controls

- Maximum crawl depth.
- Concurrent request limit.
- Per-request timeout and optional delay.
- Maximum URL count and response-body size.
- Same-host or root-domain/subdomain scope policy.
- TLS certificate verification.
- Optional custom headers for authorized sessions.

## Safety boundaries

ReconMapper intentionally does not:

- submit HTML forms;
- send `POST`, `PUT`, `PATCH`, or `DELETE` requests;
- perform credential attacks or directory brute force;
- bypass authentication or authorization controls;
- execute discovered JavaScript in a browser engine;
- exploit suspected vulnerabilities;
- follow redirects outside the configured scope;
- store raw authorization tokens or cookie values in request history.

The SQLite database can still contain sensitive paths, parameters, metadata, and response previews. Treat it as assessment evidence and protect it accordingly.

## Running the service

The default host and port are `127.0.0.1:8080`.

```bash
python run.py --host 127.0.0.1 --port 8080
```

Environment variables:

```env
RECONMAPPER_HOST=127.0.0.1
RECONMAPPER_PORT=8080
RECONMAPPER_DB=./reconmapper.db
```

Legacy `MAPCRAWLER_*` variables remain supported as migration fallbacks from version 2.1.0.

<details>
<summary><strong>Authorized session headers</strong></summary>

The settings panel accepts a JSON object containing headers for a session that you are authorized to use:

```json
{
  "Cookie": "session=AUTHORIZED_TEST_SESSION",
  "Authorization": "Bearer AUTHORIZED_TEST_TOKEN"
}
```

Hop-by-hop headers are discarded, CR/LF injection is rejected, and sensitive values are redacted before they are written to the database.

</details>

## Docker

```bash
docker build -t asia-reconmapper .

docker run --rm \
  -p 127.0.0.1:8080:8080 \
  -v "$PWD/data:/app/data" \
  -e RECONMAPPER_DB=/app/data/reconmapper.db \
  asia-reconmapper
```

## Keyboard shortcuts

- <kbd>Ctrl</kbd> + <kbd>K</kbd> — focus the target field.
- <kbd>Ctrl</kbd> + <kbd>,</kbd> — open scan settings.
- <kbd>/</kbd> — focus HTTP History search.
- <kbd>↑</kbd> / <kbd>↓</kbd> — move through request history.
- <kbd>Alt</kbd> + <kbd>[</kbd> — collapse or expand Site Map.
- <kbd>Alt</kbd> + <kbd>]</kbd> — collapse or expand Message Inspector.

Panel widths and collapsed states are retained in browser storage.

## Local API

Interactive OpenAPI documentation is available at:

```text
http://127.0.0.1:8080/api/docs
```

<details>
<summary><strong>Main endpoints</strong></summary>

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

</details>

## Architecture

```text
reconmapper-v2.0/
├── reconmapper/
│   ├── app.py                 # FastAPI application and service entry point
│   ├── core/
│   │   ├── analyzer.py        # Passive extraction and finding generation
│   │   ├── engine.py          # Async crawl orchestration
│   │   ├── models.py          # Request and response schemas
│   │   ├── scope.py           # URL normalization and scope enforcement
│   │   └── storage.py         # SQLite persistence
│   └── web/
│       ├── static/            # Interface JavaScript and CSS
│       └── templates/         # A.S.I.A operations console
├── tests/
├── docs/
├── run.py
├── pyproject.toml
└── requirements.txt
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the execution flow, storage model, and service boundaries.

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The test suite covers URL normalization, host and port scoping, redirect handling, form non-submission, parameterized-route cataloguing, secret redaction, and finding deduplication.

## Validation feedback

Version 2.1.1 replaces the previous `[object Object]` notification with readable FastAPI validation feedback. Invalid fields are now identified directly in the interface, and numeric settings are validated before scan creation.

Example:

```text
max_urls: Input should be greater than or equal to 1
max_body_bytes: Input should be greater than or equal to 16384
```

## Limitations

ReconMapper is a crawler and passive application mapper. It is not an intercepting proxy, vulnerability exploitation framework, or full browser automation engine.

Coverage can be reduced when routes depend on complex frontend state, service workers, client-side rendering, authenticated WebSocket flows, CAPTCHA challenges, or human interaction. Browser-assisted discovery may be added later without changing the existing persistence and inspection model.

## Documentation and contribution

- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Contribution guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Security policy: [`SECURITY.md`](SECURITY.md)

## Responsible use

Use ReconMapper only with explicit authorization and within the applicable rules of engagement. The operator is responsible for target ownership, scope validation, request rate, evidence handling, and compliance with applicable law.

## Author

Developed by [m2hcz](https://github.com/m2hcz) under the **A.S.I.A Security** identity.
