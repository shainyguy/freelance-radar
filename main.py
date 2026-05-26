"""
🚀 Freelance Radar — ЕДИНАЯ ТОЧКА ВХОДА.

python main.py — запускает ВСЁ:
  • Telegram-бот (polling)
  • Парсер бирж (фоновый цикл)
  • Нотификатор (рассылка подходящих заказов)

Работает локально (SQLite) и на Railway (PostgreSQL).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Railway передаёт DATABASE_URL без драйвера — фиксим
_db_url = os.environ.get("DATABASE_URL", "")
if _db_url.startswith("postgres://"):
    os.environ["DATABASE_URL"] = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgresql://") and "+asyncpg" not in _db_url:
    os.environ["DATABASE_URL"] = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("freelance_radar")


# ══════════════════════════════════════════════════
# 1. БД
# ══════════════════════════════════════════════════

async def init_db():
    from core.database import create_tables
    await create_tables()
    logger.info("✅ БД готова")
    from parser.engine import ensure_exchanges
    await ensure_exchanges()


# ══════════════════════════════════════════════════
# 2. ПАРСЕР
# ══════════════════════════════════════════════════

async def parser_loop():
    from parser.engine import parse_all
    while True:
        try:
            await parse_all()
        except Exception as e:
            logger.error(f"Parse error: {e}")
        await asyncio.sleep(settings.PARSE_INTERVAL_SECONDS)


# ══════════════════════════════════════════════════
# 3. НОТИФИКАТОР
# ══════════════════════════════════════════════════

async def notifier_loop(bot):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from core.database import async_session
    from core.models import User, Order, UserFilter, Notification
    from parser.matcher import match_orders_for_user

    while True:
        await asyncio.sleep(settings.PARSE_INTERVAL_SECONDS + 5)
        try:
            async with async_session() as session:
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.PARSE_INTERVAL_SECONDS * 2)
                r = await session.execute(
                    select(Order).options(selectinload(Order.exchange))
                    .where(Order.parsed_at >= cutoff).order_by(Order.parsed_at.desc())
                )
                new_orders = list(r.scalars().all())
                if not new_orders:
                    continue

                r = await session.execute(
                    select(User).options(selectinload(User.filters))
                    .where(User.is_banned == False)
                )
                users = list(r.scalars().all())

                tp = {"business": 0, "pro": 1, "free": 2}
                users.sort(key=lambda u: tp.get(u.tier, 99))

                sent = 0
                for user in users:
                    if user.quiet_hours_start is not None and user.quiet_hours_end is not None:
                        h = datetime.now().hour
                        s, e = user.quiet_hours_start, user.quiet_hours_end
                        if (s <= e and s <= h < e) or (s > e and (h >= s or h < e)):
                            continue

                    lim = settings.get_tier_limits(user.tier)
                    if user.notifications_today >= lim["notifications_per_day"]:
                        continue

                    active_f = [f for f in user.filters if f.is_active]
                    matched = match_orders_for_user(new_orders, active_f, user)
                    if not matched:
                        continue

                    r2 = await session.execute(
                        select(Notification.order_id).where(
                            Notification.user_id == user.id,
                            Notification.order_id.in_([o.id for o in matched]),
                        )
                    )
                    already = {row[0] for row in r2.all()}
                    to_send = [o for o in matched if o.id not in already]

                    delay = lim.get("delay_seconds", 0)
                    if delay > 0:
                        now = datetime.now(timezone.utc)
                        to_send = [o for o in to_send if o.parsed_at and (now - o.parsed_at).total_seconds() >= delay]

                    from bot.keyboards import order_card
                    from core.categories import get_category_name

                    for o in to_send:
                        if user.notifications_today >= lim["notifications_per_day"]:
                            break
                        try:
                            bud = ""
                            if o.budget_min and o.budget_max:
                                bud = f"💰 {o.budget_min:,.0f}–{o.budget_max:,.0f} {o.currency}"
                            elif o.budget_min: bud = f"💰 от {o.budget_min:,.0f}"
                            elif o.budget_max: bud = f"💰 до {o.budget_max:,.0f}"
                            ex_n = o.exchange.display_name if o.exchange else "?"
                            cat_n = get_category_name(o.category) if o.category else ""
                            urgent = "🔴 " if o.is_urgent else ""
                            txt = f"{urgent}📋 **{o.title}**\n🏢 {ex_n}"
                            if cat_n: txt += f" | {cat_n}"
                            if bud: txt += f"\n{bud}"
                            if o.ai_score: txt += f"\n🎯 {o.ai_score}/100"
                            if o.text:
                                txt += f"\n\n{o.text[:200]}{'...' if len(o.text)>200 else ''}"

                            await bot.send_message(
                                user.tg_id, txt, parse_mode="Markdown",
                                reply_markup=order_card(o.id, o.url, user.ai_credits_left > 0),
                            )
                            session.add(Notification(user_id=user.id, order_id=o.id, user_action="sent"))
                            user.notifications_today += 1
                            sent += 1
                        except Exception as e:
                            logger.debug(f"Notify {user.tg_id}: {e}")
                        await asyncio.sleep(0.05)

                await session.commit()
                if sent:
                    logger.info(f"📨 Sent {sent} notifications")
        except Exception as e:
            logger.error(f"Notifier error: {e}")


# ══════════════════════════════════════════════════
# 4. BOT
# ══════════════════════════════════════════════════

def create_bot_and_dp():
    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.fsm.storage.memory import MemoryStorage

    from bot.middlewares import DbUserMiddleware
    from bot.handlers import start, ai_handlers, profile, admin

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(DbUserMiddleware())
    dp.callback_query.middleware(DbUserMiddleware())

    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(ai_handlers.router)
    dp.include_router(profile.router)

    return bot, dp


# ══════════════════════════════════════════════════
# 5. MAIN
# ══════════════════════════════════════════════════

async def main():
    logger.info("🚀 Freelance Radar — запуск...")
    logger.info(f"   DB: {settings.DATABASE_URL[:50]}...")
    logger.info(f"   Парсинг: каждые {settings.PARSE_INTERVAL_SECONDS} сек.")
    logger.info(f"   Админы: {settings.get_admin_ids()}")

    await init_db()

    bot, dp = create_bot_and_dp()

    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="filters", description="Фильтры"),
        BotCommand(command="admin", description="Админка"),
    ])

    asyncio.create_task(parser_loop())
    asyncio.create_task(notifier_loop(bot))

    logger.info("✅ Бот, парсер и нотификатор запущены!")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
