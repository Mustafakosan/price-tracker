"""Turn messy price text from web pages into numbers.

Handles the formats you actually meet on e-commerce sites:
    "£51.77", "$1,299.90", "1.299,90 TL", "₺ 2.499", "1 299,00 €", "Sale: 19.99 USD"
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_CURRENCY_SYMBOLS = {
    "₺": "TRY", "TL": "TRY", "TRY": "TRY",
    "$": "USD", "USD": "USD",
    "€": "EUR", "EUR": "EUR",
    "£": "GBP", "GBP": "GBP",
}

# A number made of digits with optional thousands/decimal separators.
_NUMBER = re.compile(r"\d[\d\s.,  ]*\d|\d")


class PriceParseError(ValueError):
    """Raised when no price can be read from the given text."""


def detect_currency(text: str) -> str | None:
    """Return an ISO currency code found in the text, or None."""
    upper = text.upper()
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol.isalpha():
            if re.search(rf"\b{symbol}\b", upper):
                return code
        elif symbol in text:
            return code
    return None


def _normalise(number: str) -> str:
    """Convert a localised number string to a plain '1234.56' string."""
    number = re.sub(r"[\s  ]", "", number)
    has_dot, has_comma = "." in number, "," in number

    if has_dot and has_comma:
        # Whichever separator comes last is the decimal separator.
        decimal_sep = "." if number.rfind(".") > number.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        return number.replace(thousands_sep, "").replace(decimal_sep, ".")

    if has_comma or has_dot:
        sep = "," if has_comma else "."
        groups = number.split(sep)
        # "1.299" / "12,500" / "1.299.000" -> thousands separators.
        # "51.77" / "19,9" -> decimal separator.
        if all(len(g) == 3 for g in groups[1:]):
            return number.replace(sep, "")
        if len(groups) == 2:
            return number.replace(sep, ".")
        raise PriceParseError(f"Ambiguous number: {number!r}")

    return number


def parse_price(text: str) -> Decimal:
    """Extract the first price in ``text`` as a Decimal.

    >>> parse_price("£51.77")
    Decimal('51.77')
    >>> parse_price("1.299,90 TL")
    Decimal('1299.90')
    """
    if not text or not text.strip():
        raise PriceParseError("Empty price text")

    match = _NUMBER.search(text)
    if not match:
        raise PriceParseError(f"No number found in {text!r}")

    try:
        value = Decimal(_normalise(match.group()))
    except InvalidOperation as exc:  # pragma: no cover - guarded by regex
        raise PriceParseError(f"Could not parse {text!r}") from exc

    if value < 0:
        raise PriceParseError(f"Negative price in {text!r}")
    return value
