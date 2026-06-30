"""Inside-ticket UI: claim (staff), stop (rating), and close (transcript + delete)."""

from __future__ import annotations

import logging

import discord

from config.tickets import (
    option_value_for_category_id,
    ticket_button_style_for_option,
)
from utils.ticket_notifications import is_ticket_staff
from utils.ticket_close import close_ticket_channel
from utils.ticket_embed import build_ticket_panel_embed
from views.ticket_collector_view import reply_with_ticket_overview

logger = logging.getLogger(__name__)


def _staff(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return is_ticket_staff(interaction.user)


def _can_close_ticket(
    interaction: discord.Interaction,
    *,
    opener_id: int,
    claimed_by_id: int | None,
) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    u = interaction.user
    if u.id == opener_id:
        return True
    if claimed_by_id is not None and u.id == claimed_by_id:
        return True
    p = u.guild_permissions
    return bool(p.administrator or p.manage_channels)


def _build_ticket_embed(
    *,
    channel: discord.TextChannel,
    opener: discord.Member | None = None,
    opener_id: int | None = None,
    claimed_by: discord.Member | None = None,
    stopped: bool = False,
) -> discord.Embed:
    return build_ticket_panel_embed(
        channel=channel,
        opener=opener,
        opener_id=opener_id,
        claimed_by=claimed_by,
        stopped=stopped,
    )


class TicketInteriorView(discord.ui.View):
    """Per-ticket view (not registered globally); ``timeout=None``."""

    def __init__(
        self,
        *,
        opener_id: int,
        option_value: str | None = None,
        channel: discord.TextChannel | None = None,
        claimed_by_id: int | None = None,
        stopped: bool = False,
    ) -> None:
        super().__init__(timeout=None)
        self.opener_id = opener_id
        self.claimed_by_id = claimed_by_id
        self.stopped = stopped
        self.option_value = option_value
        if self.option_value is None and channel is not None and channel.category_id is not None:
            self.option_value = option_value_for_category_id(channel.category_id)
        self._apply_category_button_theme()
        self._sync_button_states()

    _BUTTON_EMOJIS: dict[str, str] = {
        "ticket_interior_claim": "📥",
        "ticket_interior_stop": "⭐",
        "ticket_interior_close": "🔒",
        "ticket_interior_gather": "📋",
    }

    def _apply_category_button_theme(self) -> None:
        """Match all buttons to the ticket category color; keep action icons."""
        style = (
            ticket_button_style_for_option(self.option_value)
            if self.option_value is not None
            else discord.ButtonStyle.primary
        )
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            child.style = style
            emoji = self._BUTTON_EMOJIS.get(child.custom_id or "")
            if emoji:
                child.emoji = emoji

    def _sync_button_states(self) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "ticket_interior_claim":
                child.disabled = self.claimed_by_id is not None
            if child.custom_id == "ticket_interior_stop":
                child.disabled = self.stopped

    @discord.ui.button(
        label="استلام",
        emoji="📥",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_interior_claim",
        row=0,
    )
    async def claim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if self.claimed_by_id is not None:
            await interaction.response.send_message(
                "تم استلام هذه التذكرة مسبقاً.",
                ephemeral=True,
            )
            return

        if not _staff(interaction) or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "فقط الإدارة يمكنها استلام التذكرة.",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "هذا الزر يعمل داخل قناة التذكرة فقط.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        opener = guild.get_member(self.opener_id) if guild else None

        new_view = TicketInteriorView(
            opener_id=self.opener_id,
            option_value=self.option_value,
            channel=channel,
            claimed_by_id=interaction.user.id,
            stopped=self.stopped,
        )
        embed = _build_ticket_embed(
            channel=channel,
            opener=opener,
            opener_id=self.opener_id,
            claimed_by=interaction.user,
            stopped=self.stopped,
        )
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(
        label="إيقاف",
        emoji="⭐",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_interior_stop",
        row=0,
    )
    async def stop_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "هذا الزر يعمل داخل قناة التذكرة فقط.",
                ephemeral=True,
            )
            return

        if not _staff(interaction) or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "فقط الإدارة يمكنها إيقاف التذكرة.",
                ephemeral=True,
            )
            return

        if self.stopped:
            await interaction.response.send_message(
                "تم إيقاف التذكرة وإرسال التقييم مسبقاً.",
                ephemeral=True,
            )
            return

        notify_cog = interaction.client.get_cog("TicketNotifications")
        if notify_cog is None:
            await interaction.response.send_message(
                "نظام التقييم غير متاح حالياً.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        sent = await notify_cog.trigger_rating_now(
            channel=channel,
            opener_id=self.opener_id,
            triggered_by=interaction.user,
            claimed_by_id=self.claimed_by_id,
        )

        if not sent:
            await interaction.followup.send(
                "تعذّر إرسال التقييم. قد يكون أُرسل مسبقاً — تحقق من القناة.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        opener = guild.get_member(self.opener_id) if guild else None
        claimed = (
            guild.get_member(self.claimed_by_id)
            if guild and self.claimed_by_id is not None
            else None
        )
        new_view = TicketInteriorView(
            opener_id=self.opener_id,
            option_value=self.option_value,
            channel=channel,
            claimed_by_id=self.claimed_by_id,
            stopped=True,
        )
        embed = _build_ticket_embed(
            channel=channel,
            opener=opener,
            opener_id=self.opener_id,
            claimed_by=claimed,
            stopped=True,
        )

        if interaction.message is not None:
            try:
                await interaction.message.edit(embed=embed, view=new_view)
            except discord.HTTPException:
                logger.exception("Failed to update ticket interior view after stop")

        await interaction.followup.send(
            "✅ تم إيقاف التذكرة وإرسال نموذج التقييم للعميل.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="إغلاق",
        emoji="🔒",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_interior_close",
        row=0,
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "هذا الزر يعمل داخل قناة التذكرة فقط.",
                ephemeral=True,
            )
            return

        if not _can_close_ticket(
            interaction,
            opener_id=self.opener_id,
            claimed_by_id=self.claimed_by_id,
        ):
            await interaction.response.send_message(
                "لا يمكنك إغلاق هذه التذكرة.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        deleted, status = await close_ticket_channel(
            bot=interaction.client,
            channel=channel,
            opener_id=self.opener_id,
            closed_by=interaction.user,
            close_reason="Ticket closed manually",
        )
        await interaction.followup.send(status, ephemeral=True)
        if not deleted:
            return

    @discord.ui.button(
        label="جمع التذاكر",
        emoji="📋",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_interior_gather",
        row=1,
    )
    async def gather_all_tickets(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await reply_with_ticket_overview(interaction)
