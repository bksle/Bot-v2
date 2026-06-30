"""Close button for ticket channels."""

from __future__ import annotations

import discord


class TicketCloseView(discord.ui.View):
    def __init__(self, opener_id: int) -> None:
        super().__init__(timeout=None)
        self.opener_id = opener_id

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "This action only works inside a text ticket channel.",
                ephemeral=True,
            )
            return

        user = interaction.user
        if not isinstance(user, discord.Member):
            await interaction.response.send_message(
                "Could not verify your permissions.",
                ephemeral=True,
            )
            return

        allowed = (
            user.id == self.opener_id
            or user.guild_permissions.administrator
            or user.guild_permissions.manage_channels
        )
        if not allowed:
            await interaction.response.send_message(
                "You cannot close this ticket.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        await channel.delete(reason=f"Ticket closed by {user} ({user.id})")
