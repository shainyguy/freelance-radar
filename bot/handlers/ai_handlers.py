"""
AI-фичи + конкурентоспособность + CRM с заработком.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB
from sqlalchemy import select

from bot.states import AIChat
from bot import keyboards as kb
from core.config import settings
from core import gigachat_client as ai
from core.competitiveness import calc_competitiveness, format_competitiveness
from core.models import User, Order, SavedOrder, Notification, CRMEntry

logger = logging.getLogger(__name__)
router = Router()


async def _order(session, oid: int):
    r = await session.execute(select(Order).where(Order.id == oid))
    return r.scalar_one_or_none()

async def _check_ai(cb: CallbackQuery, user: User) -> bool:
    if user.ai_credits_left <= 0:
        await cb.answer("❌ AI-кредиты кончились!", show_alert=True)
        return False
    return True

async def _spend(user: User, session):
    user.ai_credits_left -= 1
    user.total_responses += 1
    await session.commit()


# ── AI-отклик ─────────────────────────────────────

@router.callback_query(F.data.startswith("ai_resp:"))
async def ai_response(cb: CallbackQuery, user: User, session):
    if not await _check_ai(cb, user): return
    oid = int(cb.data.split(":")[1])
    o = await _order(session, oid)
    if not o: await cb.answer("Не найден", show_alert=True); return
    await cb.answer("🤖 Генерирую..."); await cb.message.answer("⏳ AI-отклик...")
    try:
        text = await ai.generate_response(
            o.title, o.text or "",
            user.profile_description or "", user.profile_skills or "",
            user.profile_experience_years, user.response_style or "",
        )
        await _spend(user, session)
        o.our_responses_count += 1; await session.commit()
        await cb.message.answer(
            f"🤖 **AI-отклик:**\n\n{text}\n\n───\n💳 AI: {user.ai_credits_left}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"ai_resp: {e}"); await cb.message.answer(f"❌ {e}")


# ── AI-скоринг ────────────────────────────────────

@router.callback_query(F.data.startswith("ai_score:"))
async def ai_scoring(cb: CallbackQuery, user: User, session, tier_limits: dict):
    if not tier_limits.get("ai_scoring"):
        await cb.answer("🔒 Pro", show_alert=True); return
    oid = int(cb.data.split(":")[1])
    o = await _order(session, oid)
    if not o: await cb.answer("?", show_alert=True); return
    await cb.answer("📊..."); await cb.message.answer("⏳...")
    try:
        bud = f"{o.budget_min or '?'} – {o.budget_max or '?'} {o.currency}" if (o.budget_min or o.budget_max) else ""
        res = await ai.score_order(o.title, o.text or "", bud, o.client_rating, o.responses_count)
        score = res.get("score", "?")
        o.ai_score = int(score) if isinstance(score, (int, float)) else None
        await session.commit()
        fire = "🔥" if isinstance(score, (int,float)) and score >= 70 else ""
        txt = f"📊 **AI-скоринг** {fire}\n🎯 **{score}/100**\n"
        bd = res.get("breakdown", {})
        if bd:
            for k,l in {"clarity":"Чёткость","budget":"Бюджет","client":"Клиент","profit":"Потенциал"}.items():
                txt += f"  • {l}: {bd.get(k,'?')}/25\n"
        if res.get("summary"): txt += f"\n📝 {res['summary']}"
        if res.get("recommendation"): txt += f"\n💡 {res['recommendation']}"
        await cb.message.answer(txt, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"ai_score: {e}"); await cb.message.answer(f"❌ {e}")


# ── TL;DR ────────────────────────────────────────

@router.callback_query(F.data.startswith("ai_tldr:"))
async def ai_tldr(cb: CallbackQuery, user: User, session):
    if not await _check_ai(cb, user): return
    oid = int(cb.data.split(":")[1])
    o = await _order(session, oid)
    if not o: await cb.answer("?", show_alert=True); return
    await cb.answer("📝...")
    try:
        s = await ai.summarize_order(o.title, o.text or "")
        await _spend(user, session)
        o.ai_summary = s; await session.commit()
        await cb.message.answer(f"📝 **TL;DR:**\n\n{s}\n\n💳 AI: {user.ai_credits_left}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"ai_tldr: {e}"); await cb.message.answer(f"❌ {e}")


# ── Скам-детектор ────────────────────────────────

@router.callback_query(F.data.startswith("ai_scam:"))
async def ai_scam(cb: CallbackQuery, user: User, session, tier_limits: dict):
    if not tier_limits.get("ai_scam_detector"):
        await cb.answer("🔒 Pro", show_alert=True); return
    oid = int(cb.data.split(":")[1])
    o = await _order(session, oid)
    if not o: await cb.answer("?", show_alert=True); return
    await cb.answer("🚨...")
    try:
        bud = f"{o.budget_min or '?'} – {o.budget_max or '?'}" if (o.budget_min or o.budget_max) else ""
        res = await ai.detect_scam(o.title, o.text or "", bud)
        risk = res.get("risk_level","low")
        emoji = {"low":"🟢","medium":"🟡","high":"🔴"}.get(risk,"⚪")
        txt = f"🚨 **Скам-чек**\nРиск: {emoji} **{risk.upper()}**\n"
        flags = res.get("flags", [])
        if flags: txt += "\n⚠️ Флаги:\n" + "\n".join(f"  • {f}" for f in flags)
        if res.get("explanation"): txt += f"\n\n💬 {res['explanation']}"
        if not res.get("is_suspicious"): txt += "\n\n✅ Безопасно."
        await cb.message.answer(txt, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"ai_scam: {e}"); await cb.message.answer(f"❌ {e}")


# ── Оценка цены ──────────────────────────────────

@router.callback_query(F.data.startswith("ai_price:"))
async def ai_price(cb: CallbackQuery, user: User, session):
    if not await _check_ai(cb, user): return
    oid = int(cb.data.split(":")[1])
    o = await _order(session, oid)
    if not o: await cb.answer("?", show_alert=True); return
    await cb.answer("💰...")
    try:
        res = await ai.estimate_price(o.title, o.text or "")
        await _spend(user, session)
        txt = "💰 **Калькулятор**\n\n"
        if res.get("min_price") and res.get("max_price"):
            txt += f"📊 {res['min_price']:,.0f} – {res['max_price']:,.0f} ₽\n"
        if res.get("recommended_price"):
            txt += f"✅ Рекомендация: **{res['recommended_price']:,.0f} ₽**\n"
        if res.get("estimated_hours"):
            txt += f"⏱ ~{res['estimated_hours']} ч.\n"
        if res.get("explanation"): txt += f"\n{res['explanation']}"
        txt += f"\n\n💳 AI: {user.ai_credits_left}"
        await cb.message.answer(txt, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"ai_price: {e}"); await cb.message.answer(f"❌ {e}")


# ── 📊 Конкурентоспособность ─────────────────────

@router.callback_query(F.data.startswith("compete:"))
async def competitiveness(cb: CallbackQuery, session):
    oid = int(cb.data.split(":")[1])
    o = await _order(session, oid)
    if not o: await cb.answer("?", show_alert=True); return
    await cb.answer()
    data = calc_competitiveness(
        budget_max=o.budget_max,
        responses_count=o.responses_count,
        is_urgent=o.is_urgent,
        ai_score=o.ai_score,
        posted_at=o.posted_at or o.parsed_at,
    )
    await cb.message.answer(format_competitiveness(data), parse_mode="Markdown")


# ── Переговорщик ─────────────────────────────────

@router.callback_query(F.data == "ai_negotiate")
async def ai_neg_start(cb: CallbackQuery, state: FSMContext, user: User, tier_limits: dict):
    if not tier_limits.get("ai_negotiator"):
        await cb.answer("🔒 Business", show_alert=True); return
    await cb.answer()
    await cb.message.answer("🤝 Пришлите текст переписки с заказчиком:")
    await state.set_state(AIChat.negotiation_message)

@router.message(AIChat.negotiation_message)
async def ai_neg_process(msg: Message, state: FSMContext, user: User, session):
    if user.ai_credits_left <= 0:
        await msg.answer("❌ Нет кредитов."); await state.clear(); return
    await msg.answer("⏳...")
    try:
        resp = await ai.negotiate(msg.text)
        await _spend(user, session)
        await msg.answer(f"🤝 **Рекомендация:**\n\n{resp}\n\n💳 AI: {user.ai_credits_left}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"ai_neg: {e}"); await msg.answer(f"❌ {e}")
    await state.clear()


# ── Сохранить / Скрыть ───────────────────────────

@router.callback_query(F.data.startswith("save:"))
async def save_order(cb: CallbackQuery, user: User, session):
    oid = int(cb.data.split(":")[1])
    r = await session.execute(select(SavedOrder).where(SavedOrder.user_id == user.id, SavedOrder.order_id == oid))
    if r.scalar_one_or_none(): await cb.answer("Уже!"); return
    session.add(SavedOrder(user_id=user.id, order_id=oid))
    user.total_saved += 1; await session.commit()
    await cb.answer("⭐ Сохранено!")

@router.callback_query(F.data.startswith("hide:"))
async def hide_order(cb: CallbackQuery, user: User, session):
    oid = int(cb.data.split(":")[1])
    session.add(Notification(user_id=user.id, order_id=oid, user_action="hidden"))
    await session.commit(); await cb.answer("🙈 Скрыто")
    try: await cb.message.delete()
    except: pass


# ══════════════════════════════════════════════════
# 📋 CRM с заработком
# ══════════════════════════════════════════════════

@router.callback_query(F.data.startswith("crm:"))
async def crm_menu(cb: CallbackQuery, user: User, session):
    oid = int(cb.data.split(":")[1])
    # Проверяем есть ли уже запись
    r = await session.execute(select(CRMEntry).where(CRMEntry.user_id == user.id, CRMEntry.order_id == oid))
    entry = r.scalar_one_or_none()
    if entry:
        labels = {"new":"🆕","responded":"📩","negotiation":"💬","taken":"✅","rejected":"❌","completed":"🏁"}
        txt = f"📋 **CRM-статус:** {labels.get(entry.status, '')} {entry.status}\n"
        if entry.price_agreed: txt += f"💰 Цена: {entry.price_agreed:,.0f} ₽\n"
        if entry.notes: txt += f"📝 {entry.notes}\n"
        await cb.answer()
        await cb.message.answer(txt, parse_mode="Markdown", reply_markup=kb.crm_status(oid))
    else:
        await cb.answer()
        await cb.message.answer("📋 Выберите статус:", reply_markup=kb.crm_status(oid))


@router.callback_query(F.data.startswith("crms:"))
async def crm_set(cb: CallbackQuery, user: User, session):
    parts = cb.data.split(":")
    oid, status = int(parts[1]), parts[2]
    r = await session.execute(select(CRMEntry).where(CRMEntry.user_id == user.id, CRMEntry.order_id == oid))
    entry = r.scalar_one_or_none()
    if entry:
        entry.status = status
    else:
        entry = CRMEntry(user_id=user.id, order_id=oid, status=status)
        session.add(entry)
    await session.commit()

    labels = {"responded":"📩","negotiation":"💬","taken":"✅","rejected":"❌","completed":"🏁"}
    await cb.answer(f"{labels.get(status,'')} Обновлено")

    # Если "taken" — спрашиваем цену
    if status == "taken":
        await cb.message.answer(
            "✅ Отлично! Введите **согласованную цену** (₽) или `-`:",
            parse_mode="Markdown",
        )
    elif status == "completed":
        # Если есть цена — добавляем к заработку
        if entry.price_agreed:
            user.earnings_total += entry.price_agreed
            await session.commit()
            await cb.message.answer(
                f"🏁 Заказ завершён!\n💰 +{entry.price_agreed:,.0f} ₽\n"
                f"📈 Общий заработок: **{user.earnings_total:,.0f} ₽**",
                parse_mode="Markdown",
            )
        else:
            await cb.message.answer(
                "🏁 Завершён! Введите **полученную сумму** (₽) или `-`:",
                parse_mode="Markdown",
            )
    else:
        await cb.message.edit_text(f"✅ CRM: {labels.get(status,'')} {status}")


# Обработка ввода цены после CRM (ловит числа)
# Этот хэндлер сработает только если юзер ввёл число
@router.message(F.text.regexp(r"^\d+$"))
async def crm_price_input(msg: Message, user: User, session):
    """Ловим ввод цены для CRM (число без пробелов)."""
    price = float(msg.text.strip())

    # Ищем последнюю CRM-запись без цены
    r = await session.execute(
        select(CRMEntry).where(
            CRMEntry.user_id == user.id,
            CRMEntry.price_agreed.is_(None),
            CRMEntry.status.in_(["taken", "completed"]),
        ).order_by(CRMEntry.updated_at.desc()).limit(1)
    )
    entry = r.scalar_one_or_none()
    if not entry:
        return  # не наш случай — пропускаем

    entry.price_agreed = price
    if entry.status == "completed":
        user.earnings_total += price

    await session.commit()

    txt = f"💰 Цена: **{price:,.0f} ₽** сохранена!\n"
    if entry.status == "completed":
        txt += f"📈 Общий заработок: **{user.earnings_total:,.0f} ₽**"

    await msg.answer(txt, parse_mode="Markdown")
