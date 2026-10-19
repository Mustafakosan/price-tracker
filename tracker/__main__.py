"""Command line entry point:  python -m tracker --config config.toml"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import ConfigError, load_settings
from .core import run_checks
from .notifier import format_alert, make_notifier
from .report import write_report
from .scraper import Fetcher
from .storage import PriceStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tracker", description="Track product prices and alert on changes.")
    parser.add_argument("-c", "--config", default="config.toml", help="path to config file (default: config.toml)")
    parser.add_argument("--no-notify", action="store_true", help="skip alerts, only update history and report")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logs")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("tracker")

    try:
        settings = load_settings(args.config)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    fetcher = Fetcher(delay_seconds=settings.delay_seconds, respect_robots=settings.respect_robots)
    with PriceStore(settings.database) as store:
        results = run_checks(settings.products, fetcher.fetch, store)
        report = write_report(results, store.history(), settings.report)
    log.info("Report saved to %s", report)

    changed = [r for r in results if r.ok and r.is_alert(settings.min_change_pct)]
    errors = [r for r in results if not r.ok]

    if (changed or errors) and not args.no_notify:
        make_notifier(settings.telegram_token, settings.telegram_chat_id).send(format_alert(changed, errors))
    elif not changed:
        log.info("No price changes above %s%%.", settings.min_change_pct)

    return 1 if results and len(errors) == len(results) else 0


if __name__ == "__main__":
    sys.exit(main())
