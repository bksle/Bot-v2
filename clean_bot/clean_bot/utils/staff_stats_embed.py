"""Weekly staff performance embed."""

from __future__ import annotations

from datetime import datetime, timezone

import discord

from utils.staff_points import weekly_staff_stats


def build_weekly_stats_embed() -> discord.Embed:
    stats = weekly_staff_stats()
    now = datetime.now(timezone.utc)

    medals = ("🥇", "🥈", "🥉")
    ranked = sorted(stats, key=lambda s: (-s.points, s.staff_label))

    if not any(s.review_count > 0 for s in stats):
        body = "لا توجد تقييمات خلال آخر **7 أيام**."
    else:
        lines: list[str] = []
        medal_index = 0
        for stat in ranked:
            if stat.points <= 0:
                continue
            prefix = medals[medal_index] if medal_index < len(medals) else "▫️"
            lines.append(f"{prefix} **{stat.staff_label}** — **{stat.points}** نقطة")
            medal_index += 1
        body = "\n".join(lines) if lines else "لا توجد نقاط مسجّلة هذا الأسبوع."

    embed = discord.Embed(
        title="📊 إحصائيات الإدارة الأسبوعية | SQR Store",
        description=body,
        color=0x4A9EFF,
        timestamp=now,
    )
    embed.set_footer(text="SQR Store · تقرير أسبوعي")
    return embed
