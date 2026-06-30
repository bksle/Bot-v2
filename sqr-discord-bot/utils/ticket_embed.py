"""Professional ticket panel embeds with per-category branding."""

from __future__ import annotations

from pathlib import Path

import discord

from config.tickets import (
    TICKET_SPECS,
    VENDORS_VALUE,
    option_label_for_value,
    option_value_for_category_id,
    ticket_color_for_channel,
    ticket_color_for_option,
    ticket_emoji_for_channel,
    ticket_label_for_channel,
)

_SETUP_LOGO = Path(__file__).resolve().parent.parent / "assets" / "tickets" / "logo.png"
_SETUP_COLOR = 0x4A9EFF

_SERVICE_ARABIC_NAMES: dict[str, str] = {
    "xim": "خدمة XIM",
    "chairs": "كراسي الألعاب",
    "snap": "خدمات السناب",
    "tweak": "خدمة التويك",
    "zen": "كرونيس زين",
    "spoof": "خدمة سبوف",
    "iptv": "اشتراكات IPTV",
    "color_aim": "تتبع الألوان",
    VENDORS_VALUE: "الشراكات والمتاجر",
}


def setup_panel_logo_file() -> discord.File | None:
    if _SETUP_LOGO.is_file():
        return discord.File(_SETUP_LOGO, filename="logo.png")
    return None


def build_setup_panel_embed() -> discord.Embed:
    """Premium bilingual panel for /setup."""
    embed = discord.Embed(
        title="✦ SQR Store — Support Center | مركز الدعم ✦",
        description=(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🇬🇧 **Welcome to SQR Store Premium Support**\n"
            "Select your **service category** below — a **private ticket** "
            "opens instantly for you.\n\n"
            "🇸🇦 **مرحباً بك في دعم SQR Store الفاخر**\n"
            "اختر **قسم خدمتك** من القائمة — وسيتم فتح **تذكرة خاصة** "
            "لك فوراً.\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=0xD4AF37,
    )

    embed.add_field(
        name="🛎️ Available Services · الأقسام",
        value=(
            "🔴 **XIM**　　🟠 **CHAIRS**　　🟡 **Snap**\n"
            "🟢 **Tweak**　　🔵 **Zen**　　　🟣 **Spoof**\n"
            "🟤 **IPTV**　　⚪ **COLOR・AIM**　⚫ **Vendors**"
        ),
        inline=False,
    )

    embed.add_field(
        name="📌 Before you open · قبل الفتح",
        value=(
            "▫️ Pick the **correct** category · اختر القسم **الصحيح**\n"
            "▫️ Describe your request clearly · اشرح طلبك **بوضوح**\n"
            "▫️ Our team replies ASAP · الإدارة ترد **بأقرب وقت**"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔒 Privacy · الخصوصية",
        value=(
            "Only **you** and **staff** see your ticket.\n"
            "التذكرة **خاصة** — يراها أنت والإدارة فقط."
        ),
        inline=False,
    )

    if _SETUP_LOGO.is_file():
        embed.set_thumbnail(url="attachment://logo.png")

    embed.set_footer(
        text="SQR Store · Premium Support · قائمة دائمة ▼"
    )
    embed.timestamp = discord.utils.utcnow()
    return embed


def build_ticket_setup_embed() -> discord.Embed:
    """Public ticket panel shown by /setup_tickets."""
    return build_setup_panel_embed()


def build_service_panel_embed(option_value: str) -> discord.Embed:
    """One-service ticket room panel (single open button)."""
    emoji = _emoji_for_option(option_value)
    label = option_label_for_value(option_value)
    arabic_name = _SERVICE_ARABIC_NAMES.get(option_value, label)
    color = ticket_color_for_option(option_value)

    embed = discord.Embed(
        title=f"{emoji} تذاكر {label} | SQR Store",
        description=(
            f"**{arabic_name}**\n\n"
            "مرحباً بك في قسم الدعم المخصص لهذه الخدمة.\n"
            "اضغط الزر أدناه لفتح تذكرة خاصة — سيتم إنشاؤها تلقائياً.\n\n"
            f"Welcome to the **{label}** support desk.\n"
            "Click the button below to open your private ticket."
        ),
        color=color,
    )

    embed.add_field(
        name="📌 ملاحظة",
        value=(
            "▫️ تذكرة واحدة لكل طلب\n"
            "▫️ اشرح مشكلتك بوضوح داخل التذكرة\n"
            "▫️ فريق الإدارة يرد بأقرب وقت"
        ),
        inline=False,
    )

    embed.set_footer(text=f"SQR Store · {label}")
    embed.timestamp = discord.utils.utcnow()
    return embed


def _status_text(*, claimed_by: discord.Member | None, stopped: bool) -> str:
    if stopped:
        return "⭐ بانتظار التقييم"
    if claimed_by is not None:
        return "🟢 قيد المعالجة"
    return "🟡 بانتظار الإدارة"


def build_ticket_panel_embed(
    *,
    channel: discord.TextChannel | None = None,
    option_value: str | None = None,
    opener: discord.Member | None = None,
    opener_id: int | None = None,
    claimed_by: discord.Member | None = None,
    stopped: bool = False,
    staff_mentions: str = "",
) -> discord.Embed:
    """Build the in-ticket control panel embed."""
    if option_value is None and channel is not None:
        option_value = _option_value_for_channel(channel)

    if option_value is not None:
        product_label = option_label_for_value(option_value)
        product_emoji = _emoji_for_option(option_value)
        color = ticket_color_for_option(option_value)
    elif channel is not None:
        product_label = ticket_label_for_channel(channel)
        product_emoji = ticket_emoji_for_channel(channel)
        color = ticket_color_for_channel(channel)
    else:
        product_label = "التذاكر"
        product_emoji = "🎫"
        color = 0x5865F2

    opener_display = opener.mention if opener is not None else f"<@{opener_id}>"
    claimed_value = claimed_by.mention if claimed_by is not None else "`—`"
    status = _status_text(claimed_by=claimed_by, stopped=stopped)

    embed = discord.Embed(
        title=f"{product_emoji} لوحة التحكم — {product_label}",
        description=(
            f"```\n"
            f"العميل   › {opener_display}\n"
            f"الحالة   › {status}\n"
            f"المستلم  › {claimed_value}\n"
            f"```"
        ),
        color=color,
    )

    embed.add_field(
        name="الأزرار",
        value=(
            "📥 **استلام** — تولّى التذكرة\n"
            "⭐ **إيقاف** — إرسال التقييم للعميل\n"
            "🔒 **إغلاق** — حفظ المحادثة وحذف القناة\n"
            "📋 **جمع التذاكر** — عرض كل التذاكر المفتوحة (إدارة)"
        ),
        inline=False,
    )

    if staff_mentions:
        embed.add_field(name="🔔 الإدارة", value=staff_mentions, inline=False)

    embed.set_footer(text="SQR Store · نظام التذاكر")
    embed.timestamp = discord.utils.utcnow()
    return embed


def _emoji_for_option(option_value: str) -> str:
    if option_value == VENDORS_VALUE:
        return "⚫️"
    return TICKET_SPECS[option_value].emoji


def _option_value_for_channel(channel: discord.TextChannel) -> str | None:
    if channel.category_id is None:
        return None
    return option_value_for_category_id(channel.category_id)
