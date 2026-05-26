"""
Middleware — регистрация пользователя, проверка бана, лимиты, streak.
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select

from core.config import settings
from core.database import async_session
from core.models import User

logger = logging.getLogger(__name__)


class DbUserMiddleware(BaseMiddleware):
    """
    Единый middleware: открывает сессию, находит/создаёт юзера,
    проверяет бан, обновляет streak и лимиты.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Message) and event.from_user:
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            tg_user = event.from_user

        if not tg_user:
            return await handler(event, data)

        async with async_session() as session:
            r = await session.execute(select(User).where(User.tg_id == tg_user.id))
            user = r.scalar_one_or_none()

            if not user:
                user = User(
                    tg_id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    last_name=tg_user.last_name,
                    is_admin=settings.is_admin(tg_user.id),
                    tier="business" if settings.is_admin(tg_user.id) else "free",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                logger.info(f"New user: {tg_user.id} (@{tg_user.username})")
            else:
                changed = False
                if user.username != tg_user.username:
                    user.username = tg_user.username; changed = True
                if user.first_name != tg_user.first_name:
                    user.first_name = tg_user.first_name; changed = True
                if settings.is_admin(tg_user.id) and not user.is_admin:
                    user.is_admin = True
                    user.tier = "business"
                    changed = True

                # Бан
                if user.is_banned:
                    if isinstance(event, Message):
                        await event.answer("⛔ Ваш аккаунт заблокирован.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("⛔ Заблокирован", show_alert=True)
                    return

                # Подписка истекла
                now = datetime.now(timezone.utc)
                if user.subscription_until and user.subscription_until < now:
                    if user.tier != "free" and not user.is_admin:
                        user.tier = "free"
                        user.subscription_until = None
                        changed = True

                # Дневные лимиты
                today = str(date.today())
                if user.notifications_reset_date != today:
                    user.notifications_today = 0
                    user.notifications_reset_date = today
                    changed = True

                # AI-кредиты (ежемесячный сброс)
                today_d = date.today()
                if user.ai_credits_reset_date:
                    try:
                        last = date.fromisoformat(user.ai_credits_reset_date)
                        if today_d.month != last.month or today_d.year != last.year:
                            lim = settings.get_tier_limits(user.tier)
                            user.ai_credits_left = lim["ai_credits_per_month"]
                            user.ai_credits_reset_date = str(today_d)
                            changed = True
                    except ValueError:
                        pass
                else:
                    user.ai_credits_reset_date = str(today_d)
                    changed = True

                # Streak
                if user.last_active_date:
                    try:
                        last_d = date.fromisoformat(user.last_active_date)
                        delta = (today_d - last_d).days
                        if delta == 1:
                            user.streak_days += 1; changed = True
                        elif delta > 1:
                            user.streak_days = 1; changed = True
                    except ValueError:
                        user.streak_days = 1; changed = True
                else:
                    user.streak_days = 1; changed = True
                if user.last_active_date != str(today_d):
                    user.last_active_date = str(today_d); changed = True

                if changed:
                    await session.commit()

            data["session"] = session
            data["user"] = user
            data["is_admin"] = user.is_admin
            data["tier_limits"] = settings.get_tier_limits(user.tier)

            return await handler(event, data)
