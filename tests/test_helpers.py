import pytest
import httpx
from unittest.mock import patch, AsyncMock
from bs4 import BeautifulSoup
from main import map_interactions, detect_js_wall, estimate_tokens, detect_walls, process_html_generic, _parse_url, app

def test_map_interactions_semantic():
    html = """
    <html>
        <body>
            <nav>
                <a href="/home">Home</a>
                <a href="/about">About</a>
            </nav>
            <main>
                <a href="/login" class="btn primary">Login Now</a>
                <a href="https://external.com/article">Read More</a>
                <button href="/signup">Sign Up</button>
                <form action="/search">
                    <input name="q">
                </form>
            </main>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    res = map_interactions(soup, "https://example.com")

    # Check Actions
    #
    # This previously asserted >= 2 action_links, counting <button href="/signup">
    # as one. `href` is not valid on a <button> and buttons do not navigate, so the
    # old code was manufacturing a link that does not exist. Buttons are now
    # captured as their own action_button type with a label and no href.
    action_links = [a for a in res["actions"] if a["type"] == "action_link"]
    assert len(action_links) >= 1
    assert any(a["label"] == "Login Now" and a["is_primary"] for a in action_links)
    assert all("href" in a for a in action_links), "an action_link must carry the href it links to"

    action_buttons = [a for a in res["actions"] if a["type"] == "action_button"]
    assert len(action_buttons) >= 1
    assert any(a["label"] == "Sign Up" for a in action_buttons)
    assert all("href" not in a for a in action_buttons), "a button does not navigate — it must not carry an href"

    # Check Links
    nav_links = [l for l in res["links"] if l.get("is_nav")]
    assert len(nav_links) >= 2

def test_js_wall_detection_weighted():
    html_sample = "<html>" + ("<div><span>Noise</span></div>" * 2000) + "</html>"
    bad_res = {"title": "Loading...", "content": "      "}
    assert detect_js_wall(html_sample, bad_res) is True

def test_js_wall_small_html():
    """Small HTML should never trigger JS wall detection."""
    html = "<html><body>Short page</body></html>"
    bad_res = {"title": "", "content": ""}
    assert detect_js_wall(html, bad_res) is False

def test_wall_detection_heuristics():
    # 1. Cloudflare header check
    assert detect_walls("", 403, {"server": "cloudflare"}) == "anti_scraping_challenge"

    # 2. Cloudflare body check
    cf_html = "<html><body>Error 1020: Access denied</body></html>"
    assert detect_walls(cf_html, 403, {}) == "anti_scraping_block"

    # 3. Paywall JSON-LD
    paywall_html = '<html><script type="application/ld+json">{"isAccessibleForFree": "False"}</script></html>'
    assert detect_walls(paywall_html, 200, {}) == "paywall_detected"

    # 4. Login UI string
    login_html = "<html><body>Please log in to continue reading this article</body></html>"
    assert detect_walls(login_html, 200, {}) == "login_or_paywall"

    # 5. Clear page
    assert detect_walls("<html><body>Real content</body></html>", 200, {}) is None

def test_wall_detection_empty_html():
    """Empty HTML with 200 should return None."""
    assert detect_walls("", 200, {}) is None

def test_token_estimation():
    text = "Word " * 100
    assert estimate_tokens(text) == len(text) // 4

def test_map_interactions_duplicate_links():
    """Duplicate links should be deduplicated."""
    html = """
    <html><body>
        <a href="https://example.com/page">Link One</a>
        <a href="https://example.com/page">Link Two</a>
        <a href="https://example.com/other">Other Link</a>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    res = map_interactions(soup, "https://example.com")
    hrefs = [l["href"] for l in res["links"]]
    assert hrefs.count("https://example.com/page") == 1

def test_map_interactions_link_limit():
    """Links should be capped at 40."""
    links_html = "".join(f'<a href="https://example.com/p{i}">Link {i}</a>' for i in range(60))
    html = f"<html><body>{links_html}</body></html>"
    soup = BeautifulSoup(html, "lxml")
    res = map_interactions(soup, "https://other.com")
    assert len(res["links"]) <= 40

def test_trafilatura_quality_gate_triggers_fallback():
    """When trafilatura returns < 1% of large HTML, markdownify fallback should trigger."""
    # Build a large HTML (>50KB) with substantial body content
    body_content = "<p>Important paragraph content here.</p>\n" * 1500
    html = f"<html><head><title>Big Page</title></head><body><main>{body_content}</main></body></html>"
    assert len(html) > 50_000  # ensure it's large enough

    # Mock trafilatura to return a tiny extraction (< 1% of HTML size)
    tiny_text = "tiny"
    with patch("main.trafilatura.bare_extraction", return_value={"text": tiny_text, "title": "Traf Title"}):
        result = process_html_generic(html, 50000)

    # The fallback should have produced much more content than trafilatura's "tiny"
    assert len(result["content"]) > len(tiny_text)
    assert "Important paragraph content" in result["content"]

def test_trafilatura_quality_gate_passes_good_extraction():
    """When trafilatura returns sufficient content, it should be used directly."""
    html = "<html><head><title>Page</title></head><body><p>Content</p></body></html>"
    good_text = "A" * 1000
    with patch("main.trafilatura.bare_extraction", return_value={"text": good_text, "title": "Good Title"}):
        result = process_html_generic(html, 50000)

    assert result["content"] == good_text
    assert result["title"] == "Good Title"


def test_headers_normalized_to_lowercase():
    """httpx preserves original header casing; downstream code uses lowercase keys.
    Headers must be normalized so lookups like 'content-type' and 'server' work."""
    from main import detect_walls

    # Simulate what httpx returns: headers with original casing
    raw_headers = {"Server": "cloudflare", "Content-Type": "text/html"}
    normalized = {k.lower(): v for k, v in raw_headers.items()}

    # Without normalization, lowercase lookup fails
    assert "server" not in raw_headers  # key is "Server", not "server"
    assert raw_headers.get("server") is None  # would miss Cloudflare detection

    # After normalization, lowercase lookup succeeds
    assert "server" in normalized
    assert detect_walls("", 403, normalized) == "anti_scraping_challenge"


@pytest.mark.asyncio
async def test_headers_normalized_in_code_path():
    """Regression: headers from httpx must be normalized before detect_walls.

    Without normalization, lowercase lookups like 'server' fail on headers
    with original casing (e.g., "Server"), causing Cloudflare detection to miss.
    This test exercises the real code path by patching the HTTP client.
    """
    class MockHeaders:
        def __init__(self):
            self._headers = {"Server": "cloudflare", "Content-Type": "text/html"}

        def items(self):
            return list(self._headers.items())

    class MockResponse:
        text = "<html><body><p>Test content</p></body></html>"
        status_code = 200
        headers = MockHeaders()

    app.state.client = httpx.AsyncClient()
    try:
        with patch("main.detect_walls", return_value=None) as mock_detect:
            with patch.object(app.state.client, "get", new_callable=AsyncMock,
                              return_value=MockResponse()):
                await _parse_url("https://example.com/page")

                # Verify detect_walls was called with normalized (lowercase-keyed) headers.
                # This is the assertion that fails when the fix is reverted:
                # without normalization, headers_arg.get("server") returns None.
                headers_arg = mock_detect.call_args[0][2]
                assert headers_arg.get("server") == "cloudflare", \
                    f"headers must be normalized to lowercase; got {headers_arg}"
    finally:
        await app.state.client.aclose()
