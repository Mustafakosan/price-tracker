from unittest.mock import MagicMock

import pytest
import requests

from tracker.scraper import ExtractError, FetchError, Fetcher, extract_text

BOOK_PAGE = """
<html><body>
  <div class="product_main">
    <h1>A Light in the Attic</h1>
    <p class="price_color">£51.77</p>
  </div>
  <div class="related"><p class="price_color">£10.00</p></div>
</body></html>
"""


def response(status=200, text=""):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.text = text
    resp.encoding = "utf-8"
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    return resp


def test_extract_text_uses_first_match_in_scope():
    assert extract_text(BOOK_PAGE, ".product_main .price_color") == "£51.77"


def test_extract_text_prefers_meta_content_attribute():
    html = '<meta itemprop="price" content="1299.90"><span itemprop="price">1.299,90 TL</span>'
    assert extract_text(html, 'meta[itemprop="price"]') == "1299.90"


def test_extract_text_raises_when_selector_misses():
    with pytest.raises(ExtractError):
        extract_text(BOOK_PAGE, ".does-not-exist")


def test_fetch_reads_file_urls(tmp_path):
    page = tmp_path / "p.html"
    page.write_text(BOOK_PAGE, encoding="utf-8")
    assert "A Light in the Attic" in Fetcher(delay_seconds=0).fetch(page.as_uri())


def test_fetch_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("tracker.scraper.time.sleep", lambda s: None)
    session = MagicMock()
    session.headers = {}
    session.get.side_effect = [response(503), response(200, BOOK_PAGE)]
    fetcher = Fetcher(delay_seconds=0, respect_robots=False, session=session)
    assert "price_color" in fetcher.fetch("https://shop.example/item")
    assert session.get.call_count == 2


def test_fetch_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr("tracker.scraper.time.sleep", lambda s: None)
    session = MagicMock()
    session.headers = {}
    session.get.return_value = response(500)
    fetcher = Fetcher(delay_seconds=0, retries=3, respect_robots=False, session=session)
    with pytest.raises(FetchError):
        fetcher.fetch("https://shop.example/item")
    assert session.get.call_count == 3


def test_robots_txt_disallow_is_respected():
    session = MagicMock()
    session.headers = {}
    session.get.return_value = response(200, "User-agent: *\nDisallow: /private/")
    fetcher = Fetcher(delay_seconds=0, session=session)
    assert fetcher.is_allowed("https://shop.example/public/item")
    with pytest.raises(FetchError, match="robots.txt"):
        fetcher.fetch("https://shop.example/private/item")
    # robots.txt is downloaded once per site, not once per page
    assert session.get.call_count == 1


def test_missing_robots_txt_allows_everything():
    session = MagicMock()
    session.headers = {}
    session.get.return_value = response(404)
    assert Fetcher(delay_seconds=0, session=session).is_allowed("https://shop.example/anything")
