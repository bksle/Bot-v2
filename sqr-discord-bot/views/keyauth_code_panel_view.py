"""System 2: persistent panel — button opens modal, checks key and grants role (no activation)."""

from __future__ import annotations

import logging
from pathlib import Path

import aiohttp
import discord

from integrations.keyauth_role_grant import grant_role_for_keyauth_license

logger = logging.getLogger(__name__)

CODE_PANEL_BUTTON_CUSTOM_ID = "keyauth_code_panel_open_modal_v1"

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "tickets"
_PANEL_LOGO = _ASSETS_DIR / "logo.png"
_WHITE_BANNER = _ASSETS_DIR / "banner_white.png"
_PANEL_COLOR = 0xEEEEEE

_PING_LINE = "||@everyone|| ||@here||"


def build_code_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="💎 بوابة التحقق من الاشتراك | SQR Store",
        description=(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ **مرحباً بك في عالم SQR Store**\n"
            "تحقق من كودك واحصل على رتبة Discord — **بدون تفعيل الكود في البرنامج**.\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=_PANEL_COLOR,
    )

    embed.add_field(
        name="📋 طريقة التحقق",
        value=(
            "▫️ اضغط **تحقق من الكود**\n"
            "▫️ أدخل **كود الاشتراك** الخاص بك\n"
            "▫️ يتم التحقق ومنحك الرتبة فقط\n"
            "▫️ **التفعيل** يتم لاحقاً داخل البرنامج (OAuth)"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔒 خصوصيتك تهمنا",
        value=(
            "▫️ لا تشارك كودك مع أي شخص\n"
            "▫️ الكود مرتبط بحسابك داخل السيرفر\n"
            "▫️ للمساعدة تواصل مع فريق الإدارة"
        ),
        inline=False,
    )

    embed.set_footer(text="SQR Store · Discord فقط · لا تفعيل للكود")
    embed.timestamp = discord.utils.utcnow()
    return embed


def _discord_file(path: Path) -> discord.File:
    return discord.File(path, filename=path.name)


async def send_code_panel_sequence(
    channel: discord.TextChannel,
    *,
    panel_embed: discord.Embed,
    panel_view: discord.ui.View,
) -> bool:
    """logo → white banner → mention + panel → white banner."""
    logo = _PANEL_LOGO if _PANEL_LOGO.is_file() else None
    banner = _WHITE_BANNER if _WHITE_BANNER.is_file() else None

    try:
        if logo is not None:
            await channel.send(file=_discord_file(logo))
        else:
            logger.warning("Code panel logo missing at %s", _PANEL_LOGO)

        if banner is not None:
            await channel.send(file=_discord_file(banner))
        else:
            logger.warning("Code panel white banner missing at %s", _WHITE_BANNER)

        await channel.send(
            content=_PING_LINE,
            embed=panel_embed,
            view=panel_view,
        )

        if banner is not None:
            await channel.send(file=_discord_file(banner))

        return True
    except discord.HTTPException:
        logger.exception("Failed to post code panel in %s", channel.id)
        return False


class KeyAuthLicenseModal(discord.ui.Modal, title="💎 إدخال كود الاشتراك"):
    key_input = discord.ui.TextInput(
        label="كود الاشتراك",
        placeholder="الصق الكود هنا — للتحقق ومنح الرتبة فقط…",
        style=discord.TextStyle.short,
        min_length=1,
        max_length=70,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "استخدم هذا النموذج داخل السيرفر.",
                ephemeral=True,
            )
            return

        key = str(self.key_input.value).strip()
        await interaction.response.defer(ephemeral=True)

        try:
            async with aiohttp.ClientSession() as session:
                embed = await grant_role_for_keyauth_license(
                    session,
                    guild=interaction.guild,
                    member=interaction.user,
                    key=key,
                )
        except Exception:
            logger.exception("Unexpected error in KeyAuth modal submit")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ خطأ",
                    description="حدث خطأ غير متوقع. حاول لاحقاً أو راسل الإدارة.",
                    color=discord.Color.dark_red(),
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(embed=embed, ephemeral=True)


class KeyAuthCodePanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="تحقق من الكود",
        emoji="💎",
        style=discord.ButtonStyle.secondary,
        custom_id=CODE_PANEL_BUTTON_CUSTOM_ID,
    )
    async def open_key_modal(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(KeyAuthLicenseModal())
