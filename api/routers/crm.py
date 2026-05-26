"""
CRM API — для Mini App.
Список заказов с статусами, заработок, воронка.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from core.database import get_session
from core.models import User, CRMEntry, Order, Exchange

router = APIRouter(prefix="/crm", tags=["crm"])


async def _get_user(tg_id: int, session: AsyncSession) -> User:
    r = await session.execute(select(User).where(User.tg_id == tg_id))
    user = r.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    return user


@router.get("/entries")
async def crm_entries(
    tg_id: int = Query(...),
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """Все CRM-записи пользователя."""
    user = await _get_user(tg_id, session)

    q = (
        select(CRMEntry)
        .where(CRMEntry.user_id == user.id)
        .options(selectinload(CRMEntry.order).selectinload(Order.exchange))
        .order_by(desc(CRMEntry.updated_at))
    )
    if status:
        q = q.where(CRMEntry.status == status)

    total = (await session.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar() or 0

    q = q.offset((page - 1) * per_page).limit(per_page)
    entries = list((await session.execute(q)).scalars().all())

    return {
        "total": total,
        "page": page,
        "items": [{
            "id": e.id,
            "status": e.status,
            "price_agreed": e.price_agreed,
            "notes": e.notes,
            "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            "order": {
                "id": e.order.id,
                "title": e.order.title,
                "url": e.order.url,
                "budget_min": e.order.budget_min,
                "budget_max": e.order.budget_max,
                "exchange": e.order.exchange.display_name if e.order.exchange else None,
                "category": e.order.category,
            } if e.order else None,
        } for e in entries],
    }


@router.get("/funnel")
async def crm_funnel(
    tg_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Воронка: сколько на каждом этапе."""
    user = await _get_user(tg_id, session)
    r = await session.execute(
        select(CRMEntry.status, func.count(CRMEntry.id))
        .where(CRMEntry.user_id == user.id)
        .group_by(CRMEntry.status)
    )
    funnel = {row[0]: row[1] for row in r.all()}
    return {
        "responded": funnel.get("responded", 0),
        "negotiation": funnel.get("negotiation", 0),
        "taken": funnel.get("taken", 0),
        "completed": funnel.get("completed", 0),
        "rejected": funnel.get("rejected", 0),
        "total": sum(funnel.values()),
    }


@router.get("/earnings")
async def crm_earnings(
    tg_id: int = Query(...),
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    """Заработок по периодам."""
    user = await _get_user(tg_id, session)
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Общий заработок
    total = user.earnings_total or 0

    # За период
    r = await session.execute(
        select(func.sum(CRMEntry.price_agreed))
        .where(
            CRMEntry.user_id == user.id,
            CRMEntry.status.in_(["taken", "completed"]),
            CRMEntry.price_agreed.isnot(None),
            CRMEntry.updated_at >= cutoff,
        )
    )
    period_earnings = r.scalar() or 0

    # По месяцам
    r = await session.execute(
        select(
            func.strftime("%Y-%m", CRMEntry.updated_at).label("month"),
            func.sum(CRMEntry.price_agreed),
            func.count(CRMEntry.id),
        )
        .where(
            CRMEntry.user_id == user.id,
            CRMEntry.status.in_(["taken", "completed"]),
            CRMEntry.price_agreed.isnot(None),
        )
        .group_by("month")
        .order_by(desc("month"))
        .limit(12)
    )
    by_month = [{"month": row[0], "earnings": row[1], "orders": row[2]} for row in r.all()]

    return {
        "total": total,
        "period_days": days,
        "period_earnings": period_earnings,
        "by_month": by_month,
    }


@router.get("/growth")
async def crm_growth(
    tg_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """📈 Персональный рост — сводная статистика."""
    user = await _get_user(tg_id, session)

    # Конверсия: откликов → взятых
    total_crm = (await session.execute(
        select(func.count(CRMEntry.id)).where(CRMEntry.user_id == user.id)
    )).scalar() or 0
    taken = (await session.execute(
        select(func.count(CRMEntry.id)).where(CRMEntry.user_id == user.id, CRMEntry.status.in_(["taken", "completed"]))
    )).scalar() or 0
    completed = (await session.execute(
        select(func.count(CRMEntry.id)).where(CRMEntry.user_id == user.id, CRMEntry.status == "completed")
    )).scalar() or 0

    conversion = round(taken / max(total_crm, 1) * 100, 1)

    # Средний чек
    r = await session.execute(
        select(func.avg(CRMEntry.price_agreed))
        .where(CRMEntry.user_id == user.id, CRMEntry.price_agreed.isnot(None))
    )
    avg_check = round(r.scalar() or 0)

    return {
        "user": {
            "tg_id": user.tg_id,
            "username": user.username,
            "tier": user.tier,
            "streak_days": user.streak_days,
            "ai_credits_left": user.ai_credits_left,
            "total_responses": user.total_responses,
            "total_saved": user.total_saved,
            "earnings_total": user.earnings_total,
            "profile_skills": user.profile_skills,
            "profile_categories": user.profile_categories,
        },
        "crm": {
            "total_entries": total_crm,
            "taken": taken,
            "completed": completed,
            "conversion_pct": conversion,
            "avg_check": avg_check,
        },
    }
