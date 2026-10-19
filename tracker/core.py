"""The check loop: fetch each product, compare with history, record the result."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable

from .config import Product
from .prices import PriceParseError, detect_currency, parse_price
from .scraper import ExtractError, FetchError, extract_text
from .storage import PriceStore

log = logging.getLogger(__name__)

FetchFn = Callable[[str], str]


@dataclass
class CheckResult:
    product: str
    url: str
    current: Decimal | None = None
    previous: Decimal | None = None
    currency: str | None = None
    error: str | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def ok(self) -> bool:
        return self.error is None and self.current is not None

    @property
    def change(self) -> Decimal | None:
        if self.current is None or self.previous is None:
            return None
        return self.current - self.previous

    @property
    def change_pct(self) -> Decimal | None:
        if self.change is None or not self.previous:
            return None
        return (self.change / self.previous * 100).quantize(Decimal("0.01"))

    def is_alert(self, min_change_pct: Decimal) -> bool:
        """True when the price moved by at least ``min_change_pct`` percent."""
        pct = self.change_pct
        return pct is not None and pct != 0 and abs(pct) >= min_change_pct


def check_product(product: Product, fetch: FetchFn, store: PriceStore) -> CheckResult:
    result = CheckResult(product=product.name, url=product.url)
    last = store.last_price(product.name)
    result.previous = last.price if last else None

    try:
        html = fetch(product.url)
        raw = extract_text(html, product.selector)
        result.current = parse_price(raw)
        result.currency = product.currency or detect_currency(raw)
    except (FetchError, ExtractError, PriceParseError, OSError) as exc:
        result.error = str(exc)
        log.error("%s: %s", product.name, exc)
        return result

    store.add(product.name, product.url, result.current, result.currency, result.checked_at)
    log.info("%s: %s %s (previous: %s)", product.name, result.current, result.currency or "", result.previous)
    return result


def run_checks(products: list[Product], fetch: FetchFn, store: PriceStore) -> list[CheckResult]:
    """Check every product. One broken page never stops the whole run."""
    return [check_product(p, fetch, store) for p in products]
