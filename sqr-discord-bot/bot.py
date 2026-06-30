"""
discord.py 2.x entrypoint: application commands (slash), extension loading,
and persistent UI views. Intents are explicit for guild + member resolution.
"""

from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from config.staff_stats import get_stats_guild_id
from views.high_end_tickets_view import HighEndTicketSetupView
from views.ticket_collector_view import TicketCollectorView
from views.service_ticket_panel import ALL_SERVICE_OPTIONS, ServiceTicketPanelView
from views.setup_view import SetupSelectView
from views.keyauth_code_panel_view import KeyAuthCodePanelView
from views.verification_pledge_view import VerificationPledgeView
from utils.instance_lock import acquire_bot_instance_lock

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")


def build_intents() -> discord.Intents:
    """Intents used by this bot (slash commands + guild tickets / members)."""
    intents = discord.Intents.default()
    # Requires enabling **Server Members Intent** in the Discord Developer Portal.
    # Set DISCORD_MEMBERS_INTENT=1 in .env after enabling, or the bot will connect without it.
    raw = os.environ.get("DISCORD_MEMBERS_INTENT", "0").strip().lower()
    intents.members = raw in ("1", "true", "yes", "on")
    # Required to read subscription codes pasted in ticket chat.
    raw_content = os.environ.get("DISCORD_MESSAGE_CONTENT_INTENT", "1").strip().lower()
    intents.message_content = raw_content in ("1", "true", "yes", "on")
    return intents


class SetupBot(commands.Bot):
    """commands.Bot exposes ``tree`` for app_commands registration via cogs."""

    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=build_intents())

    async def setup_hook(self) -> None:
        self.add_view(SetupSelectView())
        self.add_view(HighEndTicketSetupView())
        self.add_view(TicketCollectorView())
        for option_value in ALL_SERVICE_OPTIONS:
            self.add_view(ServiceTicketPanelView(option_value))
        self.add_view(VerificationPledgeView())
        self.add_view(KeyAuthCodePanelView())
        extensions = (
            "cogs.setup",
            "cogs.license_key",
            "cogs.keyauth_hwid",
            "cogs.keyauth_license_time",
            "cogs.verification",
            "cogs.code_panel",
            "cogs.color_aim_guide",
            "cogs.ow2_keys",
            "cogs.ticket_system",
            "cogs.ticket_notifications",
            "cogs.ticket_code_watch",
            "cogs.welcome",
            "cogs.staff_stats",
            "cogs.crack_alerts",
        )
        await asyncio.gather(*(self.load_extension(name) for name in extensions))
        sync_commands = os.environ.get("DISCORD_SYNC_COMMANDS", "0").strip().lower()
        if sync_commands not in ("1", "true", "yes", "on"):
            logger.info("Skipping slash command sync (set DISCORD_SYNC_COMMANDS=1 to sync)")
            return
        guild_id = get_stats_guild_id()
        if guild_id is not None:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d guild command(s) for %s", len(synced), guild_id)
        else:
            synced = await self.tree.sync()
            logger.info("Synced %d global application command(s)", len(synced))


async def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN in the environment or a .env file.")

    bot = SetupBot()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    if not os.environ.get("RAILWAY_ENVIRONMENT"):
        acquire_bot_instance_lock()
    asyncio.run(main())
