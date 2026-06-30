"""HTTP ingest for Auto Snap crack honeypot traps → Discord staff alerts."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import aiohttp
from aiohttp import web
import discord
from discord.ext import commands

from config.crack_alerts import (
    get_alert_channel_id,
    get_trap_listen_host,
    get_trap_listen_port,
    get_trap_secret,
    verify_trap_signature,
)

logger = logging.getLogger(__name__)


class CrackAlertCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._runner: web.AppRunner | None = None
        self._site: web.BaseSite | None = None

    async def cog_load(self) -> None:
        channel_id = get_alert_channel_id()
        if channel_id is None:
            logger.warning(
                "CRACK_ALERT_CHANNEL_ID not set — crack trap HTTP listener disabled."
            )
            return

        app = web.Application()
        app.router.add_post("/v1/trap", self._handle_trap)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        host = get_trap_listen_host()
        port = get_trap_listen_port()
        self._site = web.TCPSite(self._runner, host, port)
        await self._site.start()
        logger.info("Crack trap listener on http://%s:%s/v1/trap", host, port)

    async def cog_unload(self) -> None:
        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _handle_trap(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except (aiohttp.ContentTypeError, json.JSONDecodeError, ValueError):
            return web.Response(status=400, text="bad json")

        if not isinstance(data, dict):
            return web.Response(status=400, text="bad payload")

        signature = str(data.pop("trap_sig", "")).strip()
        if not verify_trap_signature(data, signature):
            logger.warning("Rejected crack trap alert — bad signature.")
            return web.Response(status=403, text="forbidden")

        await self._notify_discord(data)
        return web.Response(status=204)

    async def _notify_discord(self, payload: dict) -> None:
        channel_id = get_alert_channel_id()
        if channel_id is None:
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                logger.exception("Could not resolve crack alert channel %s", channel_id)
                return

        if not isinstance(channel, discord.abc.Messageable):
            return

        trap_id = str(payload.get("trap_id", "unknown"))
        host_name = str(payload.get("host_name", "?"))
        user_name = str(payload.get("user_name", "?"))
        app_path = str(payload.get("app_path", "?"))
        hwid = str(payload.get("hwid_primary", "?"))
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        embed = discord.Embed(
            title="🪤 Crack trap triggered",
            description="Someone invoked a honeypot bypass entry point.",
            color=0xEF4444,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Trap", value=f"`{trap_id}`", inline=True)
        embed.add_field(name="User", value=f"`{user_name}`", inline=True)
        embed.add_field(name="Host", value=f"`{host_name}`", inline=True)
        embed.add_field(name="HWID", value=f"`{hwid[:48]}…`" if len(hwid) > 48 else f"`{hwid}`", inline=False)
        embed.add_field(name="Path", value=f"`{app_path}`", inline=False)
        embed.set_footer(text=f"Auto Snap • {stamp}")

        content = "@everyone محاولة كسر — تم تفعيل الفخ والمسح الذاتي على جهاز الهدف."
        try:
            await channel.send(content=content, embed=embed)
        except discord.HTTPException:
            logger.exception("Failed to post crack trap alert")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CrackAlertCog(bot))
