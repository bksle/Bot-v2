"""Per-service ticket panel: one button opens that service's ticket."""

from __future__ import annotations

import discord

from config.tickets import ticket_button_style_for_option, ticket_theme_emoji_for_option
from utils.display_name import stylized_ticket_display_name
from utils.ticket_embed import build_service_panel_embed
from utils.ticket_welcome import send_service_panel_sequence
from views.ticket_flow import create_private_ticket

ALL_SERVICE_OPTIONS: tuple[str, ...] = (
    "xim",
    "chairs",
    "snap",
    "tweak",
    "zen",
    "spoof",
    "iptv",
    "color_aim",
    "vendors_partners",
)


class ServiceTicketPanelView(discord.ui.View):
    """Persistent single-button panel for one service category."""

    def __init__(self, option_value: str) -> None:
        super().__init__(timeout=None)
        self.option_value = option_value
        emoji = ticket_theme_emoji_for_option(option_value)
        style = ticket_button_style_for_option(option_value)
        button = discord.ui.Button(
            label="فتح التذكرة",
            emoji=emoji,
            style=style,
            custom_id=f"service_ticket_open_{option_value}_v1",
        )
        button.callback = self._open_ticket
        self.add_item(button)

    async def _open_ticket(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "التذاكر متاحة داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        member = interaction.user
        await interaction.response.defer(ephemeral=True)
        styled = stylized_ticket_display_name(member)
        await create_private_ticket(
            interaction,
            member=member,
            option_value=self.option_value,
            styled_channel_suffix=styled,
        )


async def post_service_panel(interaction: discord.Interaction, option_value: str) -> None:
    """Admin slash: publish branded visuals + one-button panel for a service room."""
    if interaction.channel is None or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message(
            "استخدم الأمر داخل قناة نصية لروم الخدمة.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    embed = build_service_panel_embed(option_value)
    view = ServiceTicketPanelView(option_value)
    ok = await send_service_panel_sequence(
        interaction.channel,
        option_value,
        panel_embed=embed,
        panel_view=view,
    )

    if ok:
        await interaction.followup.send("✅ تم نشر لوحة التذكرة مع الصور.", ephemeral=True)
    else:
        await interaction.followup.send("❌ فشل نشر اللوحة. تحقق من صلاحيات البوت.", ephemeral=True)
