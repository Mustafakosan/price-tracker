"""Load and validate config.toml. Secrets come from environment variables or .env."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


class ConfigError(ValueError):
    """Raised when config.toml is missing fields or has bad values."""


@dataclass(frozen=True)
class Product:
    name: str
    url: str
    selector: str
    currency: str | None = None


@dataclass(frozen=True)
class Settings:
    products: list[Product]
    database: Path = Path("data/prices.db")
    report: Path = Path("reports/price_report.xlsx")
    min_change_pct: Decimal = Decimal("0")
    delay_seconds: float = 2.0
    respect_robots: bool = True
    telegram_token: str | None = field(default=None, repr=False)
    telegram_chat_id: str | None = None


def load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from a .env file. Real environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def load_settings(path: str | Path) -> Settings:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    load_dotenv(path.parent / ".env")

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path.name} is not valid TOML: {exc}") from exc
    raw_products = data.get("products") or []
    if not raw_products:
        raise ConfigError("Config needs at least one [[products]] entry")

    products, seen = [], set()
    for i, item in enumerate(raw_products, start=1):
        missing = [k for k in ("name", "url", "selector") if not item.get(k)]
        if missing:
            raise ConfigError(f"Product #{i} is missing: {', '.join(missing)}")
        if item["name"] in seen:
            raise ConfigError(f"Duplicate product name: {item['name']!r}")
        seen.add(item["name"])
        products.append(Product(item["name"], item["url"], item["selector"], item.get("currency")))

    base = path.parent
    alerts = data.get("alerts") or {}
    scraping = data.get("scraping") or {}

    try:
        min_change = Decimal(str(alerts.get("min_change_percent", 0)))
    except ArithmeticError as exc:
        raise ConfigError("alerts.min_change_percent must be a number") from exc

    return Settings(
        products=products,
        database=base / data.get("database", "data/prices.db"),
        report=base / data.get("report", "reports/price_report.xlsx"),
        min_change_pct=min_change,
        delay_seconds=float(scraping.get("delay_seconds", 2.0)),
        respect_robots=bool(scraping.get("respect_robots", True)),
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
    )
