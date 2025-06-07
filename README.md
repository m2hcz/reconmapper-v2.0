# ReconMapper v2.0

An intelligent, asynchronous web crawler for offensive security reconnaissance, built with Python, Playwright, and asyncio.

---

## About The Project

ReconMapper is a reconnaissance (recon) tool designed to automate the initial phase of a pentest or an offensive security assessment. Instead of relying on simple HTTP requests, it leverages a headless browser controlled by Playwright to render dynamic web pages, including Single Page Applications (SPAs) built with frameworks like React, Angular, or Vue.js.

This allows for a much deeper and more realistic discovery of endpoints, subdomains, and files, simulating real user interaction and extracting links that traditional crawlers would miss. The use of `asyncio` and multiple workers ensures exceptional performance, even when dealing with large and complex targets.

---

## Key Features

* **Full JavaScript Rendering:** Uses a real Chromium browser (via Playwright) to ensure all dynamic content is processed.
* **Asynchronous & Parallel Crawling:** Leverages `asyncio` and multiple workers to scan dozens of pages simultaneously at high speed.
* **Intelligent Link Extraction:** Finds URLs in HTML tags (`<a>`, `<script>`, etc.), and also within JavaScript code and strings using regular expressions.
* **Automatic Scope Control:** Maintains focus on the target domain and its subdomains, avoiding the crawl of third-party links.
* **Respects `robots.txt`:** Fetches and obeys the rules defined in the target's `robots.txt` file for more ethical crawling.
* **URL Normalization:** Cleans and standardizes discovered URLs to avoid duplicate work and ensure data consistency.
* **Structured Output:** Generates results in real-time (streaming) as JSON objects and can create a final, consolidated summary report of all findings.
* **Flexibility:** Allows configuration of thread count, crawl depth, timeouts, and browser execution mode (headless or with a GUI).

---

## Getting Started

### Prerequisites

* Python 3.8+
* Pip

### Usage Examples

* **Basic scan on a target:**
    ```sh
    python3 mapcrawller.py -t example.com
    ```

* **Scan with more threads, saving a final summary:**
    ```sh
    python mapcrawller.py -t example.com -T 20 --summary results.json
    ```

* **Verbose scan with a visible browser UI (non-headless) for debugging:**
    ```sh
    python3 mapcrawller.py -t example.com -v --no-headless
    ```

* **Saving all discovered events in real-time (streaming):**
    ```sh
    python3 mapcrawller.py -t example.com -o events.jsonl
    ```

### Command-Line Options

| Argument | Alias | Description | Default |
| :--- | :--- | :--- | :--- |
| `--target` | `-t` | **(Required)** The target domain, without 'https://'. | N/A |
| `--threads` | `-T` | Number of parallel crawling workers. | 10 |
| `--timeout` | | Timeout in seconds for each request. | 15 |
| `--max-depth` | | Maximum crawl depth from the starting URL. | 5 |
| `--headless` | | Run the browser in headless mode. Use `--no-headless` to see the UI. | True |
| `--out` | `-o` | Output file for JSON events (one per line, streaming). | None |
| `--summary` | | Final JSON output file with a summary of all findings. | None |
| `--verbose` | `-v` | Enable verbose logging and print JSON events to the screen. | False |

---
