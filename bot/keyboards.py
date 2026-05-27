"""
Все клавиатуры бота.
Фильтры убраны — подбор по профилю.
"""
from __future__ import annotations
from aiogram.types import (
    InlineKeyboardButton as IKB,
    InlineKeyboardMarkup as IKM,
    ReplyKeyboardMarkup as RKM,
    KeyboardButton as KB,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ══════════════════════════════════════════════════
# Главное меню
# ══════════════════════════════════════════════════

def main_menu(is_admin: bool = False) -> RKM:
    b = ReplyKeyboardBuilder()
    b.row(KB(text="🔍 Заказы"),       KB(text="🤖 AI"))
    b.row(KB(text="📊 Аналитика"),    KB(text="⭐ Избранное"))
    b.row(KB(text="👤 Профиль"),      KB(text="💎 Подписка"))
    b.row(KB(text="📋 Шаблоны"),      KB(text="🔥 Radar"))
    if is_admin:
        b.row(KB(text="🔐 Админка"))
    return b.as_markup(resize_keyboard=True)


# ══════════════════════════════════════════════════
# Карточка заказа
# ══════════════════════════════════════════════════

def order_card(order_id: int, url: str, has_ai: bool = True) -> IKM:
    rows = [[IKB(text="🔗 Открыть", url=url)]]
    if has_ai:
        rows.append([IKB(text="🤖 AI-отклик", callback_data=f"ai_resp:{order_id}"),
                      IKB(text="📊 Скоринг",   callback_data=f"ai_score:{order_id}")])
        rows.append([IKB(text="📝 TL;DR",      callback_data=f"ai_tldr:{order_id}"),
                      IKB(text="🚨 Скам?",      callback_data=f"ai_scam:{order_id}")])
    rows.append([IKB(text="⭐ Сохранить", callback_data=f"save:{order_id}"),
                  IKB(text="🙈 Скрыть",    callback_data=f"hide:{order_id}")])
    rows.append([IKB(text="📊 Шансы?",    callback_data=f"compete:{order_id}"),
                  IKB(text="💰 Цена?",     callback_data=f"ai_price:{order_id}")])
    rows.append([IKB(text="📋 CRM",        callback_data=f"crm:{order_id}")])
    return IKM(inline_keyboard=rows)


# ══════════════════════════════════════════════════
# Категории
# ══════════════════════════════════════════════════

def categories_parent(selected: list[str] | None = None) -> IKM:
    from core.categories import CATEGORIES
    sel = selected or []
    b = InlineKeyboardBuilder()
    for code, (emoji, name, _) in CATEGORIES.items():
        chk = "✅" if code in sel else "⬜"
        b.row(IKB(text=f"{chk} {emoji} {name}", callback_data=f"cat_p:{code}"))
    b.row(IKB(text="▶️ Уточнить подкатегории", callback_data="cat_subs"))
    b.row(IKB(text="✅ Готово", callback_data="cat_done"))
    return b.as_markup()

def categories_sub(parent_code: str, selected: list[str] | None = None) -> IKM:
    from core.categories import get_subcategories
    sel = selected or []
    b = InlineKeyboardBuilder()
    for code, emoji, name in get_subcategories(parent_code):
        chk = "✅" if code in sel else "⬜"
        b.row(IKB(text=f"{chk} {emoji} {name}", callback_data=f"cat_s:{code}"))
    b.row(IKB(text="« Назад", callback_data="cat_back"))
    b.row(IKB(text="✅ Готово", callback_data="cat_done"))
    return b.as_markup()


# ══════════════════════════════════════════════════
# Навыки
# ══════════════════════════════════════════════════

def skills_select(selected: list[str] | None = None, page: int = 0) -> IKM:
    from core.categories import POPULAR_SKILLS
    sel = selected or []
    per_page = 12
    start = page * per_page
    skills_page = POPULAR_SKILLS[start:start+per_page]
    total_pages = (len(POPULAR_SKILLS) + per_page - 1) // per_page
    b = InlineKeyboardBuilder()
    for skill in skills_page:
        chk = "✅" if skill in sel else "⬜"
        b.row(IKB(text=f"{chk} {skill}", callback_data=f"skill_tog:{skill}"))
    nav = []
    if page > 0: nav.append(IKB(text="⬅️", callback_data=f"skill_page:{page-1}"))
    nav.append(IKB(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1: nav.append(IKB(text="➡️", callback_data=f"skill_page:{page+1}"))
    b.row(*nav)
    b.row(IKB(text="✅ Готово", callback_data="skill_done"))
    return b.as_markup()


# ══════════════════════════════════════════════════
# Биржи (для админки)
# ══════════════════════════════════════════════════

EXCHANGES = [("Kwork", "kwork"), ("FL.ru", "fl"), ("Freelance.ru", "freelanceru"), ("Weblancer", "weblancer")]


# ══════════════════════════════════════════════════
# Подписка / CRM / Confirm
# ══════════════════════════════════════════════════

def subscription() -> IKM:
    return IKM(inline_keyboard=[
        [IKB(text="⭐ Pro — 490₽/мес",               callback_data="sub:pro:1")],
        [IKB(text="⭐ Pro 3 мес — 1 250₽ (−15%)",     callback_data="sub:pro:3")],
        [IKB(text="⭐ Pro 12 мес — 3 822₽ (−35%)",    callback_data="sub:pro:12")],
        [IKB(text="💎 Business — 1 490₽/мес",          callback_data="sub:business:1")],
        [IKB(text="💎 Business 3 мес — 3 800₽ (−15%)", callback_data="sub:business:3")],
        [IKB(text="💎 Business 12 мес — 11 622₽ (−35%)", callback_data="sub:business:12")],
    ])

def crm_status(order_id: int) -> IKM:
    return IKM(inline_keyboard=[
        [IKB(text="📩 Откликнулся", callback_data=f"crms:{order_id}:responded")],
        [IKB(text="💬 Переписка",   callback_data=f"crms:{order_id}:negotiation")],
        [IKB(text="✅ Взял",        callback_data=f"crms:{order_id}:taken")],
        [IKB(text="❌ Отказ",       callback_data=f"crms:{order_id}:rejected")],
        [IKB(text="🏁 Завершён",    callback_data=f"crms:{order_id}:completed")],
    ])

def confirm_cancel(ok: str = "confirm", no: str = "cancel") -> IKM:
    return IKM(inline_keyboard=[[
        IKB(text="✅ Подтвердить", callback_data=ok),
        IKB(text="❌ Отмена",      callback_data=no),
    ]])


# ══════════════════════════════════════════════════
# Админ-панель
# ══════════════════════════════════════════════════

def admin_panel() -> IKM:
    return IKM(inline_keyboard=[
        [IKB(text="📊 Статистика",         callback_data="adm:stats")],
        [IKB(text="👥 Пользователи",       callback_data="adm:users")],
        [IKB(text="🔍 Найти пользователя", callback_data="adm:find")],
        [IKB(text="🎁 Выдать подписку",    callback_data="adm:grant")],
        [IKB(text="🏢 Биржи / парсеры",    callback_data="adm:exchanges")],
        [IKB(text="🚀 Парсить всё сейчас", callback_data="adm:parse_all")],
        [IKB(text="📢 Рассылка",           callback_data="adm:broadcast")],
        [IKB(text="🚫 Баны",               callback_data="adm:bans")],
        [IKB(text="💳 Платежи",            callback_data="adm:payments")],
        [IKB(text="📝 Аудит-лог",          callback_data="adm:audit")],
        [IKB(text="🤖 AI-тест",            callback_data="adm:ai_test")],
        [IKB(text="🏆 Достижения",         callback_data="adm:achievements")],
    ])

def admin_user_actions(tg_id: int) -> IKM:
    return IKM(inline_keyboard=[
        [IKB(text="📋 Подробно",        callback_data=f"adm:udet:{tg_id}")],
        [IKB(text="🎁 Выдать подписку", callback_data=f"adm:ugrant:{tg_id}")],
        [IKB(text="🚫 Бан",   callback_data=f"adm:uban:{tg_id}"),
         IKB(text="✅ Разбан", callback_data=f"adm:uunban:{tg_id}")],
        [IKB(text="🔄 Сброс AI",       callback_data=f"adm:ureset_ai:{tg_id}")],
        [IKB(text="👑 +Админ", callback_data=f"adm:umkadm:{tg_id}"),
         IKB(text="👤 −Админ", callback_data=f"adm:urmadm:{tg_id}")],
        [IKB(text="« Назад",           callback_data="adm:users")],
    ])

def admin_exchange(name: str, is_active: bool) -> IKM:
    rows = []
    if is_active: rows.append([IKB(text="⏸ Отключить", callback_data=f"adm:exoff:{name}")])
    else: rows.append([IKB(text="▶️ Включить",  callback_data=f"adm:exon:{name}")])
    rows.append([IKB(text="🚀 Парсить сейчас", callback_data=f"adm:exparse:{name}")])
    rows.append([IKB(text="« Назад", callback_data="adm:exchanges")])
    return IKM(inline_keyboard=rows)
