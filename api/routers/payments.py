"""
YooKassa webhook — обработка платежей.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request
from sqlalchemy import select
from core.config import settings
from core.database import async_session
from core.models import User, Payment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook")
async def yookassa_webhook(request: Request):
    body = await request.json()
    from core.yookassa_client import process_webhook
    result = process_webhook(body)
    if not result: return {"ok": True}

    if result["event"] == "succeeded":
        async with async_session() as session:
            r = await session.execute(select(Payment).where(Payment.yookassa_payment_id == result["payment_id"]))
            pay = r.scalar_one_or_none()
            if pay:
                pay.status = "succeeded"
                pay.paid_at = datetime.utcnow()
            r = await session.execute(select(User).where(User.tg_id == result["user_tg_id"]))
            user = r.scalar_one_or_none()
            if user:
                user.tier = result["tier"]
                now = datetime.utcnow()
                base = user.subscription_until if user.subscription_until and user.subscription_until > now else now
                user.subscription_until = base + timedelta(days=result["months"] * 30)
                lim = settings.get_tier_limits(result["tier"])
                user.ai_credits_left = lim["ai_credits_per_month"]
            await session.commit()

    elif result["event"] == "canceled":
        async with async_session() as session:
            r = await session.execute(select(Payment).where(Payment.yookassa_payment_id == result["payment_id"]))
            pay = r.scalar_one_or_none()
            if pay:
                pay.status = "canceled"
                await session.commit()

    return {"ok": True}
