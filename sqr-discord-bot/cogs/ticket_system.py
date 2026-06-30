"""Per-service ticket panel slash commands (one button per service room)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from views.service_ticket_panel import post_service_panel
from views.ticket_collector_view import (
    TicketCollectorView,
    build_ticket_collector_panel_embed,
)


def _admin_slash(func):
    func = app_commands.default_permissions(administrator=True)(func)
    func = app_commands.checks.has_permissions(administrator=True)(func)
    func = app_commands.guild_only()(func)
    return func


class TicketSystem(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @_admin_slash
    @app_commands.command(name="ticket_xim", description="نشر لوحة تذاكر XIM (زر واحد)")
    async def ticket_xim(self, interaction: discord.Interaction) -> None:
        await post_service_panel(interaction, "xim")

    @_admin_slash
    @app_commands.command(name="ticket_chairs", description="نشر لوحة تذاكر CHAIRS (زر واحد)")
    async def ticket_chairs(self, interaction: discord.Interaction) -> None:
        await post_service_panel(interaction, "chairs")

    @_admin_slash
    @app_commands.command(name="ticket_snap", description="نشر لوحة تذاكر Snap (زر واحد)")
    async def ticket_snap(self, interaction: discord.Interaction) -> None:
        await post_service_panel(interaction, "snap")

    @_admin_slash
    @app_commands.command(name="ticket_tweak", description="نشر لوحة تذاكر Tweak (زر واحد)")
    async def ticket_tweak(self, interaction: discord.Interaction) -> None:
        await post_service_panel(interaction, "tweak")

    @_admin_slash
    @app_commands.command(name="ticket_zen", description="نشر لوحة تذاكر Zen (زر واحد)")
    async def ticket_zen(self, interaction: discord.Interaction) -> None:
        await post_service_panel(interaction, "zen")

    @_admin_slash
    @app_commands.command(name="ticket_spoof", description="نشر لوحة تذاكر Spoof (زر واحد)")
    async def ticket_spoof(self, interaction: discord.Interaction) -> None:
        await post_service_panel(interaction, "spoof")

    @_admin_slash
    @app_commands.command(name="ticket_iptv", description="نشر لوحة تذاكر IPTV (زر واحد)")
    async def ticket_iptv(self, interaction: discord.Interaction) -> None:
        await post_service_panel(interaction, "iptv")

    @_admin_slash
    @app_commands.command(name="ticket_color_aim", description="نشر لوحة تذاكر COLOR・AIM (زر واحد)")
    async def ticket_color_aim(self, interaction: discord.Interaction) -> None:
        await post_service_panel(interaction, "color_aim")

    @_admin_slash
    @app_commands.command(name="ticket_vendors", description="نشر لوحة تذاكر الشراكات (زر واحد)")
    async def ticket_vendors(self, interaction: discord.Interaction) -> None:
        await post_service_panel(interaction, "vendors_partners")

    @_admin_slash
    @app_commands.command(
        name="ticket_collect_panel",
        description="نشر لوحة جمع كل التذاكر المفتوحة (للإدارة).",
    )
    async def ticket_collect_panel(self, interaction: discord.Interaction) -> None:
        if interaction.channel is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "استخدم الأمر داخل قناة نصية.",
                ephemeral=True,
            )
            return

        embed = build_ticket_collector_panel_embed()
        view = TicketCollectorView()
        await interaction.response.send_message(
            embed=embed,
            view=view,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketSystem(bot))
