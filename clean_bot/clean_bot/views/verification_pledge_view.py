"""Persistent pledge panel: green accept button assigns verified role."""

from __future__ import annotations

import logging
import os

import discord

logger = logging.getLogger(__name__)

PLEDGE_EMBED_TITLE = "📜 ميثاق وإقرار ملزم | SQR Store"

PLEDGE_EMBED_DESCRIPTION = (
    "الخطوه ١ 🔴: أُقر أنا (بصفتي صاحب هذا الحساب) أنني قرأت جميع هذه الشروط بتمعن،"
    " وأوافق عليها التزاماً كاملاً لا رجعة فيه.\n\n"
    "الخطوه ٢ 🟠: أتعهد أمام الله ثم أمام إدارة متجر صقر، أنني لن أستخدم أي أداة أو سكربت"
    " لظلم اللاعبين العاديين، أو لتخريب متعة اللعب النظيف بأي شكل من الأشكال.\n\n"
    "خطوه ٣. 🟡: أُقر وأتفهم تماماً أن 'متجر صقر' يوفر هذه الأدوات حصرياً كـ 'حل اضطراري'،"
    " نظراً لسوء وضعف أنظمة الحماية في الألعاب وانتشار الغشاشين.\n\n"
    "خطوه ٤ 🟢: أتعهد بأن استخدامي لأي من (الكراسي، التتبع، السكربتات) سيكون مقتصراً كـ"
    " 'ردة فعل دفاعية' فقط، في حال واجهت عدواً غشاشاً ضدي، أو 'سميرف' يتعمد تخريب اللعبة.\n\n"
    "خطوه ٥ 🔵: أُقر بأن أي محاولة لتسريب، مشاركة، أو إعادة بيع أي من أكواد ومنتجات متجر صقر"
    " لطرف ثالث، ستعرضني للطرد النهائي، سحب الرتب، وإلغاء مفاتيحي فوراً وبدون تعويض.\n\n"
    "خطوه ٦ 🟣: بضغطي على الزر أدناه، أعتبر هذا الإقرار بمثابة ميثاق غليظ أتحمل مسؤوليته"
    " الكاملة أمام الله أولاً، ثم أمام إدارة السيرفر."
)

PLEDGE_BUTTON_CUSTOM_ID = "verification_pledge_accept_v1"


def build_pledge_embed() -> discord.Embed:
    return discord.Embed(
        title=PLEDGE_EMBED_TITLE,
        description=PLEDGE_EMBED_DESCRIPTION,
        color=discord.Color.dark_teal(),
    )


def _verified_role_id() -> int | None:
    raw = os.environ.get("VERIFIED_ROLE_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("VERIFIED_ROLE_ID is not a valid integer: %r", raw)
        return None


class VerificationPledgeView(discord.ui.View):
    """timeout=None + fixed custom_id so the button survives bot restarts."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="أوافق وأتعهد ✔️",
        style=discord.ButtonStyle.success,
        custom_id=PLEDGE_BUTTON_CUSTOM_ID,
    )
    async def accept_pledge(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "يمكن تنفيذ هذا الإجراء داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        role_id = _verified_role_id()
        if role_id is None:
            await interaction.response.send_message(
                "لم يُضبط رقم رتبة التحقق على البوت (`VERIFIED_ROLE_ID`). أبلغ الإدارة.",
                ephemeral=True,
            )
            return

        role = interaction.guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message(
                "رتبة التحقق غير موجودة في هذا السيرفر أو المعرف غير صحيح.",
                ephemeral=True,
            )
            return

        member = interaction.user
        if role in member.roles:
            await interaction.response.send_message(
                "لديك رتبة التحقق مسبقاً.",
                ephemeral=True,
            )
            return

        bot_member = interaction.guild.me
        if bot_member is None or role.position >= bot_member.top_role.position:
            await interaction.response.send_message(
                "لا يمكن للبوت منح هذه الرتبة (تسلسل الرتب). اطلب من الإدارة رفع رتبة البوت.",
                ephemeral=True,
            )
            return

        try:
            await member.add_roles(role, reason="Verification pledge accepted (System 1)")
        except discord.Forbidden:
            await interaction.response.send_message(
                "البوت لا يملك صلاحية **Manage Roles** أو لا يمكنه منح هذه الرتبة.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as exc:
            logger.exception("Failed to add verified role")
            await interaction.response.send_message(
                f"حدث خطأ أثناء منح الرتبة: `{exc}`",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "✅ تم قبول الإقرار ومنحك رتبة التحقق.",
            ephemeral=True,
        )
