"""Fetch product pages politely and pull the price text out of them."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "PriceTrackerBot/1.0 (personal price monitoring)"


class FetchError(RuntimeError):
    """Raised when a page cannot be downloaded or is not allowed."""


class ExtractError(RuntimeError):
    """Raised when the configured selector finds nothing on the page."""


class Fetcher:
    """Downloads pages with retries, a polite delay and robots.txt checks.

    ``file://`` URLs are read from disk, which makes demos and tests work
    without any network access.
    """

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 15.0,
        retries: int = 3,
        delay_seconds: float = 2.0,
        respect_robots: bool = True,
        session: requests.Session | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = max(1, retries)
        self.delay_seconds = delay_seconds
        self.respect_robots = respect_robots
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last_request_at = 0.0

    # -- robots.txt -------------------------------------------------------
    def _robots_for(self, url: str) -> RobotFileParser | None:
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._robots:
            return self._robots[origin]

        parser: RobotFileParser | None = RobotFileParser()
        try:
            resp = self.session.get(f"{origin}/robots.txt", timeout=self.timeout)
            if resp.status_code >= 400:
                parser = None  # No robots.txt: nothing is disallowed.
            else:
                parser.parse(resp.text.splitlines())
        except requests.RequestException as exc:
            log.warning("Could not read robots.txt for %s: %s", origin, exc)
            parser = None
        self._robots[origin] = parser
        return parser

    def is_allowed(self, url: str) -> bool:
        if not self.respect_robots or urlparse(url).scheme == "file":
            return True
        parser = self._robots_for(url)
        return parser is None or parser.can_fetch(self.user_agent, url)

    # -- fetching ---------------------------------------------------------
    def _wait_politely(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def fetch(self, url: str) -> str:
        parts = urlparse(url)
        if parts.scheme == "file":
            # url2pathname turns "/C:/Users/x.html" into "C:\Users\x.html" on Windows
            return Path(url2pathname(parts.path)).read_text(encoding="utf-8")

        if not self.is_allowed(url):
            raise FetchError(f"robots.txt disallows {url}")

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            self._wait_politely()
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise FetchError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                resp.encoding = resp.encoding or resp.apparent_encoding
                return resp.text
            except (requests.RequestException, FetchError) as exc:
                last_error = exc
                log.warning("Attempt %d/%d failed for %s: %s", attempt, self.retries, url, exc)
                if attempt < self.retries:
                    time.sleep(2 ** attempt)  # 2s, 4s, ... back-off
        raise FetchError(f"Giving up on {url}: {last_error}")


def extract_text(html: str, selector: str) -> str:
    """Return the stripped text of the first element matching a CSS selector."""
    node = BeautifulSoup(html, "html.parser").select_one(selector)
    if node is None:
        raise ExtractError(f"Selector {selector!r} matched nothing")
    text = node.get("content") or node.get_text(" ", strip=True)
    return str(text).strip()
