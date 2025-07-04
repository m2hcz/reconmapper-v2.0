# ReconMapper

<div align="center">

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-active-brightgreen.svg)]()
[![AsyncIO](https://img.shields.io/badge/powered%20by-AsyncIO-orange.svg)](https://docs.python.org/3/library/asyncio.html)
[![aiohttp](https://img.shields.io/badge/HTTP-aiohttp-blue.svg)](https://aiohttp.readthedocs.io/)

**Advanced Asynchronous Web Reconnaissance & Attack Surface Discovery**

*Lightning-fast async web crawler that discovers directories, files, form inputs, API endpoints, and more with intelligent content analysis.*

</div>

---

## 🎯 Overview

ReconMapper is a **high-performance asynchronous web reconnaissance crawler** built with Python's asyncio and aiohttp that provides comprehensive attack surface discovery for security professionals, penetration testers, and bug bounty hunters.

### Why ReconMapper?

- 🚀 **Lightning Fast**: Pure asyncio/aiohttp architecture with concurrent workers (up to 100 threads)
- 🔍 **Deep Discovery**: Intelligent HTML parsing and JavaScript URL extraction
- 🤖 **Respectful Crawling**: Built-in robots.txt compliance and rate limiting
- � **Rich Terminal UI**: Beautiful progress bars and colored output via Rich library
- 🌐 **Historical Data**: Wayback Machine integration for discovering legacy endpoints
- 🗺️ **Sitemap Integration**: Automatic XML sitemap parsing and URL discovery

---

## 🚀 Key Features

<table>
<tr>
<td width="50%">

### 🔍 **Discovery Capabilities**
- **Directories** - Complete path hierarchy enumeration
- **Files** - Static assets and document discovery
- **Form Inputs** - HTML forms (`<input>`, `<textarea>`, `<select>`)
- **URL Parameters** - Query string parameter extraction
- **API Endpoints** - JSON response detection
- **Source Files** - JavaScript sourcemap analysis
- **Subdomains** - Automatic subdomain discovery
- **Sitemaps** - XML sitemap parsing and URL extraction

</td>
<td width="50%">

### ⚡ **Technical Features**
- **Pure AsyncIO** - High-performance concurrent crawling
- **Smart Content Detection** - HTML vs JSON vs JavaScript analysis
- **Robots.txt Compliance** - Respects crawling guidelines
- **Sourcemap Analysis** - Extracts original source files from `.js.map`
- **Rich Terminal UI** - Live progress tracking with spinners and bars
- **Memory Efficient** - Set-based deduplication and visited URL tracking
- **Depth Control** - Configurable crawl depth limiting
- **Regex URL Extraction** - Advanced pattern matching for hidden URLs

</td>
</tr>
</table>

---

## 📋 Requirements

| Component | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.9+ | Core runtime with asyncio support |
| **aiohttp** | Latest | Async HTTP client library |
| **BeautifulSoup4** | Latest | HTML parsing and link extraction |
| **Rich** | Latest | Terminal UI and progress visualization |
| **asyncio** | Built-in | Asynchronous framework |

---

## ⚡ Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/m2hcz/reconmapper-v2.0
cd reconmapper-v2.0

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install aiohttp beautifulsoup4 rich

### 2. Basic Usage

```bash
# Simple scan
python mapcrawller.py -t example.com

# Advanced scan with all features
python mapcrawller.py \
  --target example.com \
  --threads 25 \
  --timeout 30 \
  --max-depth 10 \
  --wayback \
  --summary report.json \
  --out events.jsonl \
  --verbose
```

### 3. Real-world Usage

```bash
# Large scale reconnaissance
python mapcrawller.py \
  -t target.com \
  -T 50 \
  --timeout 45 \
  --max-depth 15 \
  --wayback \
  --summary enterprise_report.json \
  -v
```

---

## 🛠️ Configuration

### Command Line Options

| Flag | Long Form | Description | Default | Example |
|------|-----------|-------------|---------|---------|
| `-t` | `--target` | Target domain | *Required* | `example.com` |
| `-T` | `--threads` | Concurrent workers (1-100) | `10` | `25` |
| ` ` | `--timeout` | Request timeout (seconds) | `15` | `30` |
| ` ` | `--max-depth` | Maximum crawl depth | `5` | `10` |
| `-o` | `--out` | JSONL output file | `None` | `events.jsonl` |
| ` ` | `--summary` | JSON summary file | `None` | `report.json` |
| ` ` | `--wayback` | Enable Wayback Machine | `False` | `--wayback` |
| `-v` | `--verbose` | Enable debug logging | `False` | `-v` |

### Configuration File

Create `config.py` or pass arguments directly via command line:

```python
# Example configuration values
TARGET = "example.com"
THREADS = 20  # Max 100
TIMEOUT = 30  # seconds
MAX_DEPTH = 8
WAYBACK = True
VERBOSE = True
```

### Built-in Constants

```python
# User Agent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Ignored Extensions
IGN_EXT = {".css"}  # CSS files are skipped

# URL Extraction Pattern
URL_RX = r'[\"\'()](?P<u>/(?!/)[\w./\-]*\??[\w=&\-]*|https?://[\w./\-]+\??[\w=&\-]*)[\"\'()]'

# Discovery Categories
CAT_ORDER = ("api_endpoints", "directories", "files", "parameters", "inputs", "source_files", "subdomains")
```

---

## 📊 Output Formats

### 1. Real-time JSONL Stream (`--out events.jsonl`)

*Currently not implemented in the shown code, but framework is ready for streaming output.*

### 2. Comprehensive Summary (`--summary report.json`)

```json
{
  "api_endpoints": [
    "https://api.example.com/v1/users",
    "https://example.com/api/data"
  ],
  "directories": [
    "/",
    "/admin",
    "/api",
    "/assets",
    "/uploads"
  ],
  "files": [
    "/robots.txt",
    "/sitemap.xml",
    "/assets/js/app.min.js",
    "/assets/css/style.css"
  ],
  "parameters": [
    "page",
    "sort",
    "filter",
    "q",
    "id"
  ],
  "inputs": [
    "input:username:text",
    "input:password:password",
    "textarea:message:textarea",
    "select:category:select"
  ],
  "source_files": [
    "src/components/Header.js",
    "src/utils/api.js",
    "src/pages/Dashboard.js"
  ],
  "subdomains": [
    "example.com",
    "api.example.com",
    "cdn.example.com"
  ],
  "generated_at": "2025-07-04T10:45:33Z"
}
```

### 3. Terminal Output

The tool displays a beautiful Rich table showing discovery counts:

```
                    ReconMapper Summary                     
┏━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Asset         ┃ Count ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━┩
│ api_endpoints │    12 │
│ directories   │    34 │
│ files         │   156 │
│ parameters    │     8 │
│ inputs        │    15 │
│ source_files  │    23 │
│ subdomains    │     4 │
└───────────────┴───────┘
```

---

## 🎭 Use Cases

### 🔐 **Penetration Testing**
- **Attack Surface Discovery**: Map all entry points and endpoints
- **Input Validation Testing**: Discover all form inputs for injection testing
- **Directory Bruteforcing**: Generate comprehensive wordlists
- **API Testing**: Identify REST/GraphQL endpoints for security testing

### 🐛 **Bug Bounty Hunting**
- **Subdomain Discovery**: Find hidden subdomains and services
- **Historical Analysis**: Discover forgotten/legacy endpoints via Wayback
- **Parameter Discovery**: Find hidden parameters for testing
- **Source Code Analysis**: Extract sensitive information from JS files

### 🛡️ **Security Assessment**
- **Asset Inventory**: Complete web application mapping
- **Compliance Checking**: Verify robots.txt and security headers
- **Change Detection**: Monitor for new endpoints and changes
- **Risk Assessment**: Identify potential security exposure points

### 📊 **OSINT & Reconnaissance**
- **Intelligence Gathering**: Comprehensive target profiling
- **Technology Stack Discovery**: Identify frameworks and technologies
- **Contact Information**: Extract emails, phones, addresses
- **Social Media Links**: Discover associated social profiles

---

## 🔧 Technical Implementation

### Core Architecture

ReconMapper uses a **pure asyncio/aiohttp architecture** for maximum performance:

```python
# Async worker pattern
async def _worker(self):
    async with aiohttp.ClientSession() as session:
        while True:
            url, depth = await self.queue.get()
            await self._process_url(session, url, depth)
```

### Discovery Methods

#### 1. **HTML Link Extraction**
```python
# BeautifulSoup parsing for forms and links
for tag in soup.find_all(["input", "textarea", "select", "form"]):
    name = tag.get("name") or tag.get("id")
    if name:
        self._found("inputs", f"{tag.name}:{name}:{tag.get('type')}")
```

#### 2. **JavaScript URL Pattern Matching**
```python
# Regex pattern for URL extraction from JS
URL_RX = re.compile(r'[\"\'()](?P<u>/(?!/)[\w./\-]*\??[\w=&\-]*|https?://[\w./\-]+\??[\w=&\-]*)[\"\'()]')
```

#### 3. **Sourcemap Analysis**
```python
# Automatic .js.map discovery and source file extraction
async def _sourcemap(self, session: aiohttp.ClientSession, js_url: str):
    async with session.get(f"{js_url}.map") as response:
        if response.status == 200:
            for src in (await response.json()).get("sources", []):
                self._found("source_files", src)
```

#### 4. **Content-Type Detection**
```python
# Smart content analysis
content_type = response.headers.get("content-type", "").lower()
if "application/json" in content_type:
    self._found("api_endpoints", str(response.url))
elif "javascript" in content_type:
    await self._parse_javascript(session, url)
```

---

## 🚀 Performance & Features

### High-Performance Async Architecture

```python
# Concurrent worker management
workers = [asyncio.create_task(self._worker()) for _ in range(self.cfg.threads)]

# Semaphore-based rate limiting
async with self.semaphore:
    await self._process_request(session, url)
```

### Intelligent Deduplication

```python
# Memory-efficient visited URL tracking
self.visit: Set[str] = set()

# Normalized URL storage to prevent duplicates
normalized = urlunparse((scheme, netloc.lower(), re.sub(r"/+", "/", path), "", "", ""))
if normalized not in self.visit:
    self.visit.add(normalized)
```

## 📈 Roadmap

### Version 2.1 (Current Implementation)
- [x] Pure asyncio/aiohttp architecture
- [x] HTML parsing with BeautifulSoup4
- [x] Rich terminal UI with progress bars
- [x] Robots.txt compliance
- [x] XML sitemap discovery
- [x] Wayback Machine integration
- [x] JavaScript URL extraction
- [x] Sourcemap analysis
- [x] Form input discovery
- [x] API endpoint detection

### Version 2.2 (Planned)
- [ ] **JSONL streaming output implementation**
- [ ] **CSV and Burp Suite export formats**
- [ ] **Custom User-Agent support**
- [ ] **Proxy support (HTTP/SOCKS)**
- [ ] **Request delay configuration**
- [ ] **Custom headers and cookies**
- [ ] **File extension filtering**
- [ ] **Exclude/include pattern matching**

### Version 2.3 (Future)
- [ ] **GraphQL endpoint discovery**
- [ ] **WebSocket detection**
- [ ] **Certificate transparency logs**
- [ ] **subdomain enumeration via DNS**
- [ ] **Technology stack fingerprinting**

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/m2hcz/reconmapper-v2.0
cd reconmapper-v2.0

# Setup development environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install aiohttp beautifulsoup4 rich

# Run the tool
python mapcrawller.py -t example.com -v

# Run tests (when available)
python -m pytest tests/ -v

# Code formatting
black mapcrawller.py
isort mapcrawller.py
flake8 mapcrawller.py
```

### Areas for Contribution

- 🐛 **Bug fixes and improvements**
- ✨ **New discovery modules**
- 📚 **Documentation enhancements**
- 🧪 **Test coverage expansion**
- 🔌 **Integration plugins**
- 🌐 **Internationalization**

---

## 🛡️ Legal Disclaimer

ReconMapper is designed for **authorized security testing and research purposes only**. Users are responsible for complying with all applicable laws and regulations. The authors and contributors are not responsible for any misuse or damage caused by this tool.

**Always obtain proper authorization before testing systems you do not own.**

---

## 📞 Support & Contact

- 📧 **Email**: [m2hczs@proton.me](m2hczs@proton.me)
- 💬 **Discord**: [My discord](s0yvenn)
- 🐛 **Issues**: [GitHub Issues](https://github.com/m2hcz/reconmapper-v2.0/issues)
---

## 🎖️ Acknowledgments

- **Python asyncio Team** - For the excellent asynchronous framework
- **aiohttp Contributors** - For the high-performance HTTP client library  
- **BeautifulSoup4 Team** - For the powerful HTML parsing capabilities
- **Rich Library** - For the beautiful terminal UI and progress visualization
- **Security Community** - For feedback and feature requests
- **Contributors** - For making this project better every day

---

<div align="center">

**⭐ Star this repository if ReconMapper helps you in your security research! ⭐**

[![GitHub stars](https://img.shields.io/github/stars/m2hcz/reconmapper-v2.0.svg?style=social&label=Star)](https://github.com/m2hcz/reconmapper-v2.0)
[![Twitter Follow](https://img.shields.io/twitter/follow/inf0secc.svg?style=social)](https://x.com/inf0secc)

</div>
