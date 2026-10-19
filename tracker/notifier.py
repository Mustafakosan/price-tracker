"""Send price-change alerts to Telegram (or print them when not configured)."""

from __future__ import annotations

import html
import logging
from decimal import Decimal

import requests

from .core import CheckResult

log = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4096  # max characters per Telegram message


def _money(value: Decimal, currency: str | None) -> str:
    return f"{value:,.2f} {currency or ''}".strip()


def format_alert(changed: list[CheckResult], errors: list[CheckResult]) -> str:
    """Build an HTML-formatted message summarising one run."""
    lines: list[str] = []
    if changed:
        lines.append(f"<b>📊 {len(changed)} price change(s)</b>")
        for r in changed:
            arrow = "🔺" if r.change > 0 else "🔻"
            lines.append(
                f"{arrow} <a href=\"{html.escape(r.url, quote=True)}\">{html.escape(r.product)}</a>\n"
                f"    {_money(r.previous, r.currency)} → <b>{_money(r.current, r.currency)}</b> "
                f"({r.change_pct:+.2f}%)"
            )
    if errors:
        if lines:
            lines.append("")
        lines.append(f"<b>⚠️ {len(errors)} product(s) could not be checked</b>")
        lines.extend(f"• {html.escape(r.product)}: {html.escape(r.error or '')}" for r in errors)

    message = "\n".join(lines)
    if len(message) > TELEGRAM_LIMIT:
        message = message[: TELEGRAM_LIMIT - 20] + "\n… (see report)"
    return message


class Notifier:
    def send(self, message: str) -> bool:
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    """Fallback when Telegram is not set up: just log the message."""

    def send(self, message: str) -> bool:
        log.info("Alert (Telegram not configured):\n%s", message)
        return True


class TelegramNotifier(Notifier):
    def __init__(self, token: str, chat_id: str, session: requests.Session | None = None) -> None:
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id
        self.session = session or requests.Session()

    def send(self, message: str) -> bool:
        try:
            resp = self.session.post(
                self.url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            # Never log self.url: it contains the bot token.
            log.error("Telegram send failed: %s", type(exc).__name__)
            return False


def make_notifier(token: str | None, chat_id: str | None) -> Notifier:
    if token and chat_id:
        return TelegramNotifier(token, chat_id)
    return ConsoleNotifier()
