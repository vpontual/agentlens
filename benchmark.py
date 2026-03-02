import asyncio
import httpx
import time
import sys

BASE_URL = "http://localhost:7001"

TEST_SITES = [
    {"name": "CNN", "url": "https://www.cnn.com"},
    {"name": "NYT", "url": "https://www.nytimes.com"},
    {"name": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Artificial_intelligence"},
    {"name": "Stack Overflow", "url": "https://stackoverflow.com/questions/11227809/why-is-processing-a-sorted-array-faster-than-processing-an-unsorted-array"},
    {"name": "GitHub", "url": "https://github.com/google/gemini-cli"},
    {"name": "Reddit", "url": "https://www.reddit.com/r/python"},
    {"name": "Hacker News", "url": "https://news.ycombinator.com"},
]

async def run_benchmark():
    print(f"{'Site':<15} | {'Type':<12} | {'Tokens':<10} | {'Status':<8} | {'Reduction':<10}")
    print("-" * 65)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for site in TEST_SITES:
            try:
                # Get raw HTML size first (simple fetch)
                t0 = time.time()
                raw_resp = await client.get(site["url"], follow_redirects=True)
                raw_tokens = len(raw_resp.text) // 4
                
                # Get proxy result
                proxy_resp = await client.get(f"{BASE_URL}/parse", params={"url": site["url"], "max_tokens": 10000})
                proxy_resp.raise_for_status()
                data = proxy_resp.json()
                
                proxy_tokens = data.get("token_estimate", 0)
                ptype = data.get("type", "unknown")
                reduction = (1 - (proxy_tokens / raw_tokens)) * 100 if raw_tokens > 0 else 0
                
                print(f"{site['name']:<15} | {ptype:<12} | {proxy_tokens:<10,} | {data.get('status_code', 200):<8} | {reduction:>8.1f}%")
            except Exception as e:
                print(f"{site['name']:<15} | ERROR: {str(e)[:40]}")

if __name__ == "__main__":
    # Wait for server to be ready
    asyncio.run(run_benchmark())
