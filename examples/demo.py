"""Offline demo: simulates two days of price checks and builds a sample report.

    python examples/demo.py

No internet needed. It writes small product pages to examples/output/pages,
runs the tracker once, changes some prices, runs it again, and leaves the
finished report at examples/output/reports/price_report.xlsx.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tracker.__main__ import main  # noqa: E402

OUT = Path(__file__).resolve().parent / "output"

# (name, price on day 1, price on day 2, how the shop formats the price)
PRODUCTS = [
    ("Wireless Headphones X200", "1.299,90 TL", "1.149,90 TL"),
    ("Smart Watch S5", "2.499,00 TL", "2.699,00 TL"),
    ("USB-C Charger 65W", "449,90 TL", "449,90 TL"),
    ("Mechanical Keyboard K8", "1.849,00 TL", "1.699,00 TL"),
    ("Bluetooth Speaker Mini", "899,00 TL", "949,00 TL"),
]

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>{name}</title></head>
<body><div class="product"><h1>{name}</h1>
<span class="price">{price}</span></div></body></html>"""


def slug(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")


def write_pages(day: int) -> None:
    pages = OUT / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    for name, day1, day2 in PRODUCTS:
        price = day1 if day == 1 else day2
        (pages / f"{slug(name)}.html").write_text(PAGE.format(name=name, price=price), encoding="utf-8")


def write_config() -> Path:
    lines = [
        'database = "data/prices.db"',
        'report = "reports/price_report.xlsx"',
        "[alerts]",
        "min_change_percent = 1",
        "[scraping]",
        "delay_seconds = 0",
    ]
    for name, *_ in PRODUCTS:
        url = (OUT / "pages" / f"{slug(name)}.html").as_uri()
        # json.dumps gives a correctly quoted/escaped TOML basic string
        lines += ["[[products]]", f"name = {json.dumps(name)}", f"url = {json.dumps(url)}",
                  'selector = ".product .price"', 'currency = "TRY"']
    path = OUT / "config.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    write_pages(day=1)
    config = write_config()

    print("\n=== Day 1: first check (builds the baseline) ===", flush=True)
    main(["--config", str(config)])

    print("\n=== Day 2: prices changed on the shop ===", flush=True)
    write_pages(day=2)
    main(["--config", str(config)])

    print(f"\nDone. Open {OUT / 'reports' / 'price_report.xlsx'}")
