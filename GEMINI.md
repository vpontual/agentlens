# AgentLens - Gemini Context

AgentLens is a specialized local HTTP proxy that transforms cluttered webpages into structured, "agent-ready" data. It significantly reduces token usage by stripping HTML noise and extracting only the core content (in Markdown) and interactive elements (links, forms, buttons).

## Project Overview

- **Purpose**: Bridge the gap between LLM agents and the web by providing a high-signal, low-noise representation of any URL.
- **Architecture**: A **Pattern-First** FastAPI server (v0.5.0) that routes requests through a dual-path parsing engine:
    - **Pattern Registry**: Detects structural patterns (e.g., `ThreadPattern` for discussions, `DocumentationPattern` for technical docs, `ECommercePattern`, `SERPPattern`) and returns optimized schemas.
    - **Generic Extraction**: Uses `trafilatura` (a hybrid density-based engine) as a high-fidelity fallback for articles and blogs, with a quality gate that falls back to markdownify when trafilatura captures < 1% of large pages (> 50KB).
    - **Interaction Mapping**: A unified, single-pass DOM traversal that identifies both standard links and "button-style" CTAs.
    - **Browser Path**: Uses `Playwright` (Chromium) for modern SPAs and JS-heavy sites, automatically detected via a weighted probe (`detect_js_wall`).
- **Key Technologies**: Python 3.13, FastAPI, trafilatura, httpx, BeautifulSoup4, markdownify, Playwright, pytest.

## Building and Running

### Prerequisites
- Python 3.13 (Experimental Python versions like 3.14 may have build issues with `greenlet`).
- Conda for environment isolation.

### Commands
- **Start Service**: `bash start.sh` (Auto-installs venv and dependencies).
- **Run Manually**:
    ```bash
    conda activate agentview
    uvicorn main:app --host 0.0.0.0 --port 7001 --reload
    ```
- **Run Tests**: `pytest tests/`

## API Reference

### 1. Parse URL (`/parse`)
Returns structured content, metadata, and interaction schema. Output varies by detected pattern:
- **Type: thread**: Optimized for Q&A and forum discussions.
- **Type: documentation**: Optimized for technical guides with section-level chunking (cap: 50 sections, includes tables).
- **Type: serp**: Extracts search results into clean lists.
- **Type: ecommerce**: Extracts price, SKU, and availability.
- **Type: article**: Generic high-fidelity Markdown extraction.

- **GET**: `/parse?url=<URL>&max_tokens=2000&include_links=true`
- **POST**:
  ```json
  {
    "url": "https://example.com",
    "max_tokens": 2000,
    "include_links": true,
    "include_actions": true,
    "force_browser": false
  }
  ```

### 2. Agent Manifest (`/agent-manifest`)
Returns only links, forms, and buttons — zero content extraction. Fast scouting endpoint for mapping site structure before committing to a full parse.
- **GET**: `/agent-manifest?url=<URL>&force_browser=false`

### 3. Batch Parse (`/batch-parse`)
Stream results for multiple URLs as JSONL.
- **POST**:
  ```json
  {
    "urls": ["https://example.com", "https://example.org"],
    "max_tokens": 2000
  }
  ```

## Agent Integration

Models should use the following strategies to interact with the proxy:

- **Self-Onboarding**: Initial task should be `GET /instructions` to parse the operational manual. The endpoint is dynamic — set `AGENTLENS_PUBLIC_URL` env var to embed the real base URL into the instructions. It also prompts the agent to save the config to memory for persistence across context compaction.
- **Scout First**: Use `GET /agent-manifest?url={url}` to map links and forms before committing to a full content fetch.
- **Tool Calling**: Define a `web_browse` tool that maps to `GET /parse?url={url}&force_browser={bool}`.
- **Pattern Handling**: 
    - If `type == "thread"`, the model must use the `messages` array for discussion context.
    - If `type == "serp"`, the model must use the `results` array for link discovery.
    - If `type == "ecommerce"`, the model must prioritize the `product` object.
- **Error Recovery**: If `wall_type` is returned, the model should retry with `force_browser=true` or look for login links in `actions`.

## Development Conventions

- **Pattern-First**: Always prefer generalized structural patterns over site-specific logic.
- **Token Efficiency**: Use optimized schemas (like flat-tree threads) to minimize indentation and repeated keys.
- **Semantic Mapping**: Navigation links (same domain) and functional actions (CTAs) are automatically separated in the `actions` and `links` arrays.
- **Wall Detection**: Automatic detection of paywalls (JSON-LD), login walls (UI strings), and anti-scraping challenges (Cloudflare).
- **JS Detection & Caching**: Automatic fallback to Playwright occurs if a page has low text density. Preferences are cached by domain to skip static fetch on repeat visits.
