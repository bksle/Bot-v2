"""Ticket opening visuals and per-service welcome copy."""

from __future__ import annotations

import logging
from pathlib import Path

import discord

from config.tickets import VENDORS_VALUE

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "tickets"
_LOGO_FILE = _ASSETS_DIR / "logo.png"

_BANNER_FILES: dict[str, str] = {
    "xim": "banner_red.png",
    "chairs": "banner_orange.png",
    "snap": "banner_yellow.png",
    "tweak": "banner_green.png",
    "zen": "banner_blue.png",
    "spoof": "banner_purple.png",
    "iptv": "banner_brown.png",
    "color_aim": "banner_white.png",
    VENDORS_VALUE: "banner_black.png",
}

_WELCOME_MESSAGES: dict[str, str] = {
    "xim": (
        "🔴 ⦅ خدمة XIM ⦆ 🔴\n\n"
        "❤️ أهلاً وسهلاً بك يا رهيب في قسم خدمة XIM! 🌹\n"
        "شكراً لفتح التيكت، نورتنا وشرفتنا بتواصلك معنا. هذا المكان مخصص لاستفساراتك وطلباتك الخاصة بـ XIM، "
        "وأنت الآن في أيدٍ أمينة. اكتب طلبك، وفريق الدعم جاهز يخدمك من عيونه ويضبط إيمك! 🚀\n\n"
        "❤️ Welcome, Awesome, to the XIM Service section! 🌹\n"
        "Thank you for opening a ticket! This is your dedicated space for all XIM requests, "
        "and you are in good hands. Drop your inquiry below, and our team is ready to assist you right away! 🚀"
    ),
    "chairs": (
        "🟠 ⦅ كراسي الألعاب ⦆ 🟠\n\n"
        "🧡 أهلاً وسهلاً بك يا رهيب في قسم كراسي الألعاب! 🌹\n"
        "شكراً لفتح التيكت، نورتنا وشرفتنا. هذا المكان مخصص لطلبك، عشان تضمن الجلسة المريحة واللعب الأسطوري. "
        "تفضل اطرح استفسارك، وفريقنا بيخدمك وتستلم كرسيك بأسرع وقت! 🚀\n\n"
        "🧡 Welcome, Awesome, to the Gaming Chairs section! 🌹\n"
        "Thank you for opening a ticket! This space is dedicated to getting you the most comfortable gaming setup. "
        "Let us know what you need, and we'll get you sorted instantly! 🚀"
    ),
    "snap": (
        "🟡 ⦅ خدمات السناب ⦆ 🟡\n\n"
        "💛 أهلاً وسهلاً بك يا رهيب في قسم خدمات السناب! 🌹\n"
        "شكراً لفتح التيكت، نورتنا بوجودك. هنا المكان المخصص لكل ما يخص السناب شات، وأنت في المكان الصح. "
        "اكتب اللي بخاطرك، وفريقنا جاهز يضبطك بأسرع وقت! 🚀\n\n"
        "💛 Welcome, Awesome, to the Snapchat Services section! 🌹\n"
        "Thank you for opening a ticket! This is your dedicated place for anything Snapchat-related. "
        "Tell us what you need, and our team will handle it immediately! 🚀"
    ),
    "tweak": (
        "🟢 ⦅ خدمة التويك ⦆ 🟢\n\n"
        "💚 أهلاً وسهلاً بك يا رهيب في قسم التويك! 🌹\n"
        "شكراً لفتح التيكت، شرفتنا بتواصلك معنا. هذا المكان مخصص لطلبات التويك عشان ترفع أداء جهازك للماكس "
        "وتاخذ فريمات خيالية! اكتب طلبك، وخبرائنا جاهزين يخدمونك من عيونهم! 🚀\n\n"
        "💚 Welcome, Awesome, to the Tweak Service section! 🌹\n"
        "Thank you for opening a ticket! This space is dedicated to boosting your PC's performance to the max. "
        "Drop your request, and our experts will gladly assist you! 🚀"
    ),
    "zen": (
        "🔵 ⦅ قطعة كرونيس زين ⦆ 🔵\n\n"
        "💙 أهلاً وسهلاً بك يا رهيب في قسم كرونيس زين! 🌹\n"
        "شكراً لفتح التيكت، نورتنا وشرفتنا. هذا المكان المخصص لقطعة الكرونيس زين والسكربتات، وأنت الآن في أيدٍ أمينة. "
        "تفضل اطرح استفسارك أو طلبك، وفريقنا بيضبطك للآخر! 🚀\n\n"
        "💙 Welcome, Awesome, to the Cronus Zen section! 🌹\n"
        "Thank you for opening a ticket! This is your dedicated space for Cronus Zen and scripts. "
        "Drop your request below, and our team will get you fully geared up! 🚀"
    ),
    "spoof": (
        "🟣 ⦅ خدمة سبوف ⦆ 🟣\n\n"
        "💜 أهلاً وسهلاً بك يا رهيب في قسم سبوف! 🌹\n"
        "شكراً لفتح التيكت، أسعدتنا بتواصلك. هذا المكان مخصص لخدمات السبوف، وأمورك هنا بالسرية والأمان التام. "
        "اطرح طلبك، وفريق الدعم بيخلصه لك في أسرع وقت! 🚀\n\n"
        "💜 Welcome, Awesome, to the Spoof section! 🌹\n"
        "Thank you for opening a ticket! This space is dedicated to Spoof services, ensuring your safety and privacy. "
        "Let us know what you need, and we'll get it done fast! 🚀"
    ),
    "iptv": (
        "🟤 ⦅ اشتراكات IPTV ⦆ 🟤\n\n"
        "🤎 أهلاً وسهلاً بك يا رهيب في قسم IPTV! 🌹\n"
        "شكراً لفتح التيكت، نورتنا وشرفتنا. هذا المكان مخصص لاشتراكاتك عشان تتابع كل القنوات والمباريات "
        "بأعلى جودة وبدون تقطيع. اكتب طلبك، وفريقنا بيسلمك اشتراكك بأسرع وقت! 🚀\n\n"
        "🤎 Welcome, Awesome, to the IPTV section! 🌹\n"
        "Thank you for opening a ticket! This is your dedicated space for high-quality streaming and channels. "
        "Drop your request, and our team will set up your subscription instantly! 🚀"
    ),
    "color_aim": (
        "⚪ ⦅ تتبع الألوان ⦆ ⚪\n\n"
        "🤍 أهلاً وسهلاً بك يا رهيب في قسم تتبع الألوان! 🌹\n"
        "شكراً لفتح التيكت، شرفتنا ونورت المتجر. هذا المكان المخصص لخدمة تتبع الألوان الاحترافية، وأنت في أيدٍ أمينة. "
        "اترك طلبك هنا، وفريقنا بيضبط لك الأداء على أكمل وجه! 🚀\n\n"
        "🤍 Welcome, Awesome, to the Color Tracking section! 🌹\n"
        "Thank you for opening a ticket! This space is dedicated to our professional color tracking service. "
        "Drop your request below, and our team will fine-tune everything for you! 🚀"
    ),
    VENDORS_VALUE: (
        "⚫ ⦅ الشراكات والمتاجر ⦆ ⚫\n\n"
        "🖤 أهلاً وسهلاً بك يا شريك النجاح في قسم الشراكات! 🌹\n"
        "شكراً لفتح التيكت، شرفنا تواصلك معنا. هذا المكان المخصص للمتاجر، الشركاء، والتعاون التجاري. "
        "تفضل بطرح عرضك أو استفسارك، والإدارة راح تتواصل معك بأقرب وقت ممكن! 🚀\n\n"
        "🖤 Welcome, Partner, to the Partnerships & Affiliates section! 🌹\n"
        "Thank you for opening a ticket! This space is dedicated to store collaborations and business inquiries. "
        "Please share your proposal, and our management will get back to you shortly! 🚀"
    ),
}


def welcome_message_for(option_value: str) -> str:
    return _WELCOME_MESSAGES.get(
        option_value,
        "🎫 أهلاً بك في تذكرة **SQR Store** — اكتب طلبك وسيقوم فريق الإدارة بالرد عليك قريباً.",
    )


def _banner_path(option_value: str) -> Path | None:
    filename = _BANNER_FILES.get(option_value)
    if filename is None:
        return None
    path = _ASSETS_DIR / filename
    return path if path.is_file() else None


def _logo_path() -> Path | None:
    return _LOGO_FILE if _LOGO_FILE.is_file() else None


def _discord_file(path: Path) -> discord.File:
    return discord.File(path, filename=path.name)


_PING_LINE = "||@everyone|| ||@here||"


def _build_mention_block() -> str:
    return _PING_LINE


async def send_branded_visual_sequence(
    channel: discord.TextChannel,
    option_value: str,
    *,
    middle_text: str,
) -> bool:
    """Post logo → color banner → text → color banner."""
    logo = _logo_path()
    banner = _banner_path(option_value)

    try:
        if logo is not None:
            await channel.send(file=_discord_file(logo))
        else:
            logger.warning("Ticket logo missing at %s", _LOGO_FILE)

        if banner is not None:
            await channel.send(file=_discord_file(banner))
        else:
            logger.warning("Ticket banner missing for option %s", option_value)

        await channel.send(middle_text)

        if banner is not None:
            await channel.send(file=_discord_file(banner))

        return True
    except discord.HTTPException:
        logger.exception("Failed to post branded visuals in %s", channel.id)
        return False


async def send_service_panel_sequence(
    channel: discord.TextChannel,
    option_value: str,
    *,
    panel_embed: discord.Embed,
    panel_view: discord.ui.View,
) -> bool:
    """
    Service room setup flow:
    logo → color banner → mention + open button → color banner.
    """
    logo = _logo_path()
    banner = _banner_path(option_value)

    try:
        if logo is not None:
            await channel.send(file=_discord_file(logo))
        else:
            logger.warning("Ticket logo missing at %s", _LOGO_FILE)

        if banner is not None:
            await channel.send(file=_discord_file(banner))
        else:
            logger.warning("Ticket banner missing for option %s", option_value)

        await channel.send(
            content=_build_mention_block(),
            embed=panel_embed,
            view=panel_view,
        )

        if banner is not None:
            await channel.send(file=_discord_file(banner))

        return True
    except discord.HTTPException:
        logger.exception("Failed to post service panel in %s", channel.id)
        return False


async def send_ticket_opening_sequence(
    channel: discord.TextChannel,
    *,
    guild: discord.Guild,
    opener: discord.Member,
    option_value: str,
    control_embed: discord.Embed,
    control_view: discord.ui.View,
) -> bool:
    """
    Post the branded opening flow:
    logo → color banner → welcome text → color banner → control panel.
    """
    mention_block = _build_mention_block()
    ok = await send_branded_visual_sequence(
        channel,
        option_value,
        middle_text=f"{mention_block}\n\n{welcome_message_for(option_value)}",
    )
    if not ok:
        return False

    try:
        await channel.send(embed=control_embed, view=control_view)
        return True
    except discord.HTTPException:
        logger.exception("Failed to post ticket opening sequence in %s", channel.id)
        return False
