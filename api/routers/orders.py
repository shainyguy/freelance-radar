"""
Orders API — для Mini App.
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from core.database import get_session
from core.models import Order, Exchange

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/")
async def list_orders(
    exchange: Optional[str] = None,
    search: Optional[str] = None,
    min_budget: Optional[float] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    q = select(Order).options(selectinload(Order.exchange)).order_by(desc(Order.parsed_at))
    if exchange: q = q.join(Exchange).where(Exchange.name == exchange)
    if min_budget: q = q.where((Order.budget_max >= min_budget) | (Order.budget_min >= min_budget))
    if search: q = q.where(Order.title.ilike(f"%{search}%") | Order.text.ilike(f"%{search}%"))
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.offset((page-1)*per_page).limit(per_page)
    orders = list((await session.execute(q)).scalars().all())
    return {
        "total": total, "page": page, "pages": (total+per_page-1)//per_page,
        "items": [{
            "id": o.id, "title": o.title, "url": o.url,
            "budget_min": o.budget_min, "budget_max": o.budget_max,
            "exchange": o.exchange.display_name if o.exchange else None,
            "ai_score": o.ai_score, "category": o.category,
            "parsed_at": o.parsed_at.isoformat() if o.parsed_at else None,
        } for o in orders],
    }
