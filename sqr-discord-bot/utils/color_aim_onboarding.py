"""Embeds and copy for COLOR・AIM role onboarding."""

from __future__ import annotations

import discord

from config.color_aim import (
    COLOR_AIM_GUIDE_CHANNEL_ID,
    COLOR_AIM_SETTINGS_CHANNEL_ID,
    COLOR_AIM_UPDATES_CHANNEL_ID,
    _EMBED_COLOR,
    color_aim_download_url,
)

_GUIDE = f"<#{COLOR_AIM_GUIDE_CHANNEL_ID}>"
_UPDATES = f"<#{COLOR_AIM_UPDATES_CHANNEL_ID}>"
_SETTINGS = f"<#{COLOR_AIM_SETTINGS_CHANNEL_ID}>"


def _download_field_value() -> str:
    url = color_aim_download_url()
    if url:
        return f"▫️ حمّل البرنامج من هنا:\n{url}\n▫️ أو من {_GUIDE} مباشرة"
    return f"▫️ رابط التحميل موجود في {_GUIDE}"


def build_color_aim_channel_guide_embed() -> discord.Embed:
    """Permanent guide posted in the COLOR・AIM guide / download channel."""
    embed = discord.Embed(
        title="⚪ COLOR・AIM — تتبع الألوان | SQR Store",
        description=(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ **مرحباً بك في خدمة تتبع الألوان**\n"
            "هذا الروم مخصّص للشرح والتحميل بعد استلام رتبتك.\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=_EMBED_COLOR,
    )

    embed.add_field(
        name="📖 الشرح",
        value=(
            "▫️ بعد **تحقق الكود** في لوحة الاشتراك تحصل على رتبتك تلقائياً\n"
            "▫️ **فعّل الكود** داخل البرنامج (OAuth) — Discord يمنح الرتبة فقط\n"
            "▫️ اتبع خطوات الإعداد في روم الإعدادات قبل التشغيل\n"
            "▫️ راقب التحديثات من روم التحديثات دائماً"
        ),
        inline=False,
    )

    embed.add_field(
        name="⬇️ التحميل",
        value=_download_field_value(),
        inline=False,
    )

    embed.add_field(
        name="🔔 التحديثات",
        value=f"كل الإعلانات والنسخ الجديدة في {_UPDATES}",
        inline=False,
    )

    embed.add_field(
        name="⚙️ الإعدادات المطلوبة",
        value=(
            f"قبل ما تبدأ، نفّذ الإعدادات في {_SETTINGS}:\n"
            "▫️ إعدادات Windows / الشاشة\n"
            "▫️ إعدادات البرنامج حسب الدليل\n"
            "▫️ تأكد من مزامنة وقت الجهاز تلقائياً"
        ),
        inline=False,
    )

    embed.set_footer(text="SQR Store · COLOR・AIM · Premium")
    embed.timestamp = discord.utils.utcnow()
    return embed


def build_color_aim_ticket_guide_embed() -> discord.Embed:
    """Full COLOR・AIM walkthrough posted in the ticket after a valid code."""
    embed = build_color_aim_channel_guide_embed()
    embed.title = "📖 شرح تتبع الألوان — COLOR・AIM"
    embed.description = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ **تم التحقق من كودك — اقرأ الشرح قبل التشغيل**\n"
        "اتبع الخطوات بالترتيب عشان يشتغل معك من أول مرة.\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    embed.set_footer(text="SQR Store · COLOR・AIM · اقرأ الشرح قبل التشغيل")
    return embed


def is_color_aim_success_embed(embed: discord.Embed) -> bool:
    title = embed.title or ""
    return title.startswith("✅")


def build_color_aim_role_success_embed(
    *,
    member: discord.Member,
    role: discord.Role,
    code_already_used: bool | None,
) -> discord.Embed:
    """Ephemeral success reply after COLOR・AIM role is granted."""
    activation_note = (
        "الكود **لم يُفعَّل** بعد — فعّله داخل البرنامج."
        if code_already_used is False
        else "تفعيل البرنامج يتم من داخل التطبيق."
    )

    embed = discord.Embed(
        title="✅ تم التحقق — COLOR・AIM",
        description=(
            f"{member.mention} — تم منحك {role.mention} بنجاح.\n\n"
            f"⚠️ {activation_note}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "**خطوتك التالية:**"
        ),
        color=discord.Color.from_rgb(87, 242, 135),
    )

    embed.add_field(
        name="📖 الشرح والتحميل",
        value=f"ادخل {_GUIDE} — فيه الشرح ورابط التحميل",
        inline=False,
    )
    embed.add_field(
        name="🔔 التحديثات",
        value=f"تابع {_UPDATES} لآخر الإصدارات والإعلانات",
        inline=False,
    )
    embed.add_field(
        name="⚙️ الإعدادات",
        value=f"نفّذ الإعدادات المطلوبة من {_SETTINGS} قبل التشغيل",
        inline=False,
    )

    embed.set_footer(text="Discord · تحقق فقط · لا تفعيل للكود")
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed
