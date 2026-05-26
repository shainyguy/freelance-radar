"""
Базовый парсер — интерфейс + утилиты.
Поддержка мульти-страничного парсинга.
"""
from __future__ import annotations
import hashlib, logging, random, re, time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import httpx
from fake_useragent import UserAgent
from core.config import settings

logger = logging.getLogger(__name__)
ua = UserAgent(fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")


@dataclass
class OrderDTO:
    external_id: str
    title: str
    url: str
    text: str = ""
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: str = "RUB"
    category: Optional[str] = None
    tags: Optional[str] = None
    client_name: Optional[str] = None
    client_rating: Optional[float] = None
    client_reviews_count: Optional[int] = None
    responses_count: Optional[int] = None
    posted_at: Optional[datetime] = None
    exchange_name: str = ""
    deadline: Optional[str] = None

    @property
    def hash(self) -> str:
        content = f"{self.title}|{self.budget_min}|{self.budget_max}|{self.text[:200]}"
        return hashlib.sha256(content.encode()).hexdigest()


def extract_budget(text: str):
    """Извлечь бюджет из текста → (min, max)."""
    if not text:
        return None, None
    text = text.replace("\xa0", "").replace(" ", "").lower()

    m = re.search(r"(\d+)[–\-−](\d+)", text)
    if m: return float(m.group(1)), float(m.group(2))

    m = re.search(r"от(\d+).*?до(\d+)", text)
    if m: return float(m.group(1)), float(m.group(2))

    m = re.search(r"от\s*(\d+)", text)
    if m: return float(m.group(1)), None

    m = re.search(r"до\s*(\d+)", text)
    if m: return None, float(m.group(1))

    m = re.search(r"(\d{3,})\s*(?:руб|₽|rub)", text)
    if m:
        v = float(m.group(1))
        return v, v

    return None, None


class BaseParser(ABC):
    name: str = ""
    base_url: str = ""
    pages_to_parse: int = 3  # парсим 3 страницы

    def __init__(self):
        self._last_req: float = 0

    def _headers(self) -> dict:
        return {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5",
        }

    def _proxy(self) -> Optional[str]:
        proxies = settings.get_proxies()
        return random.choice(proxies) if proxies else None

    async def _delay(self):
        import asyncio
        now = time.monotonic()
        elapsed = now - self._last_req
        if elapsed < 2.0:
            await asyncio.sleep(random.uniform(2.0, 4.0) - elapsed)
        self._last_req = time.monotonic()

    async def _get(self, url: str) -> Optional[str]:
        await self._delay()
        proxy = self._proxy()
        try:
            async with httpx.AsyncClient(
                proxy=proxy, follow_redirects=True, timeout=30,
            ) as client:
                r = await client.get(url, headers=self._headers())
                r.raise_for_status()
                return r.text
        except Exception as e:
            logger.error(f"[{self.name}] GET {url}: {e}")
            return None

    @abstractmethod
    async def fetch_orders(self) -> list[OrderDTO]:
        ...

    def _get_page_urls(self, base_url: str) -> list[str]:
        """Переопределяется в парсерах для генерации URL страниц."""
        return [base_url]
