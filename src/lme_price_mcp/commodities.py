"""The commodity registry: one place that knows units, live symbols and aliases.

Adding a commodity means adding one :class:`CommoditySpec` here (plus, if the
offline path should cover it, a snapshot file of the same key). Aliases make
the tools usable from Chinese and English queries alike: ``铜``, ``Cu`` and
``copper`` all resolve to the same instrument.
"""

from __future__ import annotations

from dataclasses import dataclass

from mining_brief_core.errors import DataNotFoundError


@dataclass(frozen=True)
class CommoditySpec:
    key: str
    label_en: str
    label_zh: str
    unit: str  # price unit including currency, e.g. "USD/t" or "CNY/t"
    live_symbol: str | None  # sina hq symbol ("hf_" = LME 3M, "nf_" = domestic futures)
    snapshot_file: str
    aliases: tuple[str, ...] = ()

    @property
    def normalized_aliases(self) -> tuple[str, ...]:
        return tuple(alias.strip().lower() for alias in self.aliases)


_SPECS: tuple[CommoditySpec, ...] = (
    CommoditySpec(
        key="copper",
        label_en="LME copper (3-month)",
        label_zh="LME 铜（3月期）",
        unit="USD/t",
        live_symbol="hf_CAD",
        snapshot_file="copper.json",
        aliases=("cu", "lme copper", "铜", "伦铜", "lme铜"),
    ),
    CommoditySpec(
        key="zinc",
        label_en="LME zinc (3-month)",
        label_zh="LME 锌（3月期）",
        unit="USD/t",
        live_symbol="hf_ZSD",
        snapshot_file="zinc.json",
        aliases=("zn", "lme zinc", "锌", "伦锌", "lme锌"),
    ),
    CommoditySpec(
        key="nickel",
        label_en="LME nickel (3-month)",
        label_zh="LME 镍（3月期）",
        unit="USD/t",
        live_symbol="hf_NID",
        snapshot_file="nickel.json",
        aliases=("ni", "lme nickel", "镍", "伦镍", "lme镍"),
    ),
    CommoditySpec(
        key="lithium_carbonate",
        label_en="Lithium carbonate (GFEX main contract)",
        label_zh="碳酸锂（广期所主力）",
        unit="CNY/t",
        live_symbol="nf_LC0",
        snapshot_file="lithium_carbonate.json",
        aliases=(
            "lithium",
            "li2co3",
            "lithium carbonate",
            "lc",
            "碳酸锂",
            "锂",
            "锂价",
            "电碳",
        ),
    ),
    CommoditySpec(
        key="iron_ore",
        label_en="Iron ore (DCE main contract)",
        label_zh="铁矿石（大商所主力）",
        unit="CNY/t",
        live_symbol="nf_I0",
        snapshot_file="iron_ore.json",
        aliases=("iron", "iron ore", "fe", "i", "铁矿石", "铁矿"),
    ),
)

COMMODITIES: dict[str, CommoditySpec] = {spec.key: spec for spec in _SPECS}

_ALIAS_INDEX: dict[str, str] = {}
for _spec in _SPECS:
    _ALIAS_INDEX[_spec.key] = _spec.key
    for _alias in _spec.normalized_aliases:
        _ALIAS_INDEX.setdefault(_alias, _spec.key)


def supported_commodities() -> list[str]:
    return list(COMMODITIES)


def resolve_commodity(raw: str) -> CommoditySpec:
    """Resolve a user-supplied commodity name/alias/symbol to its spec."""
    token = raw.strip().lower()
    key = _ALIAS_INDEX.get(token) or _ALIAS_INDEX.get(token.replace(" ", "_"))
    if key is None:
        supported = ", ".join(COMMODITIES)
        raise DataNotFoundError(f"unknown commodity {raw!r}; supported keys: {supported}")
    return COMMODITIES[key]
