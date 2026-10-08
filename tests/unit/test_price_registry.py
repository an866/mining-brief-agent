"""Unit tests for the commodity registry and its alias resolution."""

from __future__ import annotations

import pytest

from lme_price_mcp.commodities import (
    COMMODITIES,
    resolve_commodity,
    supported_commodities,
)
from mining_brief_core.errors import DataNotFoundError


@pytest.mark.parametrize(
    ("raw", "expected_key"),
    [
        ("copper", "copper"),
        ("Cu", "copper"),
        ("铜", "copper"),
        ("lme copper", "copper"),
        ("zinc", "zinc"),
        ("锌", "zinc"),
        ("nickel", "nickel"),
        ("镍", "nickel"),
        ("lithium_carbonate", "lithium_carbonate"),
        ("碳酸锂", "lithium_carbonate"),
        ("锂", "lithium_carbonate"),
        ("  LC  ", "lithium_carbonate"),
        ("iron ore", "iron_ore"),
        ("铁矿石", "iron_ore"),
    ],
)
def test_resolves_aliases(raw: str, expected_key: str) -> None:
    assert resolve_commodity(raw).key == expected_key


def test_unknown_commodity_raises() -> None:
    with pytest.raises(DataNotFoundError, match="unknown commodity"):
        resolve_commodity("unobtainium")


def test_registry_is_complete() -> None:
    assert set(supported_commodities()) == {
        "copper",
        "zinc",
        "nickel",
        "lithium_carbonate",
        "iron_ore",
    }
    for spec in COMMODITIES.values():
        assert spec.unit in ("USD/t", "CNY/t")
        assert spec.snapshot_file.endswith(".json")
