# Contributing to AgentLens

## Dev Setup

```bash
git clone https://github.com/vp/agentlens.git
cd agentlens
pip install -r requirements.txt
python -m playwright install chromium
```

Playwright is only needed for live fetching — the test suite runs against the FastAPI app directly via `httpx.AsyncClient` and does not require a browser.

## Running Tests

```bash
pytest tests/
```

All 47 tests should pass. No running server or browser is needed.

## Code Conventions

- **Single-file architecture**: the entire application lives in `main.py`. Don't add submodules or packages.
- **Pattern-first design**: prefer generalized structural patterns (SERP, ecommerce, thread, docs) over site-specific scraping logic.
- **Token efficiency**: response schemas are designed to minimize LLM token consumption. Keep them compact.
- **No unnecessary dependencies**: only add a new dependency if there's no reasonable way to solve the problem with what's already in `requirements.txt`.

## Pull Requests

- Tests must pass (`pytest tests/`).
- Describe **what** the PR does and **why**.
- Keep PRs focused — one concern per PR when possible.

## Bug Reports

When filing an issue, include:

- The URL that produced incorrect output
- Expected vs actual output
- Whether the issue reproduces consistently
