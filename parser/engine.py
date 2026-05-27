"""
Движок парсинга — 4 биржи: Kwork, FL.ru, Freelance.ru, Weblancer.
"""
from __future__ import annotations
import logging
from datetime import datetime
from sqlalchemy import select
from core.database import async_session
from core.models import Exchange, Order
from core.categories import map_exchange_category
from parser.base import OrderDTO
from parser.parsers.kwork import KworkParser
from parser.parsers.flru import FLRuParser
from parser.parsers.freelanceru import FreelanceRuParser
from parser.parsers.weblancer import WeblancerParser

logger = logging.getLogger(__name__)

PARSERS = {
    "kwork":      KworkParser,
    "fl":         FLRuParser,
    "freelanceru": FreelanceRuParser,
    "weblancer":  WeblancerParser,
}

EXCHANGES_INIT = [
    ("kwork",      "Kwork",          "https://kwork.ru",         "KworkParser"),
    ("fl",         "FL.ru",          "https://www.fl.ru",        "FLRuParser"),
    ("freelanceru","Freelance.ru",   "https://freelance.ru",     "FreelanceRuParser"),
    ("weblancer",  "Weblancer",      "https://www.weblancer.net","WeblancerParser"),
]


def _now():
    return datetime.utcnow()


async def ensure_exchanges():
    async with async_session() as session:
        for name, display, url, cls in EXCHANGES_INIT:
            r = await session.execute(select(Exchange).where(Exchange.name == name))
            if not r.scalar_one_or_none():
                session.add(Exchange(name=name, display_name=display,
                                     base_url=url, parser_class=cls, is_active=True))
        await session.commit()
    logger.info("Exchanges: " + ", ".join(n for n, _, _, _ in EXCHANGES_INIT))


async def save_orders(exchange_name: str, dtos: list[OrderDTO]) -> int:
    if not dtos: return 0
    new = 0
    async with async_session() as session:
        r = await session.execute(select(Exchange).where(Exchange.name == exchange_name))
        exchange = r.scalar_one_or_none()
        if not exchange: return 0

        for dto in dtos:
            r = await session.execute(select(Order).where(Order.hash == dto.hash))
            if r.scalar_one_or_none(): continue
            r = await session.execute(select(Order).where(
                Order.exchange_id == exchange.id, Order.external_id == dto.external_id))
            if r.scalar_one_or_none(): continue

            mapped_cat = map_exchange_category(dto.category) if dto.category else None
            full_text = f"{dto.title} {dto.text}".lower()
            is_urgent = any(w in full_text for w in ["срочно", "urgent", "asap", "сегодня"])

            posted = dto.posted_at
            if posted and posted.tzinfo is not None:
                posted = posted.replace(tzinfo=None)

            session.add(Order(
                exchange_id=exchange.id, external_id=dto.external_id,
                title=dto.title, text=dto.text, url=dto.url,
                budget_min=dto.budget_min, budget_max=dto.budget_max,
                currency=dto.currency,
                category=mapped_cat, category_raw=dto.category,
                tags_str=dto.tags, client_name=dto.client_name,
                client_rating=dto.client_rating,
                client_reviews_count=dto.client_reviews_count,
                responses_count=dto.responses_count,
                posted_at=posted, hash=dto.hash,
                is_urgent=is_urgent,
                deadline=dto.deadline,
                parsed_at=_now(),
            ))
            new += 1

        exchange.last_parsed_at = _now()
        exchange.parse_errors_count = 0
        await session.commit()
    return new


async def run_parser(exchange_name: str):
    cls = PARSERS.get(exchange_name)
    if not cls: return
    async with async_session() as session:
        r = await session.execute(select(Exchange).where(Exchange.name == exchange_name))
        ex = r.scalar_one_or_none()
        if not ex or not ex.is_active: return

    parser = cls()
    logger.info(f"[{exchange_name}] parsing...")
    try:
        dtos = await parser.fetch_orders()
        new = await save_orders(exchange_name, dtos)
        logger.info(f"[{exchange_name}] found={len(dtos)}, new={new}")
    except Exception as e:
        logger.error(f"[{exchange_name}] error: {e}")
        async with async_session() as session:
            r = await session.execute(select(Exchange).where(Exchange.name == exchange_name))
            ex = r.scalar_one_or_none()
            if ex: ex.parse_errors_count += 1; await session.commit()


async def parse_all():
    logger.info("=== parse cycle ===")
    for name in PARSERS:
        try: await run_parser(name)
        except Exception as e: logger.error(f"{name}: {e}")
    logger.info("=== done ===")
