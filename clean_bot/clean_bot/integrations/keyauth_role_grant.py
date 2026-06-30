"""Read-only KeyAuth license check and Discord role grant (no app activation)."""

from __future__ import annotations

import logging
import os
import aiohttp
import discord

from config.keyauth_roles import SUBSCRIPTION_LEVEL_ROLE_IDS
from config.color_aim import color_aim_role_id, is_color_aim_role
from integrations.keyauth_client import KeyAuthError, check_license_and_level
from utils.color_aim_onboarding import build_color_aim_role_success_embed

logger = logging.getLogger(__name__)


async def grant_color_aim_role_for_member(
    *,
    guild: discord.Guild,
    member: discord.Member,
    reason: str = "COLOR・AIM ticket code",
) -> discord.Embed:
    """Grant the COLOR・AIM Discord role without KeyAuth (OW2 / pasted ticket codes)."""
    role_id = color_aim_role_id()
    role = guild.get_role(role_id)
    if role is None:
        return discord.Embed(
            title="Missing role",
            description=f"Role ID {role_id} was not found in this server.",
            color=discord.Color.dark_red(),
        )

    if role in member.roles:
        embed = build_color_aim_role_success_embed(
            member=member,
            role=role,
            code_already_used=None,
        )
        embed.title = "✅ لديك الرتبة — COLOR・AIM"
        embed.description = (
            f"{member.mention} — لديك {role.mention} مسبقاً.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "**روابط مهمة:**"
        )
        embed.color = discord.Color.blurple()
        return embed.set_footer(
            text="SQR Store · COLOR・AIM · تحقق من الكود في التذكرة"
        ).set_thumbnail(url=member.display_avatar.url)

    bot_member = guild.me
    if bot_member is None or role.position >= bot_member.top_role.position:
        return discord.Embed(
            title="Could not assign role",
            description=(
                "My highest role must be **above** the subscription role, "
                f"or I cannot grant {role.mention}. Ask an admin to fix role hierarchy."
            ),
            color=discord.Color.dark_red(),
        )

    try:
        await member.add_roles(role, reason=reason)
    except discord.Forbidden:
        return discord.Embed(
            title="Could not assign role",
            description=(
                "I lack **Manage Roles** permission, or my highest role is below "
                f"the {role.mention} role. Ask an admin to fix role hierarchy."
            ),
            color=discord.Color.dark_red(),
        )
    except discord.HTTPException as exc:
        logger.exception("add_roles failed for COLOR・AIM")
        return discord.Embed(
            title="Could not assign role",
            description=f"Discord API error: `{exc}`",
            color=discord.Color.dark_red(),
        )

    return build_color_aim_role_success_embed(
        member=member,
        role=role,
        code_already_used=None,
    )


async def grant_role_for_keyauth_license(
    session: aiohttp.ClientSession,
    *,
    guild: discord.Guild,
    member: discord.Member,
    key: str,
) -> discord.Embed:
    """
    Check ``key`` with KeyAuth (``info`` only — never activates) and add the tier role.

    Returns an embed suitable for an ephemeral reply (success or error).
    """
    sellerkey = os.environ.get("KEYAUTH_SELLER_KEY", "").strip()
    if not sellerkey:
        return discord.Embed(
            title="Misconfiguration",
            description="KEYAUTH_SELLER_KEY is not set on the bot host.",
            color=discord.Color.dark_red(),
        )

    try:
        result = await check_license_and_level(
            session,
            sellerkey=sellerkey,
            key=key,
        )
    except KeyAuthError as exc:
        return (
            discord.Embed(
                title="Verification failed",
                description=str(exc),
                color=discord.Color.from_rgb(237, 66, 69),
            ).set_footer(text="KeyAuth · تحقق فقط")
        )
    except aiohttp.ClientError as exc:
        logger.exception("KeyAuth HTTP error")
        return discord.Embed(
            title="Network error",
            description=f"Could not reach KeyAuth: `{exc}`",
            color=discord.Color.dark_red(),
        )

    role_id = SUBSCRIPTION_LEVEL_ROLE_IDS.get(result.level)
    if role_id is None:
        return (
            discord.Embed(
                title="Unsupported tier",
                description=(
                    f"This key resolved to subscription level {result.level}, "
                    "but this server only grants roles for levels 1, 2, and 3."
                ),
                color=discord.Color.orange(),
            ).set_footer(text="KeyAuth · تحقق فقط")
        )

    role = guild.get_role(role_id)
    if role is None:
        return discord.Embed(
            title="Missing role",
            description=f"Role ID {role_id} was not found in this server.",
            color=discord.Color.dark_red(),
        )

    if role in member.roles:
        if is_color_aim_role(role.id):
            embed = build_color_aim_role_success_embed(
                member=member,
                role=role,
                code_already_used=result.used,
            )
            embed.title = "✅ لديك الرتبة — COLOR・AIM"
            embed.description = (
                f"{member.mention} — لديك {role.mention} مسبقاً.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "**روابط مهمة:**"
            )
            embed.color = discord.Color.blurple()
            return embed.set_footer(
                text="KeyAuth · تحقق فقط — لم يتم تفعيل الكود"
            ).set_thumbnail(url=member.display_avatar.url)

        return (
            discord.Embed(
                title="Already unlocked",
                description=f"You already have {role.mention} (level {result.level}).",
                color=discord.Color.blurple(),
            )
            .set_footer(text="KeyAuth · تحقق فقط — لم يتم تفعيل الكود")
            .set_thumbnail(url=member.display_avatar.url)
        )

    bot_member = guild.me
    if bot_member is None or role.position >= bot_member.top_role.position:
        return discord.Embed(
            title="Could not assign role",
            description=(
                "My highest role must be **above** the subscription role, "
                f"or I cannot grant {role.mention}. Ask an admin to fix role hierarchy."
            ),
            color=discord.Color.dark_red(),
        )

    try:
        await member.add_roles(
            role,
            reason=f"KeyAuth code checked (level {result.level}, no activation)",
        )
    except discord.Forbidden:
        return discord.Embed(
            title="Could not assign role",
            description=(
                "I lack **Manage Roles** permission, or my highest role is below "
                f"the {role.mention} role. Ask an admin to fix role hierarchy."
            ),
            color=discord.Color.dark_red(),
        )
    except discord.HTTPException as exc:
        logger.exception("add_roles failed")
        return discord.Embed(
            title="Could not assign role",
            description=f"Discord API error: `{exc}`",
            color=discord.Color.dark_red(),
        )

    activation_note = (
        "الكود **لم يُفعَّل** — فعّله لاحقاً داخل البرنامج."
        if result.used is False
        else "تفعيل البرنامج يتم من داخل التطبيق فقط."
    )

    if is_color_aim_role(role.id):
        return build_color_aim_role_success_embed(
            member=member,
            role=role,
            code_already_used=result.used,
        )

    return (
        discord.Embed(
            title="✅ تم التحقق — رتبة Discord",
            description=(
                f"{member.mention} — الكود **صحيح**.\n\n"
                f"**المستوى:** {result.level}\n"
                f"**الرتبة:** {role.mention}\n\n"
                f"⚠️ {activation_note}"
            ),
            color=discord.Color.from_rgb(87, 242, 135),
        )
        .add_field(name="المستوى", value=f"**{result.level}**", inline=True)
        .add_field(name="الرتبة", value=role.mention, inline=True)
        .set_footer(text="Discord فقط · لا تفعيل للكود")
        .set_thumbnail(url=member.display_avatar.url)
    )
