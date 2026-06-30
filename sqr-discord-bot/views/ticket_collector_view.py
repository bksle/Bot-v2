"""Staff button that lists all open tickets across categories."""

from __future__ import annotations

import discord

from utils.ticket_collector import build_ticket_overview_embeds, collect_open_tickets
from utils.ticket_notifications import is_ticket_staff


async def reply_with_ticket_overview(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "استخدم الزر داخل السيرفر.",
            ephemeral=True,
        )
        return

    if not isinstance(interaction.user, discord.Member) or not is_ticket_staff(interaction.user):
        await interaction.response.send_message(
            "فقط الإدارة يمكنها جمع التذاكر.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    tickets = await collect_open_tickets(interaction.guild)
    embeds = build_ticket_overview_embeds(tickets)

    await interaction.followup.send(
        content=f"✅ تم جمع **{len(tickets)}** تذكرة مفتوحة.",
        embeds=embeds[:10],
        ephemeral=True,
    )


class TicketCollectorView(discord.ui.View):
    """Persistent staff panel — ``timeout=None``."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="جمع التذاكر",
        emoji="📋",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_collector_gather_v1",
        row=0,
    )
    async def gather_tickets(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await reply_with_ticket_overview(interaction)


def build_ticket_collector_panel_embed() -> discord.Embed:
    return discord.Embed(
        title="📋 لوحة جمع التذاكر | SQR Store",
        description=(
            "اضغط الزر أدناه لعرض **كل التذاكر المفتوحة** في السيرفر\n"
            "مجمّعة حسب القسم مع حالة كل تذكرة.\n\n"
            "▫️ متاح للإدارة فقط\n"
            "▫️ يعرض روابط مباشرة لكل تذكرة"
        ),
        color=0x5865F2,
    )
