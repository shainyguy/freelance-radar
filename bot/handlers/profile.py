"""
Профиль-резюме с категориями, навыками, тихий режим,
достижения, чёрный список, шаблоны, подписка, фишки Radar.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB
from sqlalchemy import select, func

from bot.states import ProfileSetup, BlacklistAdd, TemplateCreate
from bot import keyboards as kb
from core.categories import get_category_name, get_parent_categories
from core.models import User, BlacklistEntry, Achievement, ResponseTemplate, Payment, Order

logger = logging.getLogger(__name__)
router = Router()


# ══════════════════════════════════════════════════
# 👤 Профиль — вход
# ══════════════════════════════════════════════════

@router.message(F.text == "👤 Профиль")
async def btn_profile(message: Message, user: User):
    cats = [get_category_name(c) for c in user.categories_list] if user.profile_categories else ["не указаны"]
    skills = user.profile_skills or "не указаны"

    txt = (
        "👤 **Мой профиль**\n\n"
        f"📝 {user.profile_description or 'Не заполнено'}\n"
        f"📁 Категории: {', '.join(cats)}\n"
        f"🛠 Навыки: {skills}\n"
        f"📅 Опыт: {user.profile_experience_years or '?'} лет\n"
        f"💵 Ставка: {user.profile_hourly_rate or '?'} ₽/час\n"
        f"💰 Мин. бюджет: {user.profile_min_budget or '—'} ₽\n"
        f"✍️ Стиль: {user.response_style or 'стандартный'}\n"
        f"🔗 Портфолио: {user.portfolio_url or '—'}\n\n"
        f"Тариф: {user.tier.upper()} | AI: {user.ai_credits_left} | 🔥 {user.streak_days}\n"
    )

    await message.answer(txt, parse_mode="Markdown",
        reply_markup=IKM(inline_keyboard=[
            [IKB(text="📁 Выбрать категории", callback_data="prof_cats")],
            [IKB(text="🛠 Выбрать навыки",    callback_data="prof_skills")],
            [IKB(text="✏️ Описание / опыт",    callback_data="prof_edit")],
            [IKB(text="💵 Ставка и бюджет",    callback_data="prof_rate")],
            [IKB(text="🔕 Тихий режим",       callback_data="quiet")],
            [IKB(text="🏆 Достижения",        callback_data="my_ach")],
            [IKB(text="🚫 Чёрный список",     callback_data="my_bl")],
            [IKB(text="📈 Мой рост",          callback_data="my_growth")],
        ]),
    )


# ══════════════════════════════════════════════════
# 📁 Категории — выбор из списка
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "prof_cats")
async def prof_cats_start(cb: CallbackQuery, user: User, state: FSMContext):
    selected = user.categories_list
    await state.update_data(sel_cats=selected)
    await cb.answer()
    await cb.message.answer("📁 Выберите **ваши категории**:", parse_mode="Markdown",
                             reply_markup=kb.categories_parent(selected))


@router.callback_query(F.data.startswith("cat_p:"))
async def prof_cat_toggle(cb: CallbackQuery, state: FSMContext):
    code = cb.data.split(":")[1]
    data = await state.get_data()
    sel = data.get("sel_cats", [])
    if code in sel: sel.remove(code)
    else: sel.append(code)
    await state.update_data(sel_cats=sel)
    await cb.message.edit_reply_markup(reply_markup=kb.categories_parent(sel))
    await cb.answer()


@router.callback_query(F.data == "cat_subs")
async def prof_cat_subs_menu(cb: CallbackQuery, state: FSMContext):
    """Показать список родительских категорий для уточнения."""
    from core.categories import CATEGORIES
    b = []
    for code, (emoji, name, _) in CATEGORIES.items():
        b.append([IKB(text=f"{emoji} {name}", callback_data=f"cat_sub_of:{code}")])
    b.append([IKB(text="« Назад", callback_data="cat_back")])
    await cb.answer()
    await cb.message.answer("Выберите сферу для уточнения:", reply_markup=IKM(inline_keyboard=b))


@router.callback_query(F.data.startswith("cat_sub_of:"))
async def prof_cat_subs_show(cb: CallbackQuery, state: FSMContext):
    parent = cb.data.split(":")[1]
    data = await state.get_data()
    sel = data.get("sel_cats", [])
    await cb.answer()
    await cb.message.answer("Выберите подкатегории:", reply_markup=kb.categories_sub(parent, sel))


@router.callback_query(F.data.startswith("cat_s:"))
async def prof_cat_sub_toggle(cb: CallbackQuery, state: FSMContext):
    code = cb.data.split(":")[1]
    data = await state.get_data()
    sel = data.get("sel_cats", [])
    if code in sel: sel.remove(code)
    else: sel.append(code)
    await state.update_data(sel_cats=sel)
    # Определяем parent
    parent = code.split("_")[0] if "_" in code else code
    await cb.message.edit_reply_markup(reply_markup=kb.categories_sub(parent, sel))
    await cb.answer()


@router.callback_query(F.data == "cat_back")
async def prof_cat_back(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    sel = data.get("sel_cats", [])
    await cb.answer()
    await cb.message.answer("📁 Категории:", reply_markup=kb.categories_parent(sel))


@router.callback_query(F.data == "cat_done")
async def prof_cat_done(cb: CallbackQuery, state: FSMContext, user: User, session):
    data = await state.get_data()
    sel = data.get("sel_cats", [])
    user.profile_categories = ",".join(sel) if sel else None
    await session.commit()
    names = [get_category_name(c) for c in sel] if sel else ["не выбрано"]
    await cb.answer("✅ Сохранено!")
    await cb.message.answer(f"✅ Категории: {', '.join(names)}", parse_mode="Markdown")
    await state.clear()


# ══════════════════════════════════════════════════
# 🛠 Навыки — выбор из списка
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "prof_skills")
async def prof_skills_start(cb: CallbackQuery, user: User, state: FSMContext):
    selected = user.skills_list
    await state.update_data(sel_skills=selected, skill_page=0)
    await cb.answer()
    await cb.message.answer("🛠 Выберите **навыки** (или допишите свои потом):",
                             parse_mode="Markdown", reply_markup=kb.skills_select(selected, 0))


@router.callback_query(F.data.startswith("skill_tog:"))
async def skill_toggle(cb: CallbackQuery, state: FSMContext):
    skill = cb.data.split(":", 1)[1]
    data = await state.get_data()
    sel = data.get("sel_skills", [])
    page = data.get("skill_page", 0)
    if skill in sel: sel.remove(skill)
    else: sel.append(skill)
    await state.update_data(sel_skills=sel)
    await cb.message.edit_reply_markup(reply_markup=kb.skills_select(sel, page))
    await cb.answer()


@router.callback_query(F.data.startswith("skill_page:"))
async def skill_page(cb: CallbackQuery, state: FSMContext):
    page = int(cb.data.split(":")[1])
    data = await state.get_data()
    sel = data.get("sel_skills", [])
    await state.update_data(skill_page=page)
    await cb.message.edit_reply_markup(reply_markup=kb.skills_select(sel, page))
    await cb.answer()


@router.callback_query(F.data == "skill_done")
async def skill_done(cb: CallbackQuery, state: FSMContext, user: User, session):
    data = await state.get_data()
    sel = data.get("sel_skills", [])
    user.profile_skills = ",".join(sel) if sel else None
    await session.commit()
    await cb.answer("✅ Сохранено!")
    await cb.message.answer(f"✅ Навыки: {', '.join(sel) if sel else '—'}")
    await state.clear()


# ══════════════════════════════════════════════════
# ✏️ Описание / опыт (текстовый ввод)
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "prof_edit")
async def prof_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.answer("📝 Опишите себя (2-3 предложения — для AI-откликов):")
    await state.set_state(ProfileSetup.description)

@router.message(ProfileSetup.description)
async def prof_desc(msg: Message, state: FSMContext):
    await state.update_data(desc=msg.text.strip())
    await msg.answer("📅 Лет опыта (число):")
    await state.set_state(ProfileSetup.experience)

@router.message(ProfileSetup.experience)
async def prof_exp(msg: Message, state: FSMContext):
    try: y = int(msg.text.strip())
    except ValueError: await msg.answer("❌ Число"); return
    await state.update_data(exp=y)
    await msg.answer("✍️ Стиль откликов (например: 'деловой, лаконичный') или `-`:")
    await state.set_state(ProfileSetup.response_style)

@router.message(ProfileSetup.response_style)
async def prof_style(msg: Message, state: FSMContext, user: User, session):
    data = await state.get_data()
    user.profile_description = data["desc"]
    user.profile_experience_years = data["exp"]
    user.response_style = msg.text.strip() if msg.text.strip() != "-" else None
    await session.commit()
    await msg.answer("✅ Профиль обновлён!")
    await state.clear()


# ══════════════════════════════════════════════════
# 💵 Ставка и мин. бюджет
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "prof_rate")
async def prof_rate(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "💵 Введите через пробел: **ставка** (₽/час) и **мин. бюджет** заказа (₽)\n"
        "Пример: `1500 5000`\n"
        "Или `-` чтобы пропустить.",
        parse_mode="Markdown",
    )

@router.message(F.text.regexp(r"^\d+\s+\d+$"))
async def prof_rate_set(msg: Message, user: User, session):
    parts = msg.text.strip().split()
    user.profile_hourly_rate = int(parts[0])
    user.profile_min_budget = int(parts[1])
    await session.commit()
    await msg.answer(f"✅ Ставка: {user.profile_hourly_rate} ₽/ч, мин. бюджет: {user.profile_min_budget} ₽")


# ══════════════════════════════════════════════════
# 🔕 Тихий режим
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "quiet")
async def quiet_menu(cb: CallbackQuery, user: User):
    cur = f"\nСейчас: {user.quiet_hours_start}:00 – {user.quiet_hours_end}:00" if user.quiet_hours_start is not None else "\nВыключен"
    await cb.answer()
    await cb.message.answer(f"🔕 **Тихий режим**{cur}", parse_mode="Markdown",
        reply_markup=IKM(inline_keyboard=[
            [IKB(text="🌙 22–08", callback_data="qset:22:8")],
            [IKB(text="🌙 23–09", callback_data="qset:23:9")],
            [IKB(text="🔔 Выключить", callback_data="qset:off")],
        ]))

@router.callback_query(F.data.startswith("qset:"))
async def quiet_set(cb: CallbackQuery, user: User, session):
    p = cb.data.split(":")
    if p[1] == "off":
        user.quiet_hours_start = user.quiet_hours_end = None
    else:
        user.quiet_hours_start = int(p[1]); user.quiet_hours_end = int(p[2])
    await session.commit()
    await cb.answer("✅ Сохранено")


# ══════════════════════════════════════════════════
# 🏆 Достижения
# ══════════════════════════════════════════════════

ACH = {
    "first_response": ("🎯 Первый отклик", "AI-отклик"),
    "10_responses_day": ("⚡ 10 за день", "10 AI"),
    "ai_master": ("🤖 AI-мастер", "50 AI"),
    "streak_7": ("🔥 Неделя", "7 дней"),
    "streak_30": ("🔥 Месяц", "30 дней"),
    "saved_50": ("⭐ Коллекционер", "50 сохранённых"),
    "pro_subscriber": ("💎 Pro", "Подписка"),
    "referral_3": ("🤝 Приглашатель", "3 реферала"),
    "first_crm_completed": ("🏁 Первый завершённый", "CRM"),
    "earnings_10k": ("💰 10К", "Заработок 10 000₽"),
}

@router.callback_query(F.data == "my_ach")
async def my_ach(cb: CallbackQuery, user: User, session):
    r = await session.execute(select(Achievement).where(Achievement.user_id == user.id))
    unlocked = {a.code for a in r.scalars().all()}
    txt = "🏆 **Достижения:**\n\n"
    for code, (name, desc) in ACH.items():
        txt += f"{'✅' if code in unlocked else '🔒'} {name} — {desc}\n"
    txt += f"\n🔓 {len(unlocked)}/{len(ACH)}"
    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown")


# ══════════════════════════════════════════════════
# 🚫 Чёрный список (кратко — без изменений)
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "my_bl")
async def my_bl(cb: CallbackQuery, user: User, session):
    r = await session.execute(select(BlacklistEntry).where(BlacklistEntry.user_id == user.id))
    entries = list(r.scalars().all())
    txt = "🚫 **Чёрный список:**\n\n"
    if not entries: txt += "Пусто."
    else:
        for e in entries: txt += f"• **{e.client_name}** — {e.reason or '—'}\n"
    await cb.answer()
    await cb.message.answer(txt, parse_mode="Markdown",
        reply_markup=IKM(inline_keyboard=[[IKB(text="➕ Добавить", callback_data="bl_add")]]))

@router.callback_query(F.data == "bl_add")
async def bl_add(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.answer("🚫 Имя/ник заказчика:")
    await state.set_state(BlacklistAdd.client_name)

@router.message(BlacklistAdd.client_name)
async def bl_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await msg.answer("📝 Причина (или `-`):")
    await state.set_state(BlacklistAdd.reason)

@router.message(BlacklistAdd.reason)
async def bl_reason(msg: Message, state: FSMContext, user: User, session):
    d = await state.get_data()
    session.add(BlacklistEntry(user_id=user.id, client_name=d["name"],
                               reason=msg.text.strip() if msg.text.strip() != "-" else None))
    await session.commit()
    await msg.answer(f"🚫 {d['name']} добавлен."); await state.clear()


# ══════════════════════════════════════════════════
# 📋 Шаблоны
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "tmpl_create")
async def tmpl_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.answer("📋 **Название** шаблона:", parse_mode="Markdown")
    await state.set_state(TemplateCreate.title)

@router.message(TemplateCreate.title)
async def tmpl_title(msg: Message, state: FSMContext):
    await state.update_data(title=msg.text.strip())
    await msg.answer("📝 Текст шаблона:")
    await state.set_state(TemplateCreate.text)

@router.message(TemplateCreate.text)
async def tmpl_text(msg: Message, state: FSMContext, user: User, session):
    d = await state.get_data()
    session.add(ResponseTemplate(user_id=user.id, title=d["title"], text=msg.text.strip()))
    await session.commit()
    await msg.answer(f"✅ Шаблон «{d['title']}» создан!"); await state.clear()

@router.callback_query(F.data.startswith("tmpl_view:"))
async def tmpl_view(cb: CallbackQuery, session):
    tid = int(cb.data.split(":")[1])
    r = await session.execute(select(ResponseTemplate).where(ResponseTemplate.id == tid))
    t = r.scalar_one_or_none()
    if not t: await cb.answer("?", show_alert=True); return
    await cb.answer()
    await cb.message.answer(f"📋 **{t.title}**\n\n{t.text}", parse_mode="Markdown")


# ══════════════════════════════════════════════════
# 💎 Подписка
# ══════════════════════════════════════════════════

@router.callback_query(F.data.startswith("sub:"))
async def sub_pay(cb: CallbackQuery, user: User, session):
    parts = cb.data.split(":")
    tier, months = parts[1], int(parts[2])
    from core.config import PRICING
    amount = PRICING.get(tier, {}).get(str(months))
    if not amount: await cb.answer("Ошибка", show_alert=True); return
    await cb.answer(); await cb.message.answer("⏳ Создаю платёж...")
    try:
        from core.yookassa_client import create_payment
        res = create_payment(user.tg_id, tier, months)
        session.add(Payment(user_id=user.id, yookassa_payment_id=res["payment_id"],
                            amount=res["amount"], tier=tier, months=months, status="pending"))
        await session.commit()
        await cb.message.answer(f"💳 **{tier.upper()}** — {months} мес. — **{amount:,.0f} ₽**",
            parse_mode="Markdown",
            reply_markup=IKM(inline_keyboard=[[IKB(text="💳 Оплатить", url=res["confirmation_url"])]]))
    except Exception as e:
        logger.error(f"payment: {e}"); await cb.message.answer("❌ Ошибка платежа.")


# ══════════════════════════════════════════════════
# 🔥 Radar — уникальные фишки (обработка кнопок)
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "radar:digest")
async def radar_digest(cb: CallbackQuery, user: User, session):
    """Мгновенный дайджест."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    total = (await session.execute(select(func.count(Order.id)).where(Order.parsed_at >= week_ago))).scalar() or 0
    avg_b = (await session.execute(
        select(func.avg(Order.budget_max)).where(Order.parsed_at >= week_ago, Order.budget_max.isnot(None))
    )).scalar() or 0

    # Топ-категории
    r = await session.execute(
        select(Order.category, func.count(Order.id))
        .where(Order.parsed_at >= week_ago, Order.category.isnot(None))
        .group_by(Order.category)
        .order_by(func.count(Order.id).desc()).limit(5)
    )
    top_cats = [(get_category_name(row[0]), row[1]) for row in r.all()]

    txt = (
        "📊 **Дайджест за неделю**\n\n"
        f"📋 Заказов: {total}\n"
        f"💰 Средний бюджет: {avg_b:,.0f} ₽\n\n"
    )
    if top_cats:
        txt += "🏆 **Топ-категории:**\n"
        for name, cnt in top_cats:
            txt += f"  {name}: {cnt}\n"

    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown")


@router.callback_query(F.data == "radar:price_map")
async def radar_price_map(cb: CallbackQuery, user: User, session):
    """Ценовая карта по категориям пользователя."""
    cats = user.categories_list
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)

    txt = "🏷 **Ценовая карта рынка**\n\n"

    if not cats:
        # Общая по всем
        r = await session.execute(
            select(Order.category, func.avg(Order.budget_max), func.count(Order.id))
            .where(Order.parsed_at >= month_ago, Order.budget_max.isnot(None), Order.category.isnot(None))
            .group_by(Order.category)
            .order_by(func.avg(Order.budget_max).desc()).limit(8)
        )
        for cat, avg, cnt in r.all():
            txt += f"  {get_category_name(cat)}: **{avg:,.0f} ₽** ({cnt} заказов)\n"
    else:
        for cat in cats:
            r = await session.execute(
                select(func.avg(Order.budget_max), func.min(Order.budget_min),
                       func.max(Order.budget_max), func.count(Order.id))
                .where(Order.parsed_at >= month_ago, Order.category == cat, Order.budget_max.isnot(None))
            )
            row = r.one()
            if row[3] > 0:
                txt += (f"  {get_category_name(cat)}:\n"
                        f"    Средний: **{row[0]:,.0f} ₽**\n"
                        f"    Диапазон: {row[1]:,.0f} – {row[2]:,.0f} ₽\n"
                        f"    Заказов: {row[3]}\n\n")

    if txt.endswith("\n\n"):
        pass
    else:
        txt += "\nЗаполните профиль для персональной карты."

    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown")


@router.callback_query(F.data == "radar:best_time")
async def radar_best_time(cb: CallbackQuery, user: User, session):
    """Лучшее время для откликов."""
    from sqlalchemy import extract
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)

    r = await session.execute(
        select(extract("hour", Order.parsed_at).label("h"), func.count(Order.id))
        .where(Order.parsed_at >= month_ago)
        .group_by("h").order_by(func.count(Order.id).desc()).limit(24)
    )
    hours = [(int(row[0]), row[1]) for row in r.all()]

    txt = "⏰ **Лучшее время для откликов**\n\n"
    if hours:
        top3 = sorted(hours, key=lambda x: x[1], reverse=True)[:3]
        txt += "🏆 Пиковые часы (MSK +3):\n"
        for h, cnt in top3:
            msk = (h + 3) % 24
            bars = "█" * min(cnt // max(1, top3[0][1] // 10), 10)
            txt += f"  {msk:02d}:00 — {cnt} заказов {bars}\n"

        txt += "\n📊 Все часы:\n"
        for h in range(24):
            msk = (h + 3) % 24
            cnt = next((c for hr, c in hours if hr == h), 0)
            bars = "▓" * min(cnt // max(1, top3[0][1] // 8), 8)
            txt += f"  {msk:02d}:00 {bars} {cnt}\n"

    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown")


@router.callback_query(F.data == "radar:ref_link")
async def radar_ref_link(cb: CallbackQuery, user: User):
    bot_me = await cb.bot.me()
    link = f"https://t.me/{bot_me.username}?start=ref_{user.referral_code}"
    await cb.answer()
    await cb.message.answer(f"🔗 Ваша реферальная ссылка:\n\n`{link}`\n\nЗа каждого — +5 AI-кредитов!",
                             parse_mode="Markdown")


@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery):
    await cb.answer()


# ══════════════════════════════════════════════════
# 📈 Персональный рост
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "my_growth")
async def my_growth(cb: CallbackQuery, user: User, session):
    """Персональная статистика роста."""
    from core.models import CRMEntry, Notification

    # CRM-воронка
    total_crm = (await session.execute(
        select(func.count(CRMEntry.id)).where(CRMEntry.user_id == user.id)
    )).scalar() or 0
    taken = (await session.execute(
        select(func.count(CRMEntry.id)).where(
            CRMEntry.user_id == user.id, CRMEntry.status.in_(["taken", "completed"]))
    )).scalar() or 0
    completed = (await session.execute(
        select(func.count(CRMEntry.id)).where(
            CRMEntry.user_id == user.id, CRMEntry.status == "completed")
    )).scalar() or 0

    conv = round(taken / max(total_crm, 1) * 100, 1) if total_crm else 0

    # Средний чек
    avg_r = await session.execute(
        select(func.avg(CRMEntry.price_agreed)).where(
            CRMEntry.user_id == user.id, CRMEntry.price_agreed.isnot(None))
    )
    avg_check = round(avg_r.scalar() or 0)

    # Уведомлений всего
    notifs = (await session.execute(
        select(func.count(Notification.id)).where(Notification.user_id == user.id)
    )).scalar() or 0

    txt = (
        "📈 **Персональный рост**\n\n"
        f"🤖 AI-откликов: {user.total_responses}\n"
        f"⭐ Сохранено: {user.total_saved}\n"
        f"🔔 Уведомлений: {notifs}\n"
        f"🔥 Streak: {user.streak_days} дн.\n\n"
        f"📋 **CRM-воронка:**\n"
        f"  📩 Всего откликов: {total_crm}\n"
        f"  ✅ Взятых: {taken}\n"
        f"  🏁 Завершённых: {completed}\n"
        f"  📊 Конверсия: {conv}%\n\n"
        f"💰 **Заработок:**\n"
        f"  Всего: **{user.earnings_total:,.0f} ₽**\n"
        f"  Средний чек: {avg_check:,.0f} ₽\n"
    )

    if user.reaction_avg_seconds:
        txt += f"\n⚡ Ср. время реакции: {user.reaction_avg_seconds // 60} мин."

    await cb.answer()
    await cb.message.answer(txt, parse_mode="Markdown")
