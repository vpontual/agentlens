import pytest
from unittest.mock import patch
from bs4 import BeautifulSoup
from main import map_interactions, detect_js_wall, estimate_tokens, detect_walls, process_html_generic

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
    action_links = [a for a in res["actions"] if a["type"] == "action_link"]
    assert len(action_links) >= 2
    assert any(a["label"] == "Login Now" and a["is_primary"] for a in action_links)

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
