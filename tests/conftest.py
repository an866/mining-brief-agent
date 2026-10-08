"""Shared pytest fixtures.

Tests must be hermetic: no live network, no dependence on the developer's
environment. The autouse fixture below clears the data-source mode env vars so
a developer who exports ``MINING_NEWS_SOURCE=live`` for a manual demo doesn't
silently change test behavior.
"""

from __future__ import annotations

import pytest

_SOURCE_MODE_VARS = ("MINING_NEWS_SOURCE", "MINING_PRICE_SOURCE")


@pytest.fixture(autouse=True)
def _clean_source_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _SOURCE_MODE_VARS:
        monkeypatch.delenv(var, raising=False)
