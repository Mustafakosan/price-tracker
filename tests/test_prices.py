from decimal import Decimal

import pytest

from tracker.prices import PriceParseError, detect_currency, parse_price


@pytest.mark.parametrize(
    "text, expected",
    [
        ("£51.77", "51.77"),
        ("$1,299.90", "1299.90"),
        ("1.299,90 TL", "1299.90"),
        ("₺ 2.499", "2499"),
        ("1 299,00 €", "1299.00"),
        ("1 299,00 €", "1299.00"),
        ("Sale: 19.99 USD", "19.99"),
        ("12,5 TL", "12.5"),
        ("1.299.000 TL", "1299000"),
        ("Only 7", "7"),
        ("  449,90 TL  ", "449.90"),
    ],
)
def test_parse_price_formats(text, expected):
    assert parse_price(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["", "   ", "Out of stock", "Fiyat sorunuz"])
def test_parse_price_rejects_text_without_numbers(text):
    with pytest.raises(PriceParseError):
        parse_price(text)


@pytest.mark.parametrize(
    "text, code",
    [("£51.77", "GBP"), ("1.299,90 TL", "TRY"), ("₺99", "TRY"), ("$5", "USD"), ("10 €", "EUR"), ("42", None)],
)
def test_detect_currency(text, code):
    assert detect_currency(text) == code


def test_currency_code_is_not_matched_inside_words():
    # "TL" inside "TITLE" must not count as Turkish lira.
    assert detect_currency("TITLE 42") is None
