"""Ticket notifications, delay reminders, inactivity reviews, and rating prompts."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from config.tickets import (
    STAFF_NO_REPLY_REMINDER_SECONDS,
    TICKET_INACTIVITY_REVIEW_SECONDS,
    is_ticket_channel,
    opener_id_from_topic,
    ticket_color_for_channel,
    ticket_label_for_channel,
)
from utils.ticket_delay_store import release_delay_reminder
from utils.ticket_notifications import (
    TicketNotifyState,
    notify_customer_staff_replied,
    notify_staff_delayed_response,
)
from views.ticket_rating_view import build_ticket_rating_view

logger = logging.getLogger(__name__)


class TicketNotifications(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._state: dict[int, TicketNotifyState] = {}
        self._delay_tasks: dict[int, asyncio.Task[None]] = {}
        self._inactivity_tasks: dict[int, asyncio.Task[None]] = {}

    def _state_for(self, channel_id: int) -> TicketNotifyState:
        state = self._state.get(channel_id)
        if state is None:
            state = TicketNotifyState()
            self._state[channel_id] = state
        return state

    def cancel_ticket_tracking(self, channel_id: int) -> None:
        self._state.pop(channel_id, None)
        self._cancel_delay_task(channel_id)
        self._cancel_inactivity_task(channel_id)
        release_delay_reminder(channel_id)

    def schedule_staff_response_check(
        self,
        *,
        channel_id: int,
        opener_id: int,
        guild_id: int,
    ) -> None:
        """Start or reset the 3-minute timer waiting for a staff reply."""
        state = self._state_for(channel_id)
        if state.delay_reminder_sent:
            return

        self._cancel_delay_task(channel_id)
        state.begin_awaiting_staff_reply()

        task = asyncio.create_task(
            self._staff_delay_watch(
                channel_id=channel_id,
                opener_id=opener_id,
                guild_id=guild_id,
            ),
            name=f"ticket-delay-{channel_id}",
        )
        self._delay_tasks[channel_id] = task

    def schedule_inactivity_review(
        self,
        *,
        channel_id: int,
        opener_id: int,
        guild_id: int,
    ) -> None:
        """Start the inactivity poll loop once per ticket (no reset on every message)."""
        state = self._state_for(channel_id)
        if state.rating_prompt_sent or state.rating_completed:
            return

        existing = self._inactivity_tasks.get(channel_id)
        if existing is not None and not existing.done():
            return

        task = asyncio.create_task(
            self._inactivity_review_watch(
                channel_id=channel_id,
                opener_id=opener_id,
                guild_id=guild_id,
            ),
            name=f"ticket-inactivity-{channel_id}",
        )
        self._inactivity_tasks[channel_id] = task

    def _cancel_delay_task(self, channel_id: int) -> None:
        task = self._delay_tasks.pop(channel_id, None)
        if task is not None and not task.done():
            task.cancel()

    def _cancel_inactivity_task(self, channel_id: int) -> None:
        task = self._inactivity_tasks.pop(channel_id, None)
        if task is not None and not task.done():
            task.cancel()

    def _touch_ticket_activity(
        self,
        *,
        channel_id: int,
        opener_id: int,
        guild_id: int,
    ) -> None:
        state = self._state_for(channel_id)
        state.last_activity_at = datetime.now(timezone.utc)
        if state.rating_prompt_sent or state.rating_completed:
            return
        self.schedule_inactivity_review(
            channel_id=channel_id,
            opener_id=opener_id,
            guild_id=guild_id,
        )

    async def _staff_delay_watch(
        self,
        *,
        channel_id: int,
        opener_id: int,
        guild_id: int,
    ) -> None:
        try:
            await asyncio.sleep(STAFF_NO_REPLY_REMINDER_SECONDS)
        except asyncio.CancelledError:
            return

        state = self._state.get(channel_id)
        if state is None or not state.awaiting_staff_reply or state.delay_reminder_sent:
            return

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel) or not is_ticket_channel(channel):
            return

        state.delay_reminder_sent = True
        sent = await notify_staff_delayed_response(
            guild=guild,
            ticket_channel=channel,
            opener_id=opener_id,
        )
        if not sent:
            state.delay_reminder_sent = False
        self._delay_tasks.pop(channel_id, None)

    async def _inactivity_review_watch(
        self,
        *,
        channel_id: int,
        opener_id: int,
        guild_id: int,
    ) -> None:
        poll_seconds = 10 * 60
        try:
            while True:
                await asyncio.sleep(poll_seconds)

                state = self._state.get(channel_id)
                if state is None or state.rating_prompt_sent or state.rating_completed:
                    return

                last_activity = state.last_activity_at
                if last_activity is None:
                    continue

                now = datetime.now(timezone.utc)
                inactive_for = (now - last_activity).total_seconds()
                if inactive_for < TICKET_INACTIVITY_REVIEW_SECONDS:
                    continue

                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    return

                channel = guild.get_channel(channel_id)
                if not isinstance(channel, discord.TextChannel) or not is_ticket_channel(channel):
                    return

                await self._send_rating_prompt(
                    channel=channel,
                    opener_id=opener_id,
                    state=state,
                )
                return
        except asyncio.CancelledError:
            return
        finally:
            self._inactivity_tasks.pop(channel_id, None)

    async def trigger_rating_now(
        self,
        *,
        channel: discord.TextChannel,
        opener_id: int,
        triggered_by: discord.Member,
        claimed_by_id: int | None = None,
    ) -> bool:
        """Staff shortcut: send the rating prompt immediately (skip 24h wait)."""
        state = self._state_for(channel.id)
        if state.rating_prompt_sent or state.rating_completed:
            return False

        self._cancel_delay_task(channel.id)
        self._cancel_inactivity_task(channel.id)
        state.mark_staff_replied_to_ticket()

        fallbacks: list[discord.Member] = []
        guild = channel.guild
        if guild is not None and claimed_by_id is not None and claimed_by_id != triggered_by.id:
            claimed = guild.get_member(claimed_by_id)
            if claimed is None:
                try:
                    claimed = await guild.fetch_member(claimed_by_id)
                except (discord.NotFound, discord.HTTPException):
                    claimed = None
            if claimed is not None and not claimed.bot:
                fallbacks.append(claimed)
        fallbacks.append(triggered_by)

        await self._send_rating_prompt(
            channel=channel,
            opener_id=opener_id,
            state=state,
            staff_triggered=True,
            triggered_by=triggered_by,
            fallback_members=fallbacks,
        )
        return state.rating_prompt_sent

    async def _send_rating_prompt(
        self,
        *,
        channel: discord.TextChannel,
        opener_id: int,
        state: TicketNotifyState,
        staff_triggered: bool = False,
        triggered_by: discord.Member | None = None,
        fallback_members: list[discord.Member] | None = None,
    ) -> None:
        rating_view = await build_ticket_rating_view(
            opener_id=opener_id,
            ticket_channel=channel,
            fallback_members=fallback_members,
        )

        product_label = ticket_label_for_channel(channel)
        embed_color = ticket_color_for_channel(channel)
        if staff_triggered and triggered_by is not None:
            description = (
                f"أنهت الإدارة تذكرتك في قسم **{product_label}** "
                f"بواسطة {triggered_by.mention}.\n\n"
                "نود معرفة رأيك في خدمتنا:\n"
                "1️⃣ اختر **الإداري** الذي قام بمساعدتك.\n"
                "2️⃣ اختر **النجوم** (⭐ إلى ⭐⭐⭐).\n"
                "3️⃣ اكتب **تقييمك** في النافذة.\n\n"
                "⭐⭐⭐ = نقطتان　|　⭐⭐ = نقطة　|　⭐ = بدون نقاط"
            )
        else:
            description = (
                f"مرّ **24 ساعة** دون أي نشاط في تذكرتك بقسم **{product_label}**.\n\n"
                "نود معرفة رأيك في خدمتنا:\n"
                "1️⃣ اختر **الإداري** الذي قام بمساعدتك.\n"
                "2️⃣ اختر **النجوم** (⭐ إلى ⭐⭐⭐).\n"
                "3️⃣ اكتب **تقييمك** في النافذة.\n\n"
                "⭐⭐⭐ = نقطتان　|　⭐⭐ = نقطة　|　⭐ = بدون نقاط"
            )

        embed = discord.Embed(
            title="⭐ تقييم تجربتك مع الإدارة | SQR Store",
            description=description,
            color=embed_color,
        )
        embed.set_footer(text="متاح لصاحب التذكرة فقط")

        try:
            rating_message = await channel.send(
                content=f"<@{opener_id}>",
                embed=embed,
                view=rating_view,
            )
            rating_view.rating_message_id = rating_message.id
            state.rating_prompt_sent = True
            self._cancel_inactivity_task(channel.id)
        except discord.HTTPException:
            logger.exception("Failed to send rating prompt in ticket %s", channel.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is None:
            return
        channel = message.channel
        if not isinstance(channel, discord.TextChannel):
            return
        if not is_ticket_channel(channel):
            return

        opener_id = opener_id_from_topic(channel.topic)
        if opener_id is None:
            opener_id = self._opener_id_from_overwrites(channel)
        if opener_id is None:
            return

        author_id = message.author.id
        state = self._state_for(channel.id)
        now = datetime.now(timezone.utc)

        self._touch_ticket_activity(
            channel_id=channel.id,
            opener_id=opener_id,
            guild_id=message.guild.id,
        )

        if author_id == opener_id:
            state.mark_customer_replied()
            self.schedule_staff_response_check(
                channel_id=channel.id,
                opener_id=opener_id,
                guild_id=message.guild.id,
            )
            return

        state.mark_staff_replied_to_ticket()
        if channel.id in self._delay_tasks:
            release_delay_reminder(channel.id)
            self._cancel_delay_task(channel.id)

        if not state.should_notify_staff_reply(now):
            return

        sent = await notify_customer_staff_replied(
            bot=self.bot,
            ticket_channel=channel,
            opener_id=opener_id,
        )
        if sent:
            state.mark_staff_notified(now)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        self.cancel_ticket_tracking(channel.id)

    @staticmethod
    def _opener_id_from_overwrites(channel: discord.TextChannel) -> int | None:
        """Fallback for tickets created before topic metadata was added."""
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketNotifications(bot))
