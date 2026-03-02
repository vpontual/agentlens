# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AgentLens is a local FastAPI server that converts any URL into structured, token-efficient JSON for LLM agents. It strips HTML noise and returns clean Markdown content plus an interaction schema (forms, buttons, links). It runs on port 7001.

## Environment

**Always use conda to manage the Python environment.** Do not use the system or Homebrew Python — we must not alter the default macOS Python installation.

```bash
# Activate the conda environment first (required before any command below)
conda activate agentview
```

The `agentview` conda env provides Python 3.13. The `.venv` virtualenv is created inside it for pip dependencies.

## Commands

All commands below assume you have activated the conda environment first (`conda activate agentview`).

```bash
# Setup & run (auto-creates venv, installs deps, installs Playwright)
bash start.sh

# Run manually
conda activate agentview && source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 7001 --reload

# Run all tests
conda activate agentview && source .venv/bin/activate
pytest tests/

# Run a single test file
pytest tests/test_patterns.py

# Run a single test function
pytest tests/test_patterns.py::test_serp_pattern_google

# Run with coverage
pytest --cov=main tests/

# Benchmark against live sites (requires server running)
python benchmark_compare.py
```

## Architecture

The entire application lives in **`main.py`** (~650 lines). There are no submodules or packages.

### Pattern Registry (core abstraction)

The `PatternRegistry` holds an ordered list of `BasePattern` subclasses. On each request, it iterates patterns in priority order — the first pattern that `matches(url, soup)` wins and its `extract()` produces the response. If no pattern matches, `process_html_generic()` uses trafilatura as a fallback (type: "article").

Pattern priority order: `SERPPattern` → `ECommercePattern` → `SearchPattern` → `ThreadPattern` → `DocumentationPattern`

Each pattern returns a different response shape:
- **serp**: `results[]` array of search result objects
- **ecommerce**: `product` object with price/sku/availability
- **search_config**: `search_template` URL string
- **thread**: `messages[]` flat-tree with parent-ID references
- **documentation**: `sections[]` chunked by header level (cap: 50 sections), includes `<table>` elements

### Extraction Quality

- **Trafilatura quality gate**: If trafilatura returns < 1% of HTML size on large pages (> 50KB), falls back to markdownify. Prevents near-empty extraction on content-rich sites like NPR and CNN.
- **Documentation heuristic**: Structural match requires `<pre>` blocks (not inline `<code>`) to avoid misclassifying Wikipedia/blogs as docs.

### Dual-Path Fetching

Requests start with a static `httpx` fetch. If wall detection (`detect_walls`) or JS-wall detection (`detect_js_wall`) triggers, it auto-escalates to Playwright (headless Chromium). Domain render-mode preferences are cached in `SiteCache` (persisted to `site_cache.json`) so repeat visits skip the static attempt.

### Interaction Mapping

`map_interactions()` does a single-pass DOM traversal separating:
- **actions**: forms + button-style CTAs (class matching `btn|button|cta|primary|submit|login|signup`)
- **links**: standard navigation links, tagged with `is_nav` for same-domain links

### API Endpoints

- `GET/POST /parse` — single URL parse (full content extraction + interactions)
- `GET /agent-manifest` — links + forms only, zero content extraction (fast scouting)
- `POST /batch-parse` — multiple URLs, streamed as NDJSON
- `GET /instructions` — plain-text LLM self-onboarding prompt (dynamic: uses `AGENTLENS_PUBLIC_URL` env var for base URL)
- `GET /health` — health check
- `GET /cache/clear` — reset domain render-mode cache
- `GET /` — serves `static/index.html` UI

## Testing

47 tests across 3 files using `pytest-asyncio` with an `httpx.AsyncClient` test fixture wrapping the FastAPI app (no live server needed). Pattern tests instantiate pattern classes directly and call `matches()`/`extract()` with crafted HTML. Helper tests cover `map_interactions`, `detect_walls`, `detect_js_wall`, and the trafilatura quality gate.

## Conventions

- **Pattern-first**: prefer generalized structural patterns over site-specific scraping logic
- **Token efficiency**: use compact schemas (flat-tree threads, section-chunked docs) to minimize LLM token consumption
- Reddit URLs are automatically rewritten to `old.reddit.com` for better static extraction
