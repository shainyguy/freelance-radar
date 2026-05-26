"""
Stats API — аналитика рынка для Mini App.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, extract, desc
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_session
from core.models import Order, Exchange

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def overview(days: int = Query(7, ge=1, le=90), session: AsyncSession = Depends(get_session)):
    cutoff = datetime.utcnow() - timedelta(days=days)
    cnt = (await session.execute(select(func.count(Order.id)).where(Order.parsed_at >= cutoff))).scalar() or 0
    avg = (await session.execute(
        select(func.avg(Order.budget_max)).where(Order.parsed_at >= cutoff, Order.budget_max.isnot(None))
    )).scalar() or 0
    r = await session.execute(
        select(Exchange.display_name, func.count(Order.id))
        .join(Exchange).where(Order.parsed_at >= cutoff)
        .group_by(Exchange.display_name)
    )
    by_ex = {row[0]: row[1] for row in r.all()}

    # По дням
    r = await session.execute(
        select(
            func.date(Order.parsed_at).label("day"),
            func.count(Order.id),
        ).where(Order.parsed_at >= cutoff)
        .group_by("day").order_by("day")
    )
    by_day = [{"date": str(row[0]), "count": row[1]} for row in r.all()]

    return {"orders": cnt, "avg_budget": round(avg), "by_exchange": by_ex, "by_day": by_day}


@router.get("/categories")
async def categories_stats(days: int = Query(30, ge=1, le=90), session: AsyncSession = Depends(get_session)):
    """Статистика по категориям."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    r = await session.execute(
        select(Order.category, func.count(Order.id), func.avg(Order.budget_max))
        .where(Order.parsed_at >= cutoff, Order.category.isnot(None))
        .group_by(Order.category)
        .order_by(desc(func.count(Order.id)))
        .limit(20)
    )
    return {"categories": [
        {"code": row[0], "count": row[1], "avg_budget": round(row[2] or 0)}
        for row in r.all()
    ]}


@router.get("/heatmap")
async def heatmap(days: int = Query(30, ge=7, le=90), session: AsyncSession = Depends(get_session)):
    """Тепловая карта: заказы по часам."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    r = await session.execute(
        select(
            extract("hour", Order.parsed_at).label("hour"),
            func.count(Order.id),
        ).where(Order.parsed_at >= cutoff)
        .group_by("hour").order_by("hour")
    )
    return {"hours": {int(row[0]): row[1] for row in r.all()}}


@router.get("/competitiveness")
async def market_competitiveness(
    category: str = Query(None),
    days: int = Query(7, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
):
    """Конкурентоспособность рынка по категории."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = select(
        func.avg(Order.responses_count),
        func.avg(Order.budget_max),
        func.count(Order.id),
    ).where(Order.parsed_at >= cutoff, Order.responses_count.isnot(None))

    if category:
        q = q.where(Order.category == category)

    r = await session.execute(q)
    row = r.one()
    avg_responses = round(row[0] or 0, 1)
    avg_budget = round(row[1] or 0)
    total = row[2]

    return {
        "category": category,
        "avg_responses": avg_responses,
        "avg_budget": avg_budget,
        "total_orders": total,
        "competition_level": "high" if avg_responses > 15 else "medium" if avg_responses > 5 else "low",
    }
