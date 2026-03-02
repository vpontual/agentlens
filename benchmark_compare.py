"""
Benchmark: Raw HTML vs AgentLens
Compares token counts and estimates content loss.
"""
import asyncio
import httpx
import time
import json
import re

PROXY_URL = "http://localhost:7001"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

TEST_SITES = [
    {"name": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Artificial_intelligence", "category": "documentation"},
    {"name": "CNN", "url": "https://www.cnn.com", "category": "article"},
    {"name": "Hacker News", "url": "https://news.ycombinator.com", "category": "article"},
    {"name": "Python Docs", "url": "https://docs.python.org/3/tutorial/classes.html", "category": "documentation"},
    {"name": "GitHub Repo", "url": "https://github.com/fastapi/fastapi", "category": "article"},
    {"name": "MDN Web Docs", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions", "category": "documentation"},
    {"name": "BBC News", "url": "https://www.bbc.com/news", "category": "article"},
    {"name": "NPR", "url": "https://www.npr.org", "category": "article"},
    {"name": "Stack Overflow", "url": "https://stackoverflow.com/questions/11227809/why-is-processing-a-sorted-array-faster-than-processing-an-unsorted-array", "category": "thread"},
    {"name": "Reddit", "url": "https://old.reddit.com/r/python/top/?t=week", "category": "thread"},
]


def strip_to_visible_text(html: str) -> str:
    """Extract only visible text from raw HTML for content-loss comparison."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "meta", "link", "noscript", "svg", "path",
                      "nav", "header", "footer", "aside"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def estimate_content_loss(raw_visible_text: str, proxy_content: str) -> float:
    """
    Estimate % of meaningful content lost by proxy extraction.

    Approach: extract unique meaningful words (4+ chars) from both the raw
    visible text and proxy content, then measure what fraction of raw words
    are missing from the proxy output. We filter short words to avoid noise
    from nav items, buttons, etc. that are intentionally stripped.
    """
    def meaningful_words(text: str) -> set:
        words = re.findall(r'[a-zA-Z]{4,}', text.lower())
        return set(words)

    raw_words = meaningful_words(raw_visible_text)
    proxy_words = meaningful_words(proxy_content)

    if not raw_words:
        return 0.0

    # Words in raw that are NOT in proxy output
    lost_words = raw_words - proxy_words

    # But many "lost" words are navigational/boilerplate (intentionally removed).
    # We estimate that as a rough content loss %.
    loss_pct = (len(lost_words) / len(raw_words)) * 100
    return round(loss_pct, 1)


async def run_benchmark():
    results = []

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30.0) as raw_client:
        async with httpx.AsyncClient(timeout=30.0) as proxy_client:
            for site in TEST_SITES:
                row = {"name": site["name"], "category": site["category"], "url": site["url"]}

                # 1. Fetch raw HTML
                try:
                    t0 = time.time()
                    raw_resp = await raw_client.get(site["url"])
                    raw_ms = int((time.time() - t0) * 1000)
                    raw_html = raw_resp.text
                    raw_chars = len(raw_html)
                    raw_tokens = raw_chars // 4
                    raw_visible = strip_to_visible_text(raw_html)
                    row.update({"raw_chars": raw_chars, "raw_tokens": raw_tokens, "raw_ms": raw_ms})
                except Exception as e:
                    row["error"] = f"Raw fetch failed: {e}"
                    results.append(row)
                    continue

                # 2. Fetch via proxy
                try:
                    t0 = time.time()
                    proxy_resp = await proxy_client.get(
                        f"{PROXY_URL}/parse",
                        params={"url": site["url"], "max_tokens": 50000}
                    )
                    if proxy_resp.status_code >= 400:
                        row["error"] = f"Proxy returned {proxy_resp.status_code}: {proxy_resp.text[:100]}"
                        results.append(row)
                        continue
                    proxy_ms = int((time.time() - t0) * 1000)
                    data = proxy_resp.json()

                    # Proxy content = content field + any structured data
                    proxy_content = data.get("content", "")
                    # For threads, also count messages text
                    if data.get("messages"):
                        proxy_content += " " + " ".join(m.get("text", "") for m in data["messages"])
                    # For docs, also count sections
                    if data.get("sections"):
                        proxy_content += " " + " ".join(s.get("content", "") for s in data["sections"])
                    # For SERP, count result snippets
                    if data.get("results"):
                        proxy_content += " " + " ".join(r.get("snippet", "") or "" for r in data["results"])

                    proxy_chars = len(json.dumps(data))
                    proxy_tokens = proxy_chars // 4
                    detected_type = data.get("type", "unknown")
                    render_mode = data.get("render_mode", "?")

                    # 3. Calculate savings & content loss
                    token_reduction = ((raw_tokens - proxy_tokens) / raw_tokens * 100) if raw_tokens > 0 else 0
                    content_loss = estimate_content_loss(raw_visible, proxy_content)

                    row.update({
                        "proxy_chars": proxy_chars,
                        "proxy_tokens": proxy_tokens,
                        "proxy_ms": proxy_ms,
                        "type": detected_type,
                        "render_mode": render_mode,
                        "token_reduction_pct": round(token_reduction, 1),
                        "est_content_loss_pct": content_loss,
                    })
                except Exception as e:
                    row["error"] = f"Proxy failed: {e}"

                results.append(row)

    # Print results table
    print()
    print(f"{'Site':<16} {'Type':<14} {'Raw Tokens':>12} {'Proxy Tokens':>14} {'Token Saving':>14} {'Est. Content Loss':>18} {'Mode':<8}")
    print("─" * 100)

    for r in results:
        if "error" in r:
            print(f"{r['name']:<16} ERROR: {r['error']}")
            continue
        print(
            f"{r['name']:<16} "
            f"{r.get('type','?'):<14} "
            f"{r.get('raw_tokens',0):>10,}  "
            f"{r.get('proxy_tokens',0):>12,}  "
            f"{r.get('token_reduction_pct',0):>12.1f}%  "
            f"{r.get('est_content_loss_pct',0):>16.1f}%  "
            f"{r.get('render_mode','?'):<8}"
        )

    print("─" * 100)

    # Averages
    valid = [r for r in results if "error" not in r]
    if valid:
        avg_saving = sum(r["token_reduction_pct"] for r in valid) / len(valid)
        avg_loss = sum(r["est_content_loss_pct"] for r in valid) / len(valid)
        avg_raw = sum(r["raw_tokens"] for r in valid) / len(valid)
        avg_proxy = sum(r["proxy_tokens"] for r in valid) / len(valid)
        print(
            f"{'AVERAGE':<16} "
            f"{'':<14} "
            f"{int(avg_raw):>10,}  "
            f"{int(avg_proxy):>12,}  "
            f"{avg_saving:>12.1f}%  "
            f"{avg_loss:>16.1f}%  "
        )
    print()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
