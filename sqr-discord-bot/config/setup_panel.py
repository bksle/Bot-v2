"""Bilingual labels for legacy /setup ticket dropdown."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from config.tickets import VENDORS_VALUE


@dataclass(frozen=True, slots=True)
class SetupPanelOption:
    value: str
    label: str
    description: str


# label + description ≤ Discord limits (100 chars each)
SETUP_PANEL_OPTIONS: Final[tuple[SetupPanelOption, ...]] = (
    SetupPanelOption(
        VENDORS_VALUE,
        "「⚫️」Vendors · تجار وشركاء「⚫️」",
        "Partners & stores · الشراكات والمتاجر",
    ),
    SetupPanelOption(
        "xim",
        "「🔴」XIM · إكس آیم「🔴」",
        "XIM devices · أجهزة XIM",
    ),
    SetupPanelOption(
        "chairs",
        "「🟠」CHAIRS · كراسي「🟠」",
        "Gaming chairs · كراسي الألعاب",
    ),
    SetupPanelOption(
        "snap",
        "「🟡」Snap · سناب「🟡」",
        "Snapchat services · خدمات السناب",
    ),
    SetupPanelOption(
        "tweak",
        "「🟢」Tweak · تويك「🟢」",
        "PC optimization · تحسين الأداء",
    ),
    SetupPanelOption(
        "zen",
        "「🔵」Zen · زين「🔵」",
        "Cronus Zen · كرونيس زين",
    ),
    SetupPanelOption(
        "spoof",
        "「🟣」Spoof · سبوف「🟣」",
        "HWID spoof · خدمة سبوف",
    ),
    SetupPanelOption(
        "iptv",
        "「🟤」IPTV · آی‌پی‌تی‌وی「🟤」",
        "IPTV subscriptions · اشتراكات IPTV",
    ),
    SetupPanelOption(
        "color_aim",
        "「⚪」COLOR・AIM · ألوان「⚪」",
        "Color tracking · تتبع الألوان",
    ),
)

SETUP_PANEL_COLOR: Final = 0xD4AF37
SETUP_SELECT_PLACEHOLDER: Final = "▼ اختر قسمك · Choose your service…"
