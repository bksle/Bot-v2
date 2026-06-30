"""Staff slash command to extend KeyAuth license time."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from enum import Enum

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from config.keyauth_bulk import ALL_PAID_USERS, select_bulk_targets
from integrations.keyauth_client import (
    KeyAuthError,
    bulk_extend_license_time,
    extend_license_time,
    fetch_all_license_rows,
)
from utils.ticket_notifications import is_ticket_staff

logger = logging.getLogger(__name__)


class TimeUnit(str, Enum):
    days = "Days"
    hours = "Hours"


TARGET_GROUP_LABELS: dict[str, str] = {
    "OW-7DAY": "OW-7DAY — مفاتيح 7 أيام",
    "OW-14DAY": "OW-14DAY — مفاتيح 14 يوم",
    "OW-30DAY": "OW-30DAY — مفاتيح 30 يوم",
    "OW-90DAY": "OW-90DAY — مفاتيح 90 يوم",
    "OW-1YEAR": "OW-1YEAR — مفاتيح سنة",
    ALL_PAID_USERS: "كل المشتركين المدفوعين (بدون تجربة/ساعات)",
}


def _target_group_label(value: str) -> str:
    return TARGET_GROUP_LABELS.get(value, value)


def _unit_label(value: str) -> str:
    if value == TimeUnit.days.value:
        return "أيام"
    if value == TimeUnit.hours.value:
        return "ساعات"
    return value


def _mask_license_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}…{key[-4:]}"


def _format_timestamp(ts: int | None) -> str:
    if ts is None or ts <= 0:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_duration(seconds: int | None) -> str:
    if seconds is None or seconds <= 0:
        return "—"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days} يوم")
    if hours:
        parts.append(f"{hours} ساعة")
    if minutes or not parts:
        parts.append(f"{minutes} دقيقة")
    return " ".join(parts)


def _build_success_embed(result) -> discord.Embed:
    added_label = _format_duration(result.added_seconds)
    embed = discord.Embed(
        title="✅ تم تمديد وقت الاشتراك",
        description=(
            "تم تمديد صلاحية المفتاح بنجاح.\n\n"
            f"**الوقت المضاف:** {added_label}"
        ),
        color=discord.Color.from_rgb(87, 242, 135),
    )
    embed.add_field(
        name="المفتاح",
        value=f"`{_mask_license_key(result.license_key)}`",
        inline=True,
    )

    if result.used:
        embed.add_field(name="المستخدم", value=f"`{result.username}`", inline=True)
        embed.add_field(
            name="الاشتراك",
            value=f"`{result.subscription_name}`",
            inline=True,
        )
        embed.add_field(
            name="انتهاء سابق",
            value=_format_timestamp(result.old_expiry),
            inline=False,
        )
        embed.add_field(
            name="انتهاء جديد",
            value=_format_timestamp(result.new_expiry),
            inline=False,
        )
    else:
        embed.add_field(
            name="مدة المفتاح السابقة",
            value=_format_duration(result.old_duration_seconds),
            inline=True,
        )
        embed.add_field(
            name="مدة المفتاح الجديدة",
            value=_format_duration(result.new_duration_seconds),
            inline=True,
        )
        embed.set_footer(text="مفتاح غير مُفعّل · تم التمديد قبل الاستخدام · KeyAuth · SQR Store")
        return embed

    embed.set_footer(text="KeyAuth · SQR Store")
    return embed


def _build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="❌ فشل تمديد الوقت",
        description=message,
        color=discord.Color.from_rgb(237, 66, 69),
    ).set_footer(text="KeyAuth · SQR Store")


def _build_bulk_summary_embed(
    *,
    target_group: str,
    duration: int,
    unit: str,
    matched: int,
    updated: int,
    skipped: int,
    failed: int,
    skipped_reasons: dict[str, int],
    failures: list[tuple[str, str]],
) -> discord.Embed:
    added_seconds = duration * (86400 if unit == TimeUnit.days.value else 3600)
    embed = discord.Embed(
        title="✅ اكتملت التعويضات الجماعية",
        description=(
            f"**المجموعة:** {_target_group_label(target_group)}\n"
            f"**الوقت المضاف لكل مفتاح:** {_format_duration(added_seconds)} "
            f"({duration} {_unit_label(unit)})"
        ),
        color=discord.Color.from_rgb(87, 242, 135),
    )
    embed.add_field(name="مطابقة", value=str(matched), inline=True)
    embed.add_field(name="تم التحديث", value=str(updated), inline=True)
    embed.add_field(name="فشل", value=str(failed), inline=True)
    embed.add_field(name="تم التخطي", value=str(skipped), inline=True)

    if skipped_reasons:
        reason_lines = []
        labels = {
            "prefix_mismatch": "بادئة مختلفة",
            "trial_or_hourly": "تجربة / ساعات",
            "banned": "محظور",
            "missing_key": "مفتاح ناقص",
        }
        for reason, count in sorted(skipped_reasons.items(), key=lambda x: -x[1]):
            reason_lines.append(f"▫️ {labels.get(reason, reason)}: **{count}**")
        embed.add_field(
            name="تفاصيل التخطي",
            value="\n".join(reason_lines[:8]),
            inline=False,
        )

    if failures:
        sample = failures[:5]
        lines = [f"▫️ `{_mask_license_key(key)}` — {err[:80]}" for key, err in sample]
        if len(failures) > 5:
            lines.append(f"… و **{len(failures) - 5}** أخرى")
        embed.add_field(name="أمثلة على الفشل", value="\n".join(lines), inline=False)

    embed.set_footer(text="تعويض جماعي KeyAuth · SQR Store")
    return embed


class KeyAuthLicenseTimeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="add_license_time",
        description="إضافة وقت لمفتاح KeyAuth واحد (للستaff).",
    )
    @app_commands.describe(
        license_key="مفتاح KeyAuth الخاص بالعميل",
        duration_to_add="كم وقت تبي تضيف",
        time_unit="الوحدة: أيام أو ساعات",
    )
    @app_commands.choices(
        time_unit=[
            app_commands.Choice(name="أيام", value="Days"),
            app_commands.Choice(name="ساعات", value="Hours"),
        ],
    )
    async def add_license_time(
        self,
        interaction: discord.Interaction,
        license_key: str,
        duration_to_add: app_commands.Range[int, 1, 3650],
        time_unit: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(
                embed=_build_error_embed("استخدم الأمر داخل السيرفر."),
                ephemeral=True,
            )
            return

        if not is_ticket_staff(interaction.user):
            await interaction.followup.send(
                embed=_build_error_embed("هذا الأمر للستaff فقط."),
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

        preferred_sub = os.environ.get("KEYAUTH_SUBSCRIPTION_NAME", "").strip() or None

        try:
            async with aiohttp.ClientSession() as session:
                result = await extend_license_time(
                    session,
                    sellerkey=sellerkey,
                    license_key=license_key,
                    duration_to_add=duration_to_add,
                    time_unit=time_unit,
                    subscription_name=preferred_sub,
                )
        except KeyAuthError as exc:
            await interaction.followup.send(
                embed=_build_error_embed(str(exc)),
                ephemeral=True,
            )
            return
        except aiohttp.ClientError:
            logger.exception("KeyAuth HTTP error in /add_license_time")
            await interaction.followup.send(
                embed=_build_error_embed("تعذّر الاتصال بـ KeyAuth. حاول لاحقاً."),
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception("Unexpected error in /add_license_time")
            await interaction.followup.send(
                embed=_build_error_embed("حدث خطأ غير متوقع. حاول لاحقاً."),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=_build_success_embed(result),
            ephemeral=True,
        )

    @app_commands.command(
        name="bulk_add_license_time",
        description="إضافة وقت لمجموعة مفاتيح KeyAuth دفعة واحدة (للستaff).",
    )
    @app_commands.describe(
        target_group=(
            "المجموعة: بادئة المفتاح (مثل OW-7DAY) أو كل المشتركين المدفوعين"
        ),
        duration="كم وقت تبي تضيف لكل مفتاح مطابق",
        unit="الوحدة: أيام أو ساعات",
    )
    @app_commands.choices(
        target_group=[
            app_commands.Choice(
                name="OW-7DAY — مفاتيح 7 أيام",
                value="OW-7DAY",
            ),
            app_commands.Choice(
                name="OW-14DAY — مفاتيح 14 يوم",
                value="OW-14DAY",
            ),
            app_commands.Choice(
                name="OW-30DAY — مفاتيح 30 يوم",
                value="OW-30DAY",
            ),
            app_commands.Choice(
                name="OW-90DAY — مفاتيح 90 يوم",
                value="OW-90DAY",
            ),
            app_commands.Choice(
                name="OW-1YEAR — مفاتيح سنة",
                value="OW-1YEAR",
            ),
            app_commands.Choice(
                name="كل المشتركين المدفوعين (بدون تجربة/ساعات)",
                value=ALL_PAID_USERS,
            ),
        ],
        unit=[
            app_commands.Choice(name="أيام", value="Days"),
            app_commands.Choice(name="ساعات", value="Hours"),
        ],
    )
    async def bulk_add_license_time(
        self,
        interaction: discord.Interaction,
        target_group: str,
        duration: app_commands.Range[int, 1, 3650],
        unit: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(
                embed=_build_error_embed("استخدم الأمر داخل السيرفر."),
                ephemeral=True,
            )
            return

        if not is_ticket_staff(interaction.user):
            await interaction.followup.send(
                embed=_build_error_embed("هذا الأمر للستaff فقط."),
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

        preferred_sub = os.environ.get("KEYAUTH_SUBSCRIPTION_NAME", "").strip() or None
        group_value = target_group
        unit_value = unit

        try:
            async with aiohttp.ClientSession() as session:
                rows = await fetch_all_license_rows(session, sellerkey=sellerkey)
                license_keys, skipped_reasons = select_bulk_targets(rows, group_value)

                if not license_keys:
                    skipped_total = sum(skipped_reasons.values())
                    await interaction.followup.send(
                        embed=_build_bulk_summary_embed(
                            target_group=group_value,
                            duration=duration,
                            unit=unit_value,
                            matched=0,
                            updated=0,
                            skipped=skipped_total,
                            failed=0,
                            skipped_reasons=skipped_reasons,
                            failures=[],
                        ),
                        ephemeral=True,
                    )
                    return

                successes, failures = await bulk_extend_license_time(
                    session,
                    sellerkey=sellerkey,
                    license_keys=license_keys,
                    duration_to_add=duration,
                    time_unit=unit_value,
                    subscription_name=preferred_sub,
                )
        except KeyAuthError as exc:
            await interaction.followup.send(
                embed=_build_error_embed(str(exc)),
                ephemeral=True,
            )
            return
        except aiohttp.ClientError:
            logger.exception("KeyAuth HTTP error in /bulk_add_license_time")
            await interaction.followup.send(
                embed=_build_error_embed("تعذّر الاتصال بـ KeyAuth. حاول لاحقاً."),
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception("Unexpected error in /bulk_add_license_time")
            await interaction.followup.send(
                embed=_build_error_embed("حدث خطأ غير متوقع. حاول لاحقاً."),
                ephemeral=True,
            )
            return

        skipped_total = sum(skipped_reasons.values())
        await interaction.followup.send(
            embed=_build_bulk_summary_embed(
                target_group=group_value,
                duration=duration,
                unit=unit_value,
                matched=len(license_keys),
                updated=len(successes),
                skipped=skipped_total,
                failed=len(failures),
                skipped_reasons=skipped_reasons,
                failures=failures,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(KeyAuthLicenseTimeCog(bot))
