"""Auto-detect COLOR・AIM subscription codes pasted in ticket chat."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands

from config.color_aim import color_aim_subscription_level, is_color_aim_role
from config.keyauth_roles import SUBSCRIPTION_LEVEL_ROLE_IDS
from config.tickets import (
    category_ids_for_option,
    opener_id_from_topic,
)
from integrations.keyauth_client import KeyAuthError, check_license_and_level
from integrations.keyauth_role_grant import (
    grant_color_aim_role_for_member,
    grant_role_for_keyauth_license,
)
from utils.color_aim_onboarding import (
    build_color_aim_ticket_guide_embed,
    is_color_aim_success_embed,
)
from utils.ticket_code_detect import (
    extract_license_candidates,
    is_ow2_color_tracking_key,
)
from utils.ticket_notifications import is_ticket_staff

logger = logging.getLogger(__name__)

_STATE_FLUSH_SECONDS = 45
_KEYAUTH_TIMEOUT_SECONDS = 10
_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "ticket_code_scan.json"

_COLOR_AIM_CATEGORY_IDS: frozenset[int] | None = None


def _color_aim_category_ids() -> frozenset[int]:
    global _COLOR_AIM_CATEGORY_IDS
    if _COLOR_AIM_CATEGORY_IDS is None:
        _COLOR_AIM_CATEGORY_IDS = frozenset(category_ids_for_option("color_aim"))
    return _COLOR_AIM_CATEGORY_IDS


def _load_state() -> dict:
    if not _STATE_PATH.is_file():
        return {"channels": {}, "keys_tried": {}}
    try:
        data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"channels": {}, "keys_tried": {}}
    except (OSError, json.JSONDecodeError):
        return {"channels": {}, "keys_tried": {}}


def _save_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        _STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        logger.exception("Failed to save ticket code scan state")


def _resolve_opener_id(channel: discord.TextChannel) -> int | None:
    opener_id = opener_id_from_topic(channel.topic)
    if opener_id is not None:
        return opener_id
    guild = channel.guild
    if guild is None:
        return None
    bot_id = guild.me.id if guild.me else None
    for target, overwrite in channel.overwrites.items():
        if not isinstance(target, discord.Member):
            continue
        if target.bot:
            continue
        if bot_id is not None and target.id == bot_id:
            continue
        if overwrite.send_messages is True:
            return target.id
    return None


class TicketCodeWatch(commands.Cog):
    """Grant COLOR・AIM role when the customer pastes a valid subscription code in their ticket."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._state = _load_state()
        self._session: aiohttp.ClientSession | None = None
        self._state_dirty = False
        self._flush_task: asyncio.Task[None] | None = None
        self._inflight_messages: set[int] = set()

    async def cog_load(self) -> None:
        timeout = aiohttp.ClientTimeout(total=_KEYAUTH_TIMEOUT_SECONDS)
        self._session = aiohttp.ClientSession(timeout=timeout)

    async def cog_unload(self) -> None:
        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
        if self._state_dirty:
            _save_state(self._state)
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _is_color_aim_ticket(self, channel: discord.TextChannel) -> bool:
        category_id = channel.category_id
        return category_id is not None and category_id in _color_aim_category_ids()

    def _channel_cursor(self, channel_id: int) -> int:
        channels = self._state.setdefault("channels", {})
        raw = channels.get(str(channel_id), 0)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    def _set_channel_cursor(self, channel_id: int, message_id: int) -> None:
        channels = self._state.setdefault("channels", {})
        channels[str(channel_id)] = message_id
        self._schedule_state_flush()

    def _mark_key_tried(self, channel_id: int, key: str) -> None:
        tried = self._state.setdefault("keys_tried", {})
        tried[f"{channel_id}:{key}"] = True
        self._schedule_state_flush()

    def _was_key_tried(self, channel_id: int, key: str) -> bool:
        tried = self._state.get("keys_tried", {})
        return bool(tried.get(f"{channel_id}:{key}"))

    def _schedule_state_flush(self) -> None:
        self._state_dirty = True
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(
                self._flush_state_later(),
                name="ticket-code-state-flush",
            )

    async def _flush_state_later(self) -> None:
        try:
            await asyncio.sleep(_STATE_FLUSH_SECONDS)
            if self._state_dirty:
                _save_state(self._state)
                self._state_dirty = False
        except asyncio.CancelledError:
            return

    def _drop_channel_state(self, channel_id: int) -> None:
        channels = self._state.get("channels", {})
        channels.pop(str(channel_id), None)
        tried = self._state.get("keys_tried", {})
        prefix = f"{channel_id}:"
        for key in list(tried.keys()):
            if key.startswith(prefix):
                tried.pop(key, None)
        self._schedule_state_flush()

    async def _post_onboarding(
        self,
        *,
        channel: discord.TextChannel,
        member: discord.Member,
        message: discord.Message,
        embed: discord.Embed,
    ) -> bool:
        try:
            await channel.send(
                content=member.mention,
                embed=embed,
                reference=message,
                mention_author=False,
            )
            if is_color_aim_success_embed(embed):
                await channel.send(embed=build_color_aim_ticket_guide_embed())
            return True
        except discord.HTTPException:
            logger.exception("Failed to post auto-grant reply in %s", channel.id)
            return False

    async def _try_grant_ow2_key(
        self,
        *,
        channel: discord.TextChannel,
        member: discord.Member,
        message: discord.Message,
        key: str,
    ) -> bool:
        guild = channel.guild
        if guild is None:
            return False

        embed = await grant_color_aim_role_for_member(
            guild=guild,
            member=member,
            reason=f"OW2 ticket code {key}",
        )
        posted = await self._post_onboarding(
            channel=channel,
            member=member,
            message=message,
            embed=embed,
        )
        if posted:
            logger.info(
                "Auto-granted COLOR・AIM from OW2 key for %s in ticket %s",
                member.id,
                channel.id,
            )
        return posted

    async def _try_grant_keyauth_key(
        self,
        *,
        channel: discord.TextChannel,
        member: discord.Member,
        message: discord.Message,
        key: str,
        target_level: int,
    ) -> bool:
        guild = channel.guild
        if guild is None or self._session is None:
            return False

        sellerkey = os.environ.get("KEYAUTH_SELLER_KEY", "").strip()
        if not sellerkey:
            logger.warning("KEYAUTH_SELLER_KEY missing — cannot verify KeyAuth codes")
            return False

        try:
            result = await check_license_and_level(
                self._session,
                sellerkey=sellerkey,
                key=key,
                timeout_seconds=_KEYAUTH_TIMEOUT_SECONDS,
            )
        except KeyAuthError:
            return False
        except aiohttp.ClientError:
            logger.exception("KeyAuth error while scanning ticket %s", channel.id)
            return False

        role_id = SUBSCRIPTION_LEVEL_ROLE_IDS.get(result.level)
        if role_id is None or not is_color_aim_role(role_id):
            return False
        if result.level != target_level:
            return False

        embed = await grant_role_for_keyauth_license(
            self._session,
            guild=guild,
            member=member,
            key=key,
        )
        posted = await self._post_onboarding(
            channel=channel,
            member=member,
            message=message,
            embed=embed,
        )
        if posted:
            logger.info(
                "Auto-granted COLOR・AIM role to %s in ticket %s from KeyAuth code",
                member.id,
                channel.id,
            )
        return posted

    async def _try_grant_from_message(
        self,
        *,
        channel: discord.TextChannel,
        message: discord.Message,
    ) -> bool:
        if message.author.bot:
            return False
        if not self._is_color_aim_ticket(channel):
            return False
        if not isinstance(message.author, discord.Member):
            return False
        if is_ticket_staff(message.author):
            return False

        opener_id = _resolve_opener_id(channel)
        if opener_id is None or message.author.id != opener_id:
            logger.debug(
                "Skip ticket code in %s — opener=%s author=%s",
                channel.id,
                opener_id,
                message.author.id,
            )
            return False

        content = message.content or ""
        if not content.strip():
            logger.debug(
                "Empty message content in ticket %s — enable Message Content Intent",
                channel.id,
            )
            return False

        candidates = extract_license_candidates(content)
        if not candidates:
            return False

        member = message.author
        target_level = color_aim_subscription_level()

        for key in candidates:
            if self._was_key_tried(channel.id, key):
                continue

            if is_ow2_color_tracking_key(key):
                self._mark_key_tried(channel.id, key)
                if await self._try_grant_ow2_key(
                    channel=channel,
                    member=member,
                    message=message,
                    key=key,
                ):
                    return True
                continue

            self._mark_key_tried(channel.id, key)
            if await self._try_grant_keyauth_key(
                channel=channel,
                member=member,
                message=message,
                key=key,
                target_level=target_level,
            ):
                return True

        return False

    async def _handle_message(self, message: discord.Message) -> None:
        if message.id in self._inflight_messages:
            return
        self._inflight_messages.add(message.id)
        try:
            channel = message.channel
            if not isinstance(channel, discord.TextChannel):
                return
            if message.id > self._channel_cursor(channel.id):
                self._set_channel_cursor(channel.id, message.id)
            await self._try_grant_from_message(channel=channel, message=message)
        finally:
            self._inflight_messages.discard(message.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        channel = message.channel
        if not isinstance(channel, discord.TextChannel):
            return
        if not self._is_color_aim_ticket(channel):
            return

        asyncio.create_task(
            self._handle_message(message),
            name=f"ticket-code-{message.id}",
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        if isinstance(channel, discord.TextChannel) and self._is_color_aim_ticket(channel):
            self._drop_channel_state(channel.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketCodeWatch(bot))
