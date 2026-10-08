"""Unit tests for the Sina quote-response parser.

Payloads are recorded-shape samples of ``hq.sinajs.cn`` responses; the exact
field layouts are undocumented by Sina, which is why the parser is pinned
here — if the format ever shifts, these tests fail loudly before the live
channel silently starts serving wrong numbers (and the service layer would
fall back to snapshots anyway).
"""

from __future__ import annotations

import pytest

from lme_price_mcp.providers.live import parse_hq_response
from mining_brief_core.errors import ProviderError

HF_PAYLOAD = (
    'var hq_str_hf_CAD="9520.500,,9528.000,9531.500,9475.000,9505.000,9505.500,'
    "9506.000,9505.000,9500.000,2025-10-03,03:59:55,2025-10-03,9480.000,9521.800\";\n"
)

NF_PAYLOAD = (
    'var hq_str_nf_LC0="碳酸锂连续,10:14:59,76000.000,76500.000,75500.000,76200.000,'
    "76050.000,76060.000,76050.000,123456,654321,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,"
    '0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0";\n'
)


def test_parses_lme_style_symbol() -> None:
    assert parse_hq_response(HF_PAYLOAD, "hf_CAD") == pytest.approx(9520.5)


def test_parses_domestic_futures_symbol() -> None:
    assert parse_hq_response(NF_PAYLOAD, "nf_LC0") == pytest.approx(76050.0)


def test_empty_quote_raises() -> None:
    payload = 'var hq_str_hf_CAD="";\n'
    with pytest.raises(ProviderError, match="empty quote"):
        parse_hq_response(payload, "hf_CAD")


def test_missing_symbol_raises() -> None:
    with pytest.raises(ProviderError, match="not present"):
        parse_hq_response(HF_PAYLOAD, "hf_ZSD")


def test_short_domestic_payload_raises() -> None:
    payload = 'var hq_str_nf_LC0="碳酸锂连续,10:14:59,76000.000";\n'
    with pytest.raises(ProviderError, match="fewer than"):
        parse_hq_response(payload, "nf_LC0")


def test_non_numeric_price_raises() -> None:
    payload = 'var hq_str_hf_CAD="not-a-number,rest";\n'
    with pytest.raises(ProviderError, match="not numeric"):
        parse_hq_response(payload, "hf_CAD")
