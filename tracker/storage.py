"""Price history kept in a single SQLite file - no database server needed."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product     TEXT    NOT NULL,
    url         TEXT    NOT NULL,
    price       TEXT    NOT NULL,   -- stored as text to keep Decimal precision
    currency    TEXT,
    checked_at  TEXT    NOT NULL    -- ISO-8601, UTC
);
CREATE INDEX IF NOT EXISTS idx_prices_product ON prices (product, checked_at);
"""


@dataclass(frozen=True)
class PricePoint:
    product: str
    url: str
    price: Decimal
    currency: str | None
    checked_at: datetime


class PriceStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "PriceStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @staticmethod
    def _row_to_point(row: tuple) -> PricePoint:
        product, url, price, currency, checked_at = row
        return PricePoint(product, url, Decimal(price), currency, datetime.fromisoformat(checked_at))

    def last_price(self, product: str) -> PricePoint | None:
        row = self._conn.execute(
            "SELECT product, url, price, currency, checked_at FROM prices "
            "WHERE product = ? ORDER BY checked_at DESC, id DESC LIMIT 1",
            (product,),
        ).fetchone()
        return self._row_to_point(row) if row else None

    def add(
        self,
        product: str,
        url: str,
        price: Decimal,
        currency: str | None,
        checked_at: datetime | None = None,
    ) -> PricePoint:
        checked_at = checked_at or datetime.now(timezone.utc)
        self._conn.execute(
            "INSERT INTO prices (product, url, price, currency, checked_at) VALUES (?, ?, ?, ?, ?)",
            (product, url, str(price), currency, checked_at.isoformat()),
        )
        self._conn.commit()
        return PricePoint(product, url, price, currency, checked_at)

    def history(self) -> list[PricePoint]:
        rows = self._conn.execute(
            "SELECT product, url, price, currency, checked_at FROM prices ORDER BY checked_at, id"
        ).fetchall()
        return [self._row_to_point(r) for r in rows]
