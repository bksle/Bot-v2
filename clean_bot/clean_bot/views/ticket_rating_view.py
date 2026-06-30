"""In-ticket staff rating UI: pick admin, stars (1-3), review, award points."""

from __future__ import annotations

import logging

import discord

from config.staff_ratings import RATING_STAFF, resolve_staff_member, staff_rating_entry
from config.tickets import (
    option_value_for_channel,
    ticket_color_for_channel_or_option,
)
from utils.staff_points import record_staff_rating, star_label
from utils.ticket_close import close_ticket_channel
from utils.ticket_reviews import post_ticket_review, product_label_for_ticket

logger = logging.getLogger(__name__)


class TicketReviewModal(discord.ui.Modal, title="تقييم الإدارة | SQR Store"):
    review_message = discord.ui.TextInput(
        label="اكتب تقييمك هنا",
        style=discord.TextStyle.paragraph,
        placeholder="شاركنا تجربتك مع الإدارة…",
        required=True,
        min_length=5,
        max_length=1000,
    )

    def __init__(
        self,
        *,
        opener_id: int,
        admin_key: str,
        admin_label: str,
        stars: int,
        product_label: str,
        ticket_channel: discord.TextChannel,
        parent_view: TicketRatingView,
    ) -> None:
        super().__init__(timeout=600)
        self.opener_id = opener_id
        self.admin_key = admin_key
        self.admin_label = admin_label
        self.stars = stars
        self.product_label = product_label
        self.ticket_channel = ticket_channel
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.opener_id:
            await interaction.response.send_message(
                "فقط صاحب التذكرة يمكنه إرسال التقييم.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("هذا التقييم متاح داخل السيرفر فقط.", ephemeral=True)
            return

        entry = staff_rating_entry(self.admin_key)
        admin: discord.Member | discord.User | None = None
        if entry is not None:
            admin = await resolve_staff_member(guild, entry)

        review_text = str(self.review_message.value).strip()
        points_awarded = record_staff_rating(
            staff_key=self.admin_key,
            stars=self.stars,
            customer_id=interaction.user.id,
            review_text=review_text,
            product_label=self.product_label,
        )

        posted = await post_ticket_review(
            guild=guild,
            customer=interaction.user,
            admin=admin,
            admin_label=self.admin_label,
            product_label=self.product_label,
            review_text=review_text,
            ticket_channel=self.ticket_channel,
            option_value=self.parent_view.option_value,
            stars=self.stars,
            points_awarded=points_awarded,
        )

        if not posted:
            await interaction.response.send_message(
                "تعذّر نشر التقييم حالياً. يرجى المحاولة لاحقاً أو التواصل مع الإدارة.",
                ephemeral=True,
            )
            return

        self.parent_view.mark_completed()
        for child in self.parent_view.children:
            child.disabled = True

        notify_cog = interaction.client.get_cog("TicketNotifications")
        if notify_cog is not None:
            state = notify_cog._state_for(self.ticket_channel.id)
            state.rating_completed = True

        points_note = (
            f"حصل **{self.admin_label}** على **{points_awarded}** نقطة."
            if points_awarded > 0
            else f"تقييم **{star_label(self.stars)}** — لم تُمنح نقاط."
        )

        await interaction.response.send_message(
            f"✅ شكراً لك! تم إرسال تقييمك ({star_label(self.stars)}).\n{points_note}\n"
            "سيتم إغلاق التذكرة الآن.",
            ephemeral=True,
        )

        if self.parent_view.rating_message_id is not None:
            try:
                rating_message = await self.ticket_channel.fetch_message(
                    self.parent_view.rating_message_id,
                )
                await rating_message.edit(view=self.parent_view)
            except discord.HTTPException:
                logger.exception(
                    "Failed to disable rating view on message %s",
                    self.parent_view.rating_message_id,
                )

        try:
            await self.ticket_channel.send(
                content=interaction.user.mention,
                embed=discord.Embed(
                    title="✅ تم استلام تقييمك",
                    description=(
                        f"شكراً لمشاركتنا رأيك — **{star_label(self.stars)}**\n"
                        f"{points_note}\n"
                        "سيتم **إغلاق التذكرة** تلقائياً خلال لحظات."
                    ),
                    color=ticket_color_for_channel_or_option(
                        self.ticket_channel,
                        self.parent_view.option_value,
                    ),
                ),
            )
        except discord.HTTPException:
            logger.exception("Failed to confirm rating in ticket %s", self.ticket_channel.id)

        deleted, status = await close_ticket_channel(
            bot=interaction.client,
            channel=self.ticket_channel,
            opener_id=self.opener_id,
            closed_by=interaction.user,
            close_reason="Ticket closed after customer rating",
        )
        if not deleted:
            logger.warning(
                "Auto-close after rating failed in %s: %s",
                self.ticket_channel.id,
                status,
            )


class TicketStarRatingView(discord.ui.View):
    """Choose 1-3 stars after picking staff."""

    def __init__(
        self,
        *,
        opener_id: int,
        admin_key: str,
        admin_label: str,
        product_label: str,
        ticket_channel: discord.TextChannel,
        parent_view: TicketRatingView,
    ) -> None:
        super().__init__(timeout=600)
        self.opener_id = opener_id
        self.admin_key = admin_key
        self.admin_label = admin_label
        self.product_label = product_label
        self.ticket_channel = ticket_channel
        self.parent_view = parent_view

    async def _pick_stars(self, interaction: discord.Interaction, stars: int) -> None:
        if self.parent_view.completed:
            await interaction.response.send_message("تم إرسال التقييم مسبقاً.", ephemeral=True)
            return
        if interaction.user.id != self.opener_id:
            await interaction.response.send_message(
                "فقط صاحب التذكرة يمكنه التقييم.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            TicketReviewModal(
                opener_id=self.opener_id,
                admin_key=self.admin_key,
                admin_label=self.admin_label,
                stars=stars,
                product_label=self.product_label,
                ticket_channel=self.ticket_channel,
                parent_view=self.parent_view,
            )
        )

    @discord.ui.button(label="⭐ سيء", style=discord.ButtonStyle.danger, row=0)
    async def one_star(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._pick_stars(interaction, 1)

    @discord.ui.button(label="⭐⭐ جيد", style=discord.ButtonStyle.secondary, row=0)
    async def two_stars(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._pick_stars(interaction, 2)

    @discord.ui.button(label="⭐⭐⭐ ممتاز", style=discord.ButtonStyle.success, row=0)
    async def three_stars(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._pick_stars(interaction, 3)


class TicketRatingView(discord.ui.View):
    """Per-ticket rating: staff select → stars → review text."""

    def __init__(
        self,
        *,
        opener_id: int,
        ticket_channel: discord.TextChannel,
        product_label: str,
    ) -> None:
        super().__init__(timeout=None)
        self.opener_id = opener_id
        self.ticket_channel = ticket_channel
        self.product_label = product_label
        self.option_value = option_value_for_channel(ticket_channel)
        self.completed = False
        self.rating_message_id: int | None = None

        options = [
            discord.SelectOption(
                label=entry.label,
                value=entry.key,
                description="فريق الإدارة — SQR Store",
            )
            for entry in RATING_STAFF
        ]

        select = discord.ui.Select(
            placeholder="اختر الإداري الذي قام بمساعدتك…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"ticket_rating_admin_{ticket_channel.id}",
        )
        select.callback = self._on_admin_selected
        self.add_item(select)

    def mark_completed(self) -> None:
        self.completed = True

    async def _on_admin_selected(self, interaction: discord.Interaction) -> None:
        if self.completed:
            await interaction.response.send_message("تم إرسال التقييم مسبقاً.", ephemeral=True)
            return

        if interaction.user.id != self.opener_id:
            await interaction.response.send_message(
                "فقط صاحب التذكرة يمكنه تقييم الإدارة.",
                ephemeral=True,
            )
            return

        values = interaction.data.get("values", [])
        if not values:
            await interaction.response.send_message("يرجى اختيار إداري.", ephemeral=True)
            return

        admin_key = str(values[0])
        entry = staff_rating_entry(admin_key)
        if entry is None:
            await interaction.response.send_message("خيار غير صالح.", ephemeral=True)
            return

        star_view = TicketStarRatingView(
            opener_id=self.opener_id,
            admin_key=entry.key,
            admin_label=entry.label,
            product_label=self.product_label,
            ticket_channel=self.ticket_channel,
            parent_view=self,
        )

        embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else None
        if embed is not None:
            embed = embed.copy()
            embed.colour = discord.Colour(
                ticket_color_for_channel_or_option(self.ticket_channel, self.option_value)
            )
            embed.description = (
                f"**الإداري:** {entry.label}\n\n"
                "اختر عدد النجوم لتقييم تجربتك:\n"
                "⭐ سيء (بدون نقاط)　|　⭐⭐ جيد (نقطة)　|　⭐⭐⭐ ممتاز (نقطتان)\n\n"
                "بعدها اكتب تقييمك في النافذة التي ستظهر."
            )

        await interaction.response.edit_message(embed=embed, view=star_view)


async def build_ticket_rating_view(
    *,
    opener_id: int,
    ticket_channel: discord.TextChannel,
    fallback_members: list[discord.Member] | None = None,
) -> TicketRatingView:
    del fallback_members
    return TicketRatingView(
        opener_id=opener_id,
        ticket_channel=ticket_channel,
        product_label=product_label_for_ticket(ticket_channel),
    )
