"""
Админ-панель — полное управление ботом.
"""
from __future__ import annotations
import asyncio, logging, json
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func, desc

from bot import keyboards as kb
from bot.states import AdminStates
from core.config import settings
from core.models import (
    User, Order, Exchange, Notification, Payment,
    AdminAuditLog, ResponseTemplate, Achievement,
)

logger = logging.getLogger(__name__)
router = Router()


async def _log(session, admin_tg_id, action, target_type=None, target_id=None, details=None):
    session.add(AdminAuditLog(
        admin_tg_id=admin_tg_id, action=action,
        target_type=target_type, target_id=target_id,
        details=json.dumps(details, ensure_ascii=False) if details else None,
    ))
    await session.commit()


# ══════════════════════════════════════════════════
# Вход в админку
# ══════════════════════════════════════════════════

@router.message(F.text == "🔐 Админка")
@router.message(Command("admin"))
async def admin_entry(msg: Message, user: User):
    if not user.is_admin:
        await msg.answer("⛔ Только для админов."); return
    await msg.answer("🔐 **Админ-панель**", parse_mode="Markdown", reply_markup=kb.admin_panel())


# ══════════════════════════════════════════════════
# 📊 Статистика
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:stats")
async def adm_stats(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    now = datetime.utcnow()
    today = now.replace(hour=0,minute=0,second=0,microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_u = (await session.execute(select(func.count(User.id)))).scalar() or 0
    new_today = (await session.execute(select(func.count(User.id)).where(User.created_at >= today))).scalar() or 0
    new_week = (await session.execute(select(func.count(User.id)).where(User.created_at >= week_ago))).scalar() or 0

    r = await session.execute(select(User.tier, func.count(User.id)).group_by(User.tier))
    tiers = {row[0]: row[1] for row in r.all()}

    active_w = (await session.execute(
        select(func.count(User.id)).where(User.last_active_date >= str((now - timedelta(days=7)).date()))
    )).scalar() or 0

    total_o = (await session.execute(select(func.count(Order.id)))).scalar() or 0
    orders_today = (await session.execute(select(func.count(Order.id)).where(Order.parsed_at >= today))).scalar() or 0
    orders_week = (await session.execute(select(func.count(Order.id)).where(Order.parsed_at >= week_ago))).scalar() or 0

    total_n = (await session.execute(select(func.count(Notification.id)))).scalar() or 0
    notif_today = (await session.execute(select(func.count(Notification.id)).where(Notification.sent_at >= today))).scalar() or 0

    rev_month = (await session.execute(
        select(func.sum(Payment.amount)).where(Payment.status == "succeeded", Payment.paid_at >= month_ago)
    )).scalar() or 0
    rev_total = (await session.execute(
        select(func.sum(Payment.amount)).where(Payment.status == "succeeded")
    )).scalar() or 0
    pay_cnt = (await session.execute(
        select(func.count(Payment.id)).where(Payment.status == "succeeded")
    )).scalar() or 0

    banned = (await session.execute(select(func.count(User.id)).where(User.is_banned == True))).scalar() or 0

    r = await session.execute(select(Exchange))
    exchanges = list(r.scalars().all())
    ex_txt = ""
    for e in exchanges:
        st = "🟢" if e.is_active else "🔴"
        last = e.last_parsed_at.strftime("%H:%M:%S") if e.last_parsed_at else "—"
        err = f" ⚠️{e.parse_errors_count}" if e.parse_errors_count else ""
        ex_txt += f"  {st} {e.display_name}: {last}{err}\n"

    txt = (
        "📊 **Статистика**\n\n"
        f"👥 Всего: {total_u}  |  Сегодня: +{new_today}  |  Неделя: +{new_week}\n"
        f"🟢 Активных (7д): {active_w}  |  🚫 Бан: {banned}\n"
        f"📦 Free: {tiers.get('free',0)}  |  Pro: {tiers.get('pro',0)}  |  Biz: {tiers.get('business',0)}\n\n"
        f"📋 Заказов: {total_o}  |  Сегодня: {orders_today}  |  Неделя: {orders_week}\n"
        f"🔔 Уведомлений: {total_n}  |  Сегодня: {notif_today}\n\n"
        f"💰 Платежей: {pay_cnt}  |  Месяц: {rev_month:,.0f}₽  |  Всего: {rev_total:,.0f}₽\n\n"
        f"🏢 Биржи:\n{ex_txt}"
    )
    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown")


# ══════════════════════════════════════════════════
# 👥 Пользователи
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:users")
async def adm_users(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    r = await session.execute(select(User).order_by(desc(User.created_at)).limit(20))
    users = list(r.scalars().all())
    b = InlineKeyboardBuilder()
    for u in users:
        te = {"free":"🆓","pro":"⭐","business":"💎"}.get(u.tier,"")
        ban = "🚫" if u.is_banned else ""
        adm = "👑" if u.is_admin else ""
        nm = u.username or u.first_name or str(u.tg_id)
        b.row(IKB(text=f"{te}{adm}{ban} @{nm}", callback_data=f"adm:udet:{u.tg_id}"))
    b.row(IKB(text="🔍 Поиск", callback_data="adm:find"))
    b.row(IKB(text="« Назад", callback_data="adm:back"))
    await cb.answer()
    await cb.message.answer("👥 **Последние:**", parse_mode="Markdown", reply_markup=b.as_markup())


# ══════════════════════════════════════════════════
# 🔍 Поиск пользователя
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:find")
async def adm_find(cb: CallbackQuery, state: FSMContext, user: User):
    if not user.is_admin: return
    await cb.answer()
    await cb.message.answer("🔍 Введите **Telegram ID** или **@username**:", parse_mode="Markdown")
    await state.set_state(AdminStates.user_lookup)


@router.message(AdminStates.user_lookup)
async def adm_find_proc(msg: Message, state: FSMContext, user: User, session):
    if not user.is_admin: await state.clear(); return
    q = msg.text.strip().lstrip("@")
    try:
        tg_id = int(q)
        r = await session.execute(select(User).where(User.tg_id == tg_id))
    except ValueError:
        r = await session.execute(select(User).where(User.username == q))
    target = r.scalar_one_or_none()
    if not target:
        await msg.answer("❌ Не найден."); await state.clear(); return
    await _show_user(msg, target, session)
    await state.clear()


async def _show_user(event, target: User, session):
    from sqlalchemy import select, func
    from core.models import UserFilter
    fc = (await session.execute(select(func.count(UserFilter.id)).where(UserFilter.user_id == target.id))).scalar() or 0
    nc = (await session.execute(select(func.count(Notification.id)).where(Notification.user_id == target.id))).scalar() or 0
    pc = (await session.execute(select(func.count(Payment.id)).where(Payment.user_id == target.id, Payment.status == "succeeded"))).scalar() or 0
    pt = (await session.execute(select(func.sum(Payment.amount)).where(Payment.user_id == target.id, Payment.status == "succeeded"))).scalar() or 0
    ac = (await session.execute(select(func.count(Achievement.id)).where(Achievement.user_id == target.id))).scalar() or 0

    sub = target.subscription_until.strftime("%d.%m.%Y") if target.subscription_until else "—"

    txt = (
        f"👤 **Пользователь**\n\n"
        f"🆔 `{target.tg_id}`\n"
        f"📛 @{target.username or '—'}\n"
        f"👤 {target.first_name or ''} {target.last_name or ''}\n"
        f"👑 Админ: {'✅' if target.is_admin else '❌'}  |  🚫 Бан: {'✅' if target.is_banned else '❌'}\n\n"
        f"📦 **{target.tier.upper()}**  |  До: {sub}\n"
        f"🤖 AI: {target.ai_credits_left}  |  🔥 {target.streak_days}\n\n"
        f"⚙️ Фильтров: {fc}  |  🔔 Уведомлений: {nc}\n"
        f"💳 Платежей: {pc} ({pt:,.0f}₽)  |  🏆 Ачивок: {ac}\n"
        f"📅 Рег: {target.created_at.strftime('%d.%m.%Y') if target.created_at else '?'}\n"
    )
    if target.profile_skills:
        txt += f"🛠 {target.profile_skills}\n"

    dest = event if isinstance(event, Message) else event.message
    await dest.answer(txt, parse_mode="Markdown", reply_markup=kb.admin_user_actions(target.tg_id))


@router.callback_query(F.data.startswith("adm:udet:"))
async def adm_udet(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    tg_id = int(cb.data.split(":")[2])
    r = await session.execute(select(User).where(User.tg_id == tg_id))
    target = r.scalar_one_or_none()
    if not target: await cb.answer("Не найден", show_alert=True); return
    await cb.answer()
    await _show_user(cb, target, session)


# ══════════════════════════════════════════════════
# 🚫 Бан / Разбан
# ══════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm:uban:"))
async def adm_ban(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    tg_id = int(cb.data.split(":")[2])
    r = await session.execute(select(User).where(User.tg_id == tg_id))
    t = r.scalar_one_or_none()
    if not t: await cb.answer("?", show_alert=True); return
    if t.is_admin: await cb.answer("Нельзя забанить админа!", show_alert=True); return
    t.is_banned = True; await session.commit()
    await _log(session, user.tg_id, "ban", "user", t.id, {"tg_id": tg_id})
    await cb.answer("🚫 Забанен")
    await cb.message.answer(f"🚫 `{tg_id}` забанен.", parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm:uunban:"))
async def adm_unban(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    tg_id = int(cb.data.split(":")[2])
    r = await session.execute(select(User).where(User.tg_id == tg_id))
    t = r.scalar_one_or_none()
    if not t: await cb.answer("?", show_alert=True); return
    t.is_banned = False; await session.commit()
    await _log(session, user.tg_id, "unban", "user", t.id)
    await cb.answer("✅ Разбанен")
    await cb.message.answer(f"✅ `{tg_id}` разбанен.", parse_mode="Markdown")


# ══════════════════════════════════════════════════
# 🎁 Выдать подписку
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:grant")
async def adm_grant_start(cb: CallbackQuery, state: FSMContext, user: User):
    if not user.is_admin: return
    await cb.answer()
    await cb.message.answer("🎁 Введите **Telegram ID**:", parse_mode="Markdown")
    await state.set_state(AdminStates.grant_sub_user_id)


@router.callback_query(F.data.startswith("adm:ugrant:"))
async def adm_grant_direct(cb: CallbackQuery, state: FSMContext, user: User):
    if not user.is_admin: return
    tg_id = int(cb.data.split(":")[2])
    await state.update_data(grant_tg=tg_id)
    await cb.answer()
    await cb.message.answer(
        f"🎁 Тариф для `{tg_id}`:", parse_mode="Markdown",
        reply_markup=IKM(inline_keyboard=[
            [IKB(text="⭐ Pro", callback_data="adm:gt:pro"),
             IKB(text="💎 Business", callback_data="adm:gt:business")],
        ]),
    )
    await state.set_state(AdminStates.grant_sub_tier)


@router.message(AdminStates.grant_sub_user_id)
async def adm_grant_uid(msg: Message, state: FSMContext, user: User):
    if not user.is_admin: await state.clear(); return
    try: tg_id = int(msg.text.strip())
    except ValueError: await msg.answer("❌ Число"); return
    await state.update_data(grant_tg=tg_id)
    await msg.answer(
        f"🎁 Тариф для `{tg_id}`:", parse_mode="Markdown",
        reply_markup=IKM(inline_keyboard=[
            [IKB(text="⭐ Pro", callback_data="adm:gt:pro"),
             IKB(text="💎 Business", callback_data="adm:gt:business")],
        ]),
    )
    await state.set_state(AdminStates.grant_sub_tier)


@router.callback_query(AdminStates.grant_sub_tier, F.data.startswith("adm:gt:"))
async def adm_grant_tier(cb: CallbackQuery, state: FSMContext, user: User):
    if not user.is_admin: return
    tier = cb.data.split(":")[2]
    await state.update_data(grant_tier=tier)
    b = InlineKeyboardBuilder()
    for m in [1,3,6,12,999]:
        label = f"{m} мес." if m < 999 else "♾ Навсегда"
        b.row(IKB(text=label, callback_data=f"adm:gm:{m}"))
    await cb.answer()
    await cb.message.answer(f"📅 Срок **{tier.upper()}**:", parse_mode="Markdown", reply_markup=b.as_markup())
    await state.set_state(AdminStates.grant_sub_months)


@router.callback_query(AdminStates.grant_sub_months, F.data.startswith("adm:gm:"))
async def adm_grant_months(cb: CallbackQuery, state: FSMContext, user: User, session):
    if not user.is_admin: return
    months = int(cb.data.split(":")[2])
    data = await state.get_data()
    tg_id = data["grant_tg"]
    tier = data["grant_tier"]

    r = await session.execute(select(User).where(User.tg_id == tg_id))
    target = r.scalar_one_or_none()
    if not target:
        await cb.answer("Не найден", show_alert=True); await state.clear(); return

    target.tier = tier
    now = datetime.utcnow()
    base = target.subscription_until if target.subscription_until and target.subscription_until > now else now
    if months >= 999:
        target.subscription_until = datetime(2099,12,31)
    else:
        target.subscription_until = base + timedelta(days=months*30)
    lim = settings.get_tier_limits(tier)
    target.ai_credits_left = lim["ai_credits_per_month"]
    await session.commit()
    await _log(session, user.tg_id, "grant_sub", "user", target.id, {"tier":tier,"months":months})

    ms = f"{months} мес." if months < 999 else "навсегда"
    await cb.answer("✅")
    await cb.message.answer(
        f"✅ `{tg_id}` → **{tier.upper()}** {ms}\n"
        f"До: {target.subscription_until.strftime('%d.%m.%Y')}", parse_mode="Markdown")

    # Уведомить
    try:
        bot = cb.bot
        await bot.send_message(tg_id,
            f"🎉 Вам выдана **{tier.upper()}** {ms}!\nAI: {target.ai_credits_left}",
            parse_mode="Markdown")
    except: pass
    await state.clear()


# ══════════════════════════════════════════════════
# 🔄 AI credits reset
# ══════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm:ureset_ai:"))
async def adm_reset_ai(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    tg_id = int(cb.data.split(":")[2])
    r = await session.execute(select(User).where(User.tg_id == tg_id))
    t = r.scalar_one_or_none()
    if not t: await cb.answer("?", show_alert=True); return
    lim = settings.get_tier_limits(t.tier)
    t.ai_credits_left = lim["ai_credits_per_month"]
    await session.commit()
    await _log(session, user.tg_id, "reset_ai", "user", t.id)
    await cb.answer(f"✅ AI → {t.ai_credits_left}")
    await cb.message.answer(f"✅ AI кредиты `{tg_id}` → {t.ai_credits_left}", parse_mode="Markdown")


# ══════════════════════════════════════════════════
# 👑 Админ +/−
# ══════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm:umkadm:"))
async def adm_mkadmin(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    tg_id = int(cb.data.split(":")[2])
    r = await session.execute(select(User).where(User.tg_id == tg_id))
    t = r.scalar_one_or_none()
    if not t: await cb.answer("?", show_alert=True); return
    t.is_admin = True; t.tier = "business"
    t.subscription_until = datetime(2099,12,31)
    lim = settings.get_tier_limits("business")
    t.ai_credits_left = lim["ai_credits_per_month"]
    await session.commit()
    await _log(session, user.tg_id, "make_admin", "user", t.id)
    await cb.answer("👑"); await cb.message.answer(f"👑 `{tg_id}` — админ.", parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm:urmadm:"))
async def adm_rmadmin(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    tg_id = int(cb.data.split(":")[2])
    if tg_id == user.tg_id:
        await cb.answer("Нельзя снять с себя!", show_alert=True); return
    r = await session.execute(select(User).where(User.tg_id == tg_id))
    t = r.scalar_one_or_none()
    if not t: await cb.answer("?", show_alert=True); return
    t.is_admin = False; await session.commit()
    await _log(session, user.tg_id, "remove_admin", "user", t.id)
    await cb.answer("👤"); await cb.message.answer(f"👤 `{tg_id}` — не админ.", parse_mode="Markdown")


# ══════════════════════════════════════════════════
# 🏢 Биржи
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:exchanges")
async def adm_exchanges(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    r = await session.execute(select(Exchange).order_by(Exchange.id))
    exchanges = list(r.scalars().all())
    b = InlineKeyboardBuilder()
    txt = "🏢 **Биржи:**\n\n"
    for e in exchanges:
        st = "🟢" if e.is_active else "🔴"
        last = e.last_parsed_at.strftime("%d.%m %H:%M") if e.last_parsed_at else "—"
        err = f" ⚠️{e.parse_errors_count}" if e.parse_errors_count else ""
        txt += f"{st} **{e.display_name}** — {last}{err}\n"
        b.row(IKB(text=f"{st} {e.display_name}", callback_data=f"adm:exdet:{e.name}"))
    b.row(IKB(text="🚀 Парсить все", callback_data="adm:parse_all"))
    b.row(IKB(text="« Назад", callback_data="adm:back"))
    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm:exdet:"))
async def adm_exdet(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    name = cb.data.split(":")[2]
    r = await session.execute(select(Exchange).where(Exchange.name == name))
    e = r.scalar_one_or_none()
    if not e: await cb.answer("?", show_alert=True); return
    oc = (await session.execute(select(func.count(Order.id)).where(Order.exchange_id == e.id))).scalar() or 0
    today = datetime.utcnow().replace(hour=0,minute=0,second=0,microsecond=0)
    ot = (await session.execute(select(func.count(Order.id)).where(Order.exchange_id == e.id, Order.parsed_at >= today))).scalar() or 0
    txt = (
        f"🏢 **{e.display_name}**\n\n"
        f"{'🟢 Активна' if e.is_active else '🔴 Отключена'}\n"
        f"URL: {e.base_url}\n"
        f"Парсер: {e.parser_class}\n"
        f"Последний парсинг: {e.last_parsed_at.strftime('%d.%m.%Y %H:%M:%S') if e.last_parsed_at else '—'}\n"
        f"Ошибок: {e.parse_errors_count}\n"
        f"Заказов всего: {oc}  |  Сегодня: {ot}"
    )
    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown", reply_markup=kb.admin_exchange(e.name, e.is_active))


@router.callback_query(F.data.startswith("adm:exon:"))
async def adm_exon(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    name = cb.data.split(":")[2]
    r = await session.execute(select(Exchange).where(Exchange.name == name))
    e = r.scalar_one_or_none()
    if e: e.is_active = True; await session.commit()
    await _log(session, user.tg_id, "exchange_on", "exchange", details={"name":name})
    await cb.answer(f"✅ {name} вкл")
    await cb.message.answer(f"✅ **{name}** включена.", parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm:exoff:"))
async def adm_exoff(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    name = cb.data.split(":")[2]
    r = await session.execute(select(Exchange).where(Exchange.name == name))
    e = r.scalar_one_or_none()
    if e: e.is_active = False; await session.commit()
    await _log(session, user.tg_id, "exchange_off", "exchange", details={"name":name})
    await cb.answer(f"🔴 {name} откл")
    await cb.message.answer(f"🔴 **{name}** отключена.", parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm:exparse:"))
async def adm_exparse(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    name = cb.data.split(":")[2]
    await cb.answer("🚀 Запуск...")
    await cb.message.answer(f"🚀 Парсинг **{name}**...", parse_mode="Markdown")
    try:
        from parser.engine import run_parser
        await run_parser(name)
        await cb.message.answer(f"✅ **{name}** готово.", parse_mode="Markdown")
        await _log(session, user.tg_id, "force_parse", details={"exchange":name})
    except Exception as e:
        await cb.message.answer(f"❌ {e}")


@router.callback_query(F.data == "adm:parse_all")
async def adm_parse_all(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    await cb.answer("🚀")
    await cb.message.answer("🚀 Парсинг всех бирж...")
    try:
        from parser.engine import parse_all
        await parse_all()
        await cb.message.answer("✅ Готово.")
        await _log(session, user.tg_id, "force_parse_all")
    except Exception as e:
        await cb.message.answer(f"❌ {e}")


# ══════════════════════════════════════════════════
# 📢 Рассылка
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:broadcast")
async def adm_broadcast(cb: CallbackQuery, state: FSMContext, user: User):
    if not user.is_admin: return
    await cb.answer()
    await cb.message.answer("📢 Введите текст рассылки (Markdown). /cancel — отмена.")
    await state.set_state(AdminStates.broadcast_message)


@router.message(AdminStates.broadcast_message)
async def adm_bc_preview(msg: Message, state: FSMContext, user: User, session):
    if not user.is_admin: await state.clear(); return
    if msg.text == "/cancel": await state.clear(); await msg.answer("❌ Отмена"); return
    await state.update_data(bc_text=msg.text)
    cnt = (await session.execute(select(func.count(User.id)).where(User.is_banned == False))).scalar() or 0
    await msg.answer(
        f"📢 **Превью:**\n\n{msg.text}\n\n───\nПолучат: **{cnt}** чел.\nОтправить?",
        parse_mode="Markdown", reply_markup=kb.confirm_cancel("adm:bc_ok", "adm:bc_no"),
    )
    await state.set_state(AdminStates.broadcast_confirm)


@router.callback_query(AdminStates.broadcast_confirm, F.data == "adm:bc_ok")
async def adm_bc_send(cb: CallbackQuery, state: FSMContext, user: User, session):
    if not user.is_admin: return
    data = await state.get_data()
    text = data.get("bc_text", "")
    r = await session.execute(select(User.tg_id).where(User.is_banned == False))
    ids = [row[0] for row in r.all()]
    await cb.answer("📢 Начинаю...")
    await cb.message.answer(f"📢 Рассылка → {len(ids)} чел...")
    ok = fail = 0
    for tid in ids:
        try:
            await cb.bot.send_message(tid, text, parse_mode="Markdown"); ok += 1
        except: fail += 1
        if (ok + fail) % 30 == 0: await asyncio.sleep(1)
    await _log(session, user.tg_id, "broadcast", details={"ok":ok,"fail":fail,"text":text[:200]})
    await cb.message.answer(f"✅ Доставлено: {ok}  |  ❌ Ошибок: {fail}")
    await state.clear()


@router.callback_query(AdminStates.broadcast_confirm, F.data == "adm:bc_no")
async def adm_bc_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear(); await cb.answer("❌"); await cb.message.answer("❌ Отменено.")


# ══════════════════════════════════════════════════
# 🚫 Баны
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:bans")
async def adm_bans(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    r = await session.execute(select(User).where(User.is_banned == True).limit(20))
    banned = list(r.scalars().all())
    txt = "🚫 **Забаненные:**\n\n"
    b = InlineKeyboardBuilder()
    if not banned: txt += "Нет."
    for u in banned:
        txt += f"🚫 @{u.username or u.tg_id}\n"
        b.row(IKB(text=f"✅ Разбан @{u.username or u.tg_id}", callback_data=f"adm:uunban:{u.tg_id}"))
    b.row(IKB(text="🔍 Забанить по ID", callback_data="adm:find"))
    b.row(IKB(text="« Назад", callback_data="adm:back"))
    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown", reply_markup=b.as_markup())


# ══════════════════════════════════════════════════
# 💳 Платежи
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:payments")
async def adm_payments(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    r = await session.execute(select(Payment).order_by(desc(Payment.created_at)).limit(20))
    pays = list(r.scalars().all())
    txt = "💳 **Платежи:**\n\n"
    if not pays: txt += "Нет."
    else:
        for p in pays:
            se = {"pending":"⏳","succeeded":"✅","canceled":"❌","refunded":"↩️"}.get(p.status,"❓")
            txt += f"{se} #{p.id} | U{p.user_id} | {p.tier.upper()} {p.months}м | {p.amount:,.0f}₽\n"
    tr = (await session.execute(select(func.sum(Payment.amount)).where(Payment.status == "succeeded"))).scalar() or 0
    tc = (await session.execute(select(func.count(Payment.id)).where(Payment.status == "succeeded"))).scalar() or 0
    txt += f"\n───\n💰 Итого: {tc} на {tr:,.0f}₽"
    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown")


# ══════════════════════════════════════════════════
# 📝 Аудит-лог
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:audit")
async def adm_audit(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    r = await session.execute(select(AdminAuditLog).order_by(desc(AdminAuditLog.created_at)).limit(20))
    logs = list(r.scalars().all())
    txt = "📝 **Аудит-лог:**\n\n"
    if not logs: txt += "Пусто."
    else:
        for l in logs:
            d = f" | {l.details[:80]}" if l.details else ""
            txt += f"🕐 {l.created_at.strftime('%d.%m %H:%M') if l.created_at else '?'} | {l.admin_tg_id} | `{l.action}`{d}\n"
    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown")


# ══════════════════════════════════════════════════
# 🤖 AI-тест
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:ai_test")
async def adm_ai(cb: CallbackQuery, state: FSMContext, user: User):
    if not user.is_admin: return
    await cb.answer()
    await cb.message.answer("🤖 **AI-тест** — пишите промпт. /cancel — выход.", parse_mode="Markdown")
    await state.set_state(AdminStates.ai_prompt)


@router.message(AdminStates.ai_prompt)
async def adm_ai_proc(msg: Message, state: FSMContext, user: User):
    if not user.is_admin: await state.clear(); return
    if msg.text == "/cancel": await state.clear(); await msg.answer("Выход."); return
    await msg.answer("⏳...")
    try:
        from core.gigachat_client import ai_test
        resp = ai_test(msg.text)
        await msg.answer(f"🤖 **GigaChat:**\n\n{resp}", parse_mode="Markdown")
    except Exception as e:
        await msg.answer(f"❌ {e}")
    await msg.answer("Ещё промпт или /cancel")


# ══════════════════════════════════════════════════
# 🗄 Шаблоны публичные
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:templates")
async def adm_templates(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    r = await session.execute(select(ResponseTemplate).where(ResponseTemplate.is_public == True))
    tmpls = list(r.scalars().all())
    txt = "🗄 **Публичные шаблоны:**\n\n"
    b = InlineKeyboardBuilder()
    if not tmpls: txt += "Нет."
    else:
        for t in tmpls:
            txt += f"📋 **{t.title}** (исп: {t.usage_count})\n  {t.text[:80]}...\n\n"
            b.row(IKB(text=f"🗑 {t.title}", callback_data=f"adm:tdel:{t.id}"))
    b.row(IKB(text="« Назад", callback_data="adm:back"))
    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("adm:tdel:"))
async def adm_tdel(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    tid = int(cb.data.split(":")[2])
    r = await session.execute(select(ResponseTemplate).where(ResponseTemplate.id == tid))
    t = r.scalar_one_or_none()
    if t:
        await session.delete(t); await session.commit()
        await _log(session, user.tg_id, "del_template", "template", tid)
        await cb.answer("🗑 Удалён")
    else:
        await cb.answer("?", show_alert=True)


# ══════════════════════════════════════════════════
# 🏆 Достижения
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:achievements")
async def adm_ach(cb: CallbackQuery, user: User, session):
    if not user.is_admin: return
    r = await session.execute(
        select(Achievement.code, func.count(Achievement.id)).group_by(Achievement.code).order_by(desc(func.count(Achievement.id)))
    )
    rows = r.all()
    names = {"first_response":"🎯 Первый отклик","10_responses_day":"⚡ 10/день",
             "ai_master":"🤖 AI-мастер","streak_7":"🔥 Неделя","streak_30":"🔥 Месяц",
             "saved_50":"⭐ Коллекционер","pro_subscriber":"💎 Pro"}
    txt = "🏆 **Достижения:**\n\n"
    if not rows: txt += "Ни у кого нет."
    else:
        for code, cnt in rows:
            txt += f"  {names.get(code, code)}: {cnt} чел.\n"
    await cb.answer(); await cb.message.answer(txt, parse_mode="Markdown")


# ══════════════════════════════════════════════════
# Навигация
# ══════════════════════════════════════════════════

@router.callback_query(F.data == "adm:back")
async def adm_back(cb: CallbackQuery, user: User):
    if not user.is_admin: return
    await cb.answer()
    await cb.message.answer("🔐 **Админ-панель**", parse_mode="Markdown", reply_markup=kb.admin_panel())


@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery):
    await cb.answer()
