# ReconMapper

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-active-brightgreen.svg)]()

ReconMapper is an **asynchronous**, **Playwright-powered** web reconnaissance crawler that discovers:

* **Directories & files** (including static assets)
* **Form inputs** (`<input>`, `<textarea>`, `<select>`, `<form>`)
* **URL parameters** (query-string keys)
* **JSON API endpoints**
* **JavaScript source files** via sourcemaps
* **Historic URLs** (via Wayback Machine)
* And more, all while respecting `robots.txt` and ingesting sitemaps.

---

## 🚀 Features

| Category          | Collected Items                                 |
| ----------------- | ----------------------------------------------- |
| **Directories**   | All unique path hierarchies                     |
| **Files**         | Static assets: CSS, JS, images, documents, etc. |
| **Form Inputs**   | Names & types for HTML forms                    |
| **URL Params**    | Query parameters                                |
| **API Endpoints** | URLs returning JSON                             |
| **Source Files**  | Original JS sources from `.js.map`              |
| **Wayback**       | Historic URLs seeded from the Web Archive       |
| **Sitemap**       | URLs discovered via `<sitemap>` entries         |
| **Robots.txt**    | Honor Disallow/Allow rules                      |
| **Rich UI**       | Live progress bar, colored logs (enable `-v`)   |

---

## ⚡ Installation

```bash
# Clone the repository
git clone https://github.com/your-org/reconmapper.git
cd reconmapper

# Create a virtual environment
env=".venv"
python3 -m venv "$env" && source "$env/bin/activate"

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install
```

> **Requires Python 3.9+**

---

## 🎯 Usage

```bash
python recon_mapper.py \
  -t example.com \
  -T 20 \
  --timeout 20 \
  --max-depth 5 \
  --wayback \
  --summary report.json \
  --out events.jsonl \
  -v
```

| Flag              | Description                                         |
| ----------------- | --------------------------------------------------- |
| `-t`, `--target`  | Target domain (e.g. `example.com`)                  |
| `-T`, `--threads` | Number of concurrent workers (max 100)              |
| `--timeout`       | Request timeout (seconds)                           |
| `--max-depth`     | Crawl depth                                         |
| `--headless`      | Run Chromium headless (toggle with `--no-headless`) |
| `-o`, `--out`     | Streaming JSONL log file                            |
| `--summary`       | Final JSON summary file                             |
| `--wayback`       | Enable Wayback Machine enrichment                   |
| `-v`, `--verbose` | Enable debug (per-item) logging                     |

---

## 📦 Output

### Live log (`events.jsonl`)

```json
{ "ts": "2025-06-29T21:00:00Z", "type": "input", "name": "search", "url": "https://example.com" }
{ "ts": "2025-06-29T21:00:01Z", "type": "file", "path": "/static/js/app.js" }
```

### Summary (`report.json`)

```json
{
  "directories": ["/","/api","/admin"],
  "files": ["/robots.txt","/static/js/app.js"],
  "inputs": ["input:username:text"],
  "parameters": ["q","page"],
  "api_endpoints": ["https://api.example.com/v1/users"],
  "source_files": ["src/index.js"],
  "subdomains": ["example.com","api.example.com"],
  "generated_at": "2025-06-29T21:05:00Z"
}
```

---
## 🧭 Roadmap

* [ ] CSV/HTML export
* [ ] Burp intruder list output
* [ ] Interactive GUI
* [ ] `.reconignore` support
