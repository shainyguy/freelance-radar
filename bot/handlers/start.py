"""
/start, /help, кнопки главного меню.
"""
from __future__ import annotations
import secrets
from aiogram import Router, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message
from sqlalchemy import select

from bot import keyboards as kb
from core.models import User
from core.categories import get_category_name

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, session, command: CommandObject = None):
    # Реферальная система
    if command and command.args and command.args.startswith("ref_"):
        ref_code = command.args[4:]
        if not user.referred_by:
            r = await session.execute(select(User).where(User.referral_code == ref_code))
            referrer = r.scalar_one_or_none()
            if referrer and referrer.tg_id != user.tg_id:
                user.referred_by = referrer.tg_id
                # Бонус: +5 AI-кредитов обоим
                user.ai_credits_left += 5
                referrer.ai_credits_left += 5
                await session.commit()
                try:
                    await message.bot.send_message(
                        referrer.tg_id,
                        f"🎉 По вашей ссылке зарегистрировался @{user.username or user.first_name}!\n"
                        f"+5 AI-кредитов! (всего: {referrer.ai_credits_left})",
                    )
                except: pass

    # Генерация реферального кода
    if not user.referral_code:
        user.referral_code = secrets.token_urlsafe(8)
        await session.commit()

    has_profile = bool(user.profile_categories or user.profile_skills)

    text = (
        f"👋 Привет, {user.first_name or 'фрилансер'}!\n\n"
        "Я — **Freelance Radar** 📡\n\n"
    )

    if not has_profile:
        text += (
            "🚀 **Давай настроим бота под тебя!**\n"
            "Нажми 👤 Профиль → заполни резюме.\n"
            "Я буду подбирать заказы по твоим навыкам автоматически!\n\n"
        )
    else:
        cats = [get_category_name(c) for c in user.categories_list[:3]]
        cats_str = ", ".join(cats) if cats else "—"
        text += (
            f"📦 Тариф: **{user.tier.upper()}**\n"
            f"🤖 AI: {user.ai_credits_left}  |  🔥 {user.streak_days} дн.\n"
            f"📁 Сферы: {cats_str}\n"
            f"🛠 Навыки: {user.profile_skills or '—'}\n\n"
        )

    text += (
        "🔹 Kwork • FL.ru • Freelance.ru\n\n"
        f"🔗 Реферальная ссылка: `https://t.me/{(await message.bot.me()).username}?start=ref_{user.referral_code}`"
    )

    await message.answer(text, parse_mode="Markdown", reply_markup=kb.main_menu(user.is_admin))


@router.message(Command("help"))
async def cmd_help(message: Message, user: User):
    await message.answer(
        "📖 **Freelance Radar**\n\n"
        "**Кнопки:**\n"
        "🔍 Заказы — подходящие заказы\n"
        "🤖 AI — отклик, скоринг, скам, цена\n"
        "📊 Аналитика — статистика рынка\n"
        "⭐ Избранное — сохранённые\n"
        "👤 Профиль — резюме, категории, навыки\n"
        "💎 Подписка — тарифы\n"
        "📋 Шаблоны — шаблоны откликов\n"
        "🔥 Radar — уникальные фишки\n"
        + ("🔐 Админка — управление\n" if user.is_admin else ""),
        parse_mode="Markdown",
    )


# ── 🔍 Заказы ────────────────────────────────────

@router.message(F.text == "🔍 Заказы")
async def btn_orders(message: Message, user: User, session):
    from sqlalchemy.orm import selectinload
    from core.models import Order, UserFilter, Notification
    from parser.matcher import match_orders_for_user

    r = await session.execute(
        select(UserFilter).where(UserFilter.user_id == user.id, UserFilter.is_active == True)
    )
    filters = list(r.scalars().all())

    r = await session.execute(
        select(Order).options(selectinload(Order.exchange)).order_by(Order.parsed_at.desc()).limit(80)
    )
    orders = list(r.scalars().all())

    # Скрытые
    r = await session.execute(
        select(Notification.order_id).where(
            Notification.user_id == user.id, Notification.user_action == "hidden",
        )
    )
    hidden = {row[0] for row in r.all()}

    matched = [o for o in match_orders_for_user(orders, filters, user) if o.id not in hidden]
    if not matched:
        has_profile = bool(user.profile_categories or user.profile_skills)
        if not has_profile:
            await message.answer(
                "📭 Заполните **профиль** (👤 Профиль), чтобы получать подходящие заказы!\n"
                "Заполните профиль → 👤 Профиль.",
                parse_mode="Markdown",
            )
        else:
            await message.answer("📭 Нет новых подходящих заказов. Попробуйте расширить фильтры.")
        return

    for o in matched[:5]:
        bud = ""
        if o.budget_min and o.budget_max:
            bud = f"💰 {o.budget_min:,.0f} – {o.budget_max:,.0f} {o.currency}"
        elif o.budget_min: bud = f"💰 от {o.budget_min:,.0f} {o.currency}"
        elif o.budget_max: bud = f"💰 до {o.budget_max:,.0f} {o.currency}"

        ex_name = o.exchange.display_name if o.exchange else "?"
        score = f"🎯 {o.ai_score}/100" if o.ai_score else ""
        resps = f"👥 {o.responses_count}" if o.responses_count else ""
        cat_name = get_category_name(o.category) if o.category else ""
        urgent = "🔴 СРОЧНО " if o.is_urgent else ""

        txt = f"{urgent}📋 **{o.title}**\n🏢 {ex_name}"
        if cat_name: txt += f"  |  {cat_name}"
        if bud: txt += f"\n{bud}"
        if score: txt += f"\n{score}"
        if resps: txt += f"\n{resps}"
        if o.deadline: txt += f"\n⏰ Срок: {o.deadline}"
        if o.ai_summary:
            txt += f"\n\n📝 {o.ai_summary}"
        elif o.text:
            preview = o.text[:200] + ("..." if len(o.text) > 200 else "")
            txt += f"\n\n{preview}"

        await message.answer(txt, parse_mode="Markdown",
                              reply_markup=kb.order_card(o.id, o.url, user.ai_credits_left > 0))

    if len(matched) > 5:
        await message.answer(f"Показано 5 из {len(matched)}. Уточните фильтры.")


# ── 💎 Подписка ──────────────────────────────────

@router.message(F.text == "💎 Подписка")
async def btn_sub(message: Message, user: User):
    sub = f"Тариф: **{user.tier.upper()}**\n"
    if user.subscription_until:
        from datetime import datetime, timezone
        rem = (user.subscription_until - datetime.utcnow()).days
        sub += f"До: {user.subscription_until.strftime('%d.%m.%Y')} ({rem} дн.)\n"
    sub += f"AI: {user.ai_credits_left}  |  🔥 {user.streak_days}\n\n"
    sub += (
        "─────────────────\n"
        "⭐ **Pro** 490₽/мес — все биржи, 100 AI, скоринг, детектор, дайджесты\n"
        "💎 **Business** 1490₽/мес — 1000 AI, переговорщик, команда, хантинг\n"
    )
    await message.answer(sub, parse_mode="Markdown", reply_markup=kb.subscription())


# ── 🤖 AI ────────────────────────────────────────

@router.message(F.text == "🤖 AI")
async def btn_ai(message: Message, user: User):
    from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB
    await message.answer(
        f"🤖 **AI-инструменты**\nКредиты: {user.ai_credits_left}\n\n"
        "В карточке заказа:\n"
        "• 🤖 AI-отклик  • 📊 Скоринг  • 📝 TL;DR\n"
        "• 🚨 Детектор скама  • 💰 Оценка цены\n\n"
        "Дополнительно:",
        parse_mode="Markdown",
        reply_markup=IKM(inline_keyboard=[
            [IKB(text="🤝 AI-переговорщик", callback_data="ai_negotiate")],
        ]),
    )


# ── 📊 Аналитика ────────────────────────────────

@router.message(F.text == "📊 Аналитика")
async def btn_analytics(message: Message, user: User, session):
    from sqlalchemy import func
    from core.models import Order, Notification, CRMEntry
    from datetime import datetime, timezone, timedelta
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    today_c = (await session.execute(select(func.count(Order.id)).where(Order.parsed_at >= day_ago))).scalar() or 0
    week_c = (await session.execute(select(func.count(Order.id)).where(Order.parsed_at >= week_ago))).scalar() or 0
    avg_b = (await session.execute(
        select(func.avg(Order.budget_max)).where(Order.parsed_at >= week_ago, Order.budget_max.isnot(None))
    )).scalar() or 0
    my_n = (await session.execute(
        select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.sent_at >= week_ago)
    )).scalar() or 0

    # CRM-статистика
    crm_taken = (await session.execute(
        select(func.count(CRMEntry.id)).where(CRMEntry.user_id == user.id, CRMEntry.status == "taken")
    )).scalar() or 0
    crm_total = (await session.execute(
        select(func.sum(CRMEntry.price_agreed)).where(
            CRMEntry.user_id == user.id, CRMEntry.status.in_(["taken", "completed"]),
            CRMEntry.price_agreed.isnot(None),
        )
    )).scalar() or 0

    txt = (
        "📊 **Аналитика**\n\n"
        f"📋 Сегодня: {today_c} заказов\n"
        f"📋 За неделю: {week_c}\n"
        f"💰 Средний бюджет: {avg_b:,.0f} ₽\n"
        f"🔔 Моих уведомлений: {my_n}\n\n"
        f"📈 **Мои результаты:**\n"
        f"  🤖 AI-откликов: {user.total_responses}\n"
        f"  ✅ Взятых заказов: {crm_taken}\n"
        f"  💰 Заработок (CRM): {crm_total:,.0f} ₽\n"
    )
    if user.reaction_avg_seconds:
        txt += f"  ⚡ Ср. реакция: {user.reaction_avg_seconds // 60} мин.\n"

    await message.answer(txt, parse_mode="Markdown")


# ── ⭐ Избранное ─────────────────────────────────

@router.message(F.text == "⭐ Избранное")
async def btn_saved(message: Message, user: User, session):
    from sqlalchemy.orm import selectinload
    from core.models import SavedOrder, Order
    r = await session.execute(
        select(SavedOrder).where(SavedOrder.user_id == user.id)
        .options(selectinload(SavedOrder.order).selectinload(Order.exchange))
        .order_by(SavedOrder.saved_at.desc()).limit(10)
    )
    saved = list(r.scalars().all())
    if not saved:
        await message.answer("📭 Нет сохранённых заказов."); return
    for s in saved:
        o = s.order
        bud = ""
        if o.budget_min: bud = f"💰 от {o.budget_min:,.0f}"
        if o.budget_max: bud += f" до {o.budget_max:,.0f}"
        ex = o.exchange.display_name if o.exchange else "?"
        await message.answer(
            f"📋 **{o.title}**\n🏢 {ex} {bud}",
            parse_mode="Markdown",
            reply_markup=kb.order_card(o.id, o.url, user.ai_credits_left > 0),
        )


# ── 📋 Шаблоны ──────────────────────────────────

@router.message(F.text == "📋 Шаблоны")
async def btn_templates(message: Message, user: User, session):
    from core.models import ResponseTemplate
    from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB
    r = await session.execute(
        select(ResponseTemplate).where(
            (ResponseTemplate.user_id == user.id) | (ResponseTemplate.is_public == True)
        ).order_by(ResponseTemplate.usage_count.desc()).limit(20)
    )
    tmpls = list(r.scalars().all())
    if not tmpls:
        await message.answer("📋 Нет шаблонов.",
            reply_markup=IKM(inline_keyboard=[[IKB(text="➕ Создать", callback_data="tmpl_create")]])); return
    txt = "📋 **Шаблоны:**\n\n"
    rows = []
    for t in tmpls:
        icon = "📢" if t.is_public else "🔒"
        txt += f"{icon} **{t.title}** ({t.usage_count} исп.)\n"
        rows.append([IKB(text=f"{icon} {t.title}", callback_data=f"tmpl_view:{t.id}")])
    rows.append([IKB(text="➕ Создать", callback_data="tmpl_create")])
    await message.answer(txt, parse_mode="Markdown", reply_markup=IKM(inline_keyboard=rows))


# ── 🔥 Radar — уникальные фишки ─────────────────

@router.message(F.text == "🔥 Radar")
async def btn_radar(message: Message, user: User, session):
    from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB

    ref_link = f"https://t.me/{(await message.bot.me()).username}?start=ref_{user.referral_code}"

    # Считаем рефералов
    from sqlalchemy import func
    ref_count = (await session.execute(
        select(func.count(User.id)).where(User.referred_by == user.tg_id)
    )).scalar() or 0

    txt = (
        "🔥 **Radar — уникальные фишки**\n\n"
        f"🔗 **Реферальная программа**\n"
        f"  Ваша ссылка: `{ref_link}`\n"
        f"  Приглашено: {ref_count} чел.\n"
        f"  За каждого: +5 AI-кредитов обоим!\n\n"
        f"📊 **Персональный дайджест**\n"
        f"  Каждый понедельник — сводка за неделю:\n"
        f"  заказы, тренды, лучшие часы.\n\n"
        f"⚡ **Снайпер-режим** (Pro+)\n"
        f"  Мгновенные уведомления за 30 сек\n"
        f"  до конкурентов.\n\n"
        f"🏷 **Ценовая карта рынка**\n"
        f"  Сколько платят в твоей нише.\n\n"
        f"🎯 **Автоподбор по профилю**\n"
        f"  Заполни резюме — бот сам найдёт.\n"
    )

    await message.answer(txt, parse_mode="Markdown",
        reply_markup=IKM(inline_keyboard=[
            [IKB(text="📊 Дайджест сейчас", callback_data="radar:digest")],
            [IKB(text="🏷 Ценовая карта", callback_data="radar:price_map")],
            [IKB(text="⏰ Лучшее время", callback_data="radar:best_time")],
            [IKB(text="📋 Копировать реф-ссылку", callback_data="radar:ref_link")],
        ]),
    )
