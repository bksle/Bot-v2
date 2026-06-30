"""Welcome embed for new server members."""

from __future__ import annotations

import discord

_WELCOME_COLOR = 0x4A9EFF


def build_member_welcome_embed(member: discord.Member) -> discord.Embed:
    member_count = member.guild.member_count or 0

    embed = discord.Embed(
        title="🌹 أهلاً بك في SQR Store",
        description=(
            f"{member.mention}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ **نورت السيرفر يا رهيب!** حياك الله في **SQR Store**.\n"
            "نتمنى لك تجربة ممتعة — تفضّل بالتجوّل واكتشف أقسامنا وخدماتنا.\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✨ **Welcome, {member.display_name}!**\n"
            "Glad to have you at **SQR Store** — enjoy your stay!"
        ),
        color=_WELCOME_COLOR,
    )

    embed.add_field(
        name="📌 ابدأ من هنا",
        value=(
            "▫️ اقرأ القوانين والتعليمات\n"
            "▫️ فعّل اشتراكك من قسم التفعيل\n"
            "▫️ افتح تذكرة من قسم خدمتك عند الحاجة"
        ),
        inline=False,
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"SQR Store · العضو رقم {member_count}")
    embed.timestamp = discord.utils.utcnow()
    return embed
