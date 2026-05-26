"""
YooKassa — создание платежей и обработка вебхуков.
"""
from __future__ import annotations
import logging, uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from core.config import settings, PRICING

logger = logging.getLogger(__name__)


def _configure():
    try:
        from yookassa import Configuration
        Configuration.account_id = settings.YOOKASSA_SHOP_ID
        Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    except Exception as e:
        logger.warning(f"YooKassa config failed: {e}")

_configure()


def create_payment(user_tg_id: int, tier: str, months: int,
                    return_url: str = "https://t.me/FreelanceRadarBot") -> dict:
    from yookassa import Payment as YooPayment
    amount = PRICING.get(tier, {}).get(str(months))
    if not amount:
        raise ValueError(f"Invalid tier/months: {tier}/{months}")

    payment = YooPayment.create({
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": f"Freelance Radar {tier.upper()} — {months} мес.",
        "metadata": {
            "user_tg_id": str(user_tg_id),
            "tier": tier,
            "months": str(months),
        },
    }, uuid.uuid4().hex)

    return {
        "payment_id": payment.id,
        "confirmation_url": payment.confirmation.confirmation_url,
        "amount": amount,
    }


def process_webhook(body: dict) -> Optional[dict]:
    try:
        from yookassa.domain.notification import (
            WebhookNotificationEventType, WebhookNotificationFactory,
        )
        notification = WebhookNotificationFactory().create(body)
        payment = notification.object
        meta = payment.metadata or {}

        if notification.event == WebhookNotificationEventType.PAYMENT_SUCCEEDED:
            return {
                "event": "succeeded",
                "payment_id": payment.id,
                "user_tg_id": int(meta.get("user_tg_id", 0)),
                "tier": meta.get("tier", "pro"),
                "months": int(meta.get("months", 1)),
                "amount": float(payment.amount.value),
            }
        elif notification.event == WebhookNotificationEventType.PAYMENT_CANCELED:
            return {
                "event": "canceled",
                "payment_id": payment.id,
                "user_tg_id": int(meta.get("user_tg_id", 0)),
            }
    except Exception as e:
        logger.exception(f"Webhook error: {e}")
    return None
