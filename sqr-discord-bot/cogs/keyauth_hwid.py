"""Slash command to reset KeyAuth HWID for a license key (subscription-safe)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from integrations.keyauth_client import KeyAuthError, reset_license_hwid

logger = logging.getLogger(__name__)


def _mask_license_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}…{key[-4:]}"


def _format_expiry(raw: object) -> str:
    if raw is None or str(raw).strip() == "":
        return "—"
    try:
        ts = int(str(raw).strip())
    except ValueError:
        return str(raw)
    if ts <= 0:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _build_success_embed(
    *,
    member: discord.Member,
    result,
) -> discord.Embed:
    snap = result.subscription_snapshot
    subs = snap.get("subscriptions")
    sub_expiry = None
    if isinstance(subs, list) and subs and isinstance(subs[0], dict):
        sub_expiry = subs[0].get("expiry")

    expiry_display = _format_expiry(sub_expiry or snap.get("expiry"))

    embed = discord.Embed(
        title="✅ تم إعادة ضبط HWID",
        description=(
            f"{member.mention} — تم فك ربط الجهاز (HWID) للمفتاح.\n\n"
            "▫️ **مدة الاشتراك ما تغيّرت**\n"
            "▫️ **تاريخ الانتهاء ما تغيّر**\n"
            "▫️ تم مسح ربط الجهاز فقط (HWID)\n\n"
            "تقدر تفعّل البرنامج على جهازك الجديد."
        ),
        color=discord.Color.from_rgb(87, 242, 135),
    )
    embed.add_field(
        name="المفتاح",
        value=f"`{_mask_license_key(result.license_key)}`",
        inline=True,
    )
    embed.add_field(name="الحساب", value=f"`{result.username}`", inline=True)
    embed.add_field(name="الانتهاء (بدون تغيير)", value=expiry_display, inline=True)
    embed.set_footer(text="KeyAuth · إعادة ضبط HWID فقط · SQR Store")
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


def _build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="❌ فشل إعادة ضبط HWID",
        description=message,
        color=discord.Color.from_rgb(237, 66, 69),
    ).set_footer(text="KeyAuth · إعادة ضبط HWID فقط · SQR Store")


class KeyAuthHwidCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="reset_hwid",
        description="إعادة ضبط HWID لمفتاح (بدون تغيير مدة الاشتراك).",
    )
    @app_commands.describe(
        license_key="مفتاح KeyAuth اللي تبي تفك ربط الجهاز عنه",
    )
    async def reset_hwid(
        self,
        interaction: discord.Interaction,
        license_key: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(
                embed=_build_error_embed("استخدم الأمر داخل السيرفر."),
                ephemeral=True,
            )
            return

        sellerkey = os.environ.get("KEYAUTH_SELLER_KEY", "").strip()
        if not sellerkey:
            await interaction.followup.send(
                embed=_build_error_embed("KEYAUTH_SELLER_KEY غير مضبوط على البوت."),
                ephemeral=True,
            )
            return

        try:
            async with aiohttp.ClientSession() as session:
                result = await reset_license_hwid(
                    session,
                    sellerkey=sellerkey,
                    license_key=license_key,
                )
        except KeyAuthError as exc:
            await interaction.followup.send(
                embed=_build_error_embed(str(exc)),
                ephemeral=True,
            )
            return
        except aiohttp.ClientError:
            logger.exception("KeyAuth HTTP error in /reset_hwid")
            await interaction.followup.send(
                embed=_build_error_embed("تعذّر الاتصال بـ KeyAuth. حاول لاحقاً."),
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception("Unexpected error in /reset_hwid")
            await interaction.followup.send(
                embed=_build_error_embed("حدث خطأ غير متوقع. حاول لاحقاً."),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=_build_success_embed(member=interaction.user, result=result),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(KeyAuthHwidCog(bot))
