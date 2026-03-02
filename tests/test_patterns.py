import pytest
from bs4 import BeautifulSoup
from main import ThreadPattern, DocumentationPattern, SERPPattern, ECommercePattern, SearchPattern

# --- SERP Pattern ---

@pytest.mark.asyncio
async def test_serp_pattern_google():
    p = SERPPattern()
    html = """
    <div class="g">
        <a href="https://site1.com"><h3>Result 1</h3></a>
        <div class="VwiC3b">Snippet 1</div>
    </div>
    <div class="tF2Cxc">
        <a href="https://site2.com"><h3>Result 2</h3></a>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    res = await p.extract("https://google.com/search?q=test", html, soup)
    assert res["type"] == "serp"
    assert len(res["results"]) == 2
    assert res["results"][0]["title"] == "Result 1"
    assert res["results"][0]["url"] == "https://site1.com"

# --- ECommerce Pattern ---

@pytest.mark.asyncio
async def test_ecommerce_pattern_json_ld():
    p = ECommercePattern()
    html = """
    <html>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "sku": "SKU123",
            "offers": {
                "price": "29.99",
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock"
            }
        }
        </script>
        <title>Great Product</title>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://store.com/p1", soup) is True
    res = await p.extract("https://store.com/p1", html, soup)
    assert res["type"] == "ecommerce"
    assert res["product"]["price"] == "29.99"
    assert res["product"]["sku"] == "SKU123"

def test_ecommerce_no_match_article_jsonld():
    """JSON-LD with @type: Article must NOT match ecommerce."""
    p = ECommercePattern()
    html = """
    <html>
        <script type="application/ld+json">
        {"@type": "Article", "headline": "News Story", "author": "Reporter"}
        </script>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://news.com/story", soup) is False

def test_ecommerce_match_graph_product():
    """JSON-LD with @type: Product inside @graph MUST match."""
    p = ECommercePattern()
    html = """
    <html>
        <script type="application/ld+json">
        {"@graph": [
            {"@type": "WebSite", "name": "Store"},
            {"@type": "Product", "sku": "ABC", "offers": {"price": "10"}}
        ]}
        </script>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://store.com/item", soup) is True

def test_ecommerce_no_match_organization_jsonld():
    """JSON-LD with @type: Organization must NOT match ecommerce."""
    p = ECommercePattern()
    html = """
    <html>
        <script type="application/ld+json">
        {"@type": "Organization", "name": "Wikipedia"}
        </script>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://en.wikipedia.org/wiki/Python", soup) is False

@pytest.mark.asyncio
async def test_ecommerce_extract_none_script_string():
    """extract() should handle script tags with no string content."""
    p = ECommercePattern()
    html = '<html><script type="application/ld+json"></script><title>Test</title></html>'
    soup = BeautifulSoup(html, "lxml")
    res = await p.extract("https://store.com", html, soup)
    assert res["type"] == "ecommerce"
    assert res["product"]["price"] is None

@pytest.mark.asyncio
async def test_ecommerce_extract_offers_array():
    """extract() should handle offers as an array."""
    p = ECommercePattern()
    html = """
    <html>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "sku": "ARR1",
            "offers": [
                {"price": "19.99", "priceCurrency": "EUR", "availability": "InStock"},
                {"price": "24.99", "priceCurrency": "EUR"}
            ]
        }
        </script>
        <title>Array Offers</title>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    res = await p.extract("https://store.com", html, soup)
    assert res["product"]["price"] == "19.99"
    assert res["product"]["currency"] == "EUR"

@pytest.mark.asyncio
async def test_ecommerce_extract_no_title():
    """extract() should not crash when soup.title is None."""
    p = ECommercePattern()
    html = '<html><body><script type="application/ld+json">{"@type":"Product"}</script></body></html>'
    soup = BeautifulSoup(html, "lxml")
    res = await p.extract("https://store.com", html, soup)
    assert res["title"] == "Product"

def test_ecommerce_structural_signals():
    """Two structural signals (price + add-to-cart) should match."""
    p = ECommercePattern()
    html = """
    <html><body>
        <span class="price">$29.99</span>
        <button class="add-to-cart">Add to Cart</button>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://store.com/product", soup) is True

def test_ecommerce_single_signal_no_match():
    """Only one structural signal should NOT match."""
    p = ECommercePattern()
    html = '<html><body><span class="price">$29.99</span></body></html>'
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://store.com/product", soup) is False

# --- Search Pattern ---

@pytest.mark.asyncio
async def test_search_pattern_detection():
    p = SearchPattern()
    html = """
    <html><body>
    <form role="search" action="/find" method="GET">
        <input type="text" name="q">
    </form>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    # URL with /search path should match
    assert p.matches("https://site.com/search?q=test", soup) is True
    res = await p.extract("https://site.com/search?q=test", html, soup)
    assert res["type"] == "search_config"
    assert res["search_template"] == "https://site.com/find?q={query}"

def test_search_no_match_nav_bar():
    """A search form in <nav> should NOT match."""
    p = SearchPattern()
    html = """
    <html><body>
        <nav>
            <form role="search" action="/search">
                <input type="text" name="q">
            </form>
        </nav>
        <main><p>Content</p></main>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://blog.com/", soup) is False

def test_search_match_url_path():
    """URL with /search path should match when form exists."""
    p = SearchPattern()
    html = """
    <html><body>
        <header>
            <form role="search" action="/search"><input name="q"></form>
        </header>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://site.com/search?q=python", soup) is True

def test_search_match_main_content():
    """Search form in <main> should match even without search URL."""
    p = SearchPattern()
    html = """
    <html><body>
        <main>
            <form role="search" action="/find"><input name="q"></form>
        </main>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://site.com/", soup) is True

# --- Thread Pattern ---

def test_thread_pattern_known_domains():
    p = ThreadPattern()
    assert p.matches("https://stackoverflow.com/questions/1", BeautifulSoup("", "lxml")) is True
    assert p.matches("https://news.ycombinator.com/item?id=123", BeautifulSoup("", "lxml")) is True
    assert p.matches("https://lobste.rs/s/abc123", BeautifulSoup("", "lxml")) is True
    assert p.matches("https://forum.discourse.org/t/1", BeautifulSoup("", "lxml")) is True

def test_thread_no_match_single_post_class():
    """A single .post class (e.g. WordPress) should NOT match as thread."""
    p = ThreadPattern()
    html = '<html><body><div class="post">Blog post content</div></body></html>'
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://blog.com/my-post", soup) is False

def test_thread_no_match_comment_count():
    """An element like .comment-count should NOT match as thread."""
    p = ThreadPattern()
    html = '<html><body><span class="comment-count">5 comments</span></body></html>'
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://blog.com/post", soup) is False

def test_thread_match_comments_section():
    """A #comments section with 2+ comment items should match."""
    p = ThreadPattern()
    html = """
    <html><body>
        <div id="comments">
            <div class="comment">First comment</div>
            <div class="comment">Second comment</div>
        </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://blog.com/post", soup) is True

def test_thread_match_three_containers():
    """3+ exact comment containers should match."""
    p = ThreadPattern()
    html = """
    <html><body>
        <div class="comment">One</div>
        <div class="comment">Two</div>
        <div class="comment">Three</div>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://forum.com/thread", soup) is True

# --- Documentation Pattern ---

def test_documentation_pattern_match_toc():
    p = DocumentationPattern()
    assert p.matches("https://docs.py.org", BeautifulSoup('<div id="toc"></div>', "lxml")) is True

def test_documentation_match_known_domain():
    """Known doc domains should match."""
    p = DocumentationPattern()
    assert p.matches("https://docs.python.org/3/library/json.html", BeautifulSoup("<html></html>", "lxml")) is True
    assert p.matches("https://developer.mozilla.org/en-US/docs/Web", BeautifulSoup("<html></html>", "lxml")) is True

def test_documentation_match_url_path():
    """URL path heuristics (/docs/, /api/, etc.) should match."""
    p = DocumentationPattern()
    assert p.matches("https://example.com/docs/getting-started", BeautifulSoup("<html></html>", "lxml")) is True
    assert p.matches("https://example.com/api/reference", BeautifulSoup("<html></html>", "lxml")) is True

def test_documentation_match_structural():
    """h1 + 3 h2s + pre blocks should match."""
    p = DocumentationPattern()
    html = """
    <html><body>
        <article>
            <h1>API Reference</h1>
            <h2>Installation</h2>
            <pre><code>pip install lib</code></pre>
            <h2>Usage</h2>
            <pre><code>import lib</code></pre>
            <h2>Configuration</h2>
            <pre>lib.config()</pre>
            <h2>FAQ</h2>
        </article>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://example.com/readme", soup) is True

def test_documentation_no_match_inline_code_only():
    """Inline <code> without <pre> should NOT trigger structural match."""
    p = DocumentationPattern()
    html = """
    <html><body>
        <article>
            <h1>Article Title</h1>
            <h2>Section One</h2>
            <p>Use <code>foo</code> for this.</p>
            <h2>Section Two</h2>
            <p>And <code>bar</code> for that.</p>
            <h2>Section Three</h2>
            <p>More text with <code>baz</code>.</p>
        </article>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://blog.com/article", soup) is False

def test_documentation_no_match_blog():
    """A blog post with just one h1 and no code should not match."""
    p = DocumentationPattern()
    html = """
    <html><body>
        <article>
            <h1>My Blog Post</h1>
            <p>Some content here.</p>
        </article>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert p.matches("https://blog.com/post", soup) is False

@pytest.mark.asyncio
async def test_documentation_extract_sections():
    """extract() should return sections chunked by header."""
    p = DocumentationPattern()
    html = """
    <html>
        <title>My Docs</title>
        <body>
            <article>
                <h1>Getting Started</h1>
                <p>Welcome to the docs.</p>
                <h2>Installation</h2>
                <p>Run pip install.</p>
                <pre>pip install mylib</pre>
                <h2>Usage</h2>
                <p>Import and use.</p>
            </article>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    res = await p.extract("https://example.com/docs", html, soup)
    assert res["type"] == "documentation"
    assert res["title"] == "My Docs"
    assert len(res["sections"]) >= 2
    assert res["total_sections"] == len(res["sections"])
    assert res["truncated"] is False

@pytest.mark.asyncio
async def test_documentation_extract_truncation():
    """extract() should cap at 50 sections and set truncated flag."""
    p = DocumentationPattern()
    sections_html = "".join(f"<h2>Section {i}</h2><p>Content {i}</p>" for i in range(55))
    html = f"<html><title>Big Docs</title><body><article><h1>Title</h1>{sections_html}</article></body></html>"
    soup = BeautifulSoup(html, "lxml")
    res = await p.extract("https://example.com/docs", html, soup)
    assert len(res["sections"]) == 50
    assert res["total_sections"] == 55  # 55 h2s (h1 section has no body content)
    assert res["truncated"] is True

@pytest.mark.asyncio
async def test_documentation_extract_includes_tables():
    """extract() should include table content in sections."""
    p = DocumentationPattern()
    html = """
    <html>
        <title>API Docs</title>
        <body>
            <article>
                <h1>API Reference</h1>
                <h2>Parameters</h2>
                <table>
                    <tr><th>Name</th><th>Type</th><th>Description</th></tr>
                    <tr><td>timeout</td><td>int</td><td>Request timeout in seconds</td></tr>
                    <tr><td>retries</td><td>int</td><td>Number of retries</td></tr>
                </table>
            </article>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    res = await p.extract("https://example.com/docs/api", html, soup)
    assert res["type"] == "documentation"
    params_section = next(s for s in res["sections"] if s["title"] == "Parameters")
    assert "timeout" in params_section["content"]
    assert "retries" in params_section["content"]
