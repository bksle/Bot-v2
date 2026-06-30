"""Persistent dropdown view for the /setup ticket flow (legacy panel)."""

from __future__ import annotations

import discord

from config.setup_panel import SETUP_PANEL_OPTIONS, SETUP_SELECT_PLACEHOLDER
from utils.display_name import stylized_ticket_display_name
from views.ticket_flow import create_private_ticket


class SetupSelectView(discord.ui.View):
    """timeout=None and fixed custom_id so the view survives bot restarts."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="setup_category_dropdown",
        placeholder=SETUP_SELECT_PLACEHOLDER,
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label=opt.label[:100],
                value=opt.value,
                description=opt.description[:100],
            )
            for opt in SETUP_PANEL_OPTIONS
        ],
    )
    async def category_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select,
    ) -> None:
        value = select.values[0]

        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Tickets can only be opened inside a server.\n"
                "❌ التذاكر تُفتح داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        member = interaction.user
        await interaction.response.defer(ephemeral=True)
        styled = stylized_ticket_display_name(member)
        await create_private_ticket(
            interaction,
            member=member,
            option_value=value,
            styled_channel_suffix=styled,
        )
