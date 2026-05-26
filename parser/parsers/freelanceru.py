"""
Freelance.ru — парсим 3 страницы https://freelance.ru/project/search/page/N
"""
from __future__ import annotations
import logging, re
from typing import Optional
from bs4 import BeautifulSoup
from parser.base import BaseParser, OrderDTO, extract_budget

logger = logging.getLogger(__name__)


class FreelanceRuParser(BaseParser):
    name = "freelanceru"
    base_url = "https://freelance.ru"

    async def fetch_orders(self) -> list[OrderDTO]:
        orders = []
        seen_ids = set()

        for page in range(1, self.pages_to_parse + 1):
            url = f"https://freelance.ru/project/search/page/{page}"
            html = await self._get(url)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            page_orders = 0

            for link in soup.find_all("a", href=re.compile(r"/projects/.*\.html$")):
                title = link.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                o = self._parse_project(link)
                if o and o.external_id not in seen_ids:
                    seen_ids.add(o.external_id)
                    orders.append(o)
                    page_orders += 1

            logger.debug(f"[freelance.ru] page {page}: {page_orders} orders")
            if page_orders == 0:
                break

        logger.info(f"[freelance.ru] total: {len(orders)} orders")
        return orders

    def _parse_project(self, link) -> Optional[OrderDTO]:
        try:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href and not href.startswith("http"):
                href = self.base_url + href
            if not title or not href:
                return None

            m = re.search(r"-(\d+)\.html", href)
            ext_id = m.group(1) if m else href

            # Описание из title атрибута или следующего блока
            text = link.get("title", "") or ""

            # Ищем контейнер
            parent = link.parent
            if parent:
                parent = parent.parent or parent

            budget_min = budget_max = None
            category = None

            if parent:
                full = parent.get_text(separator="\n", strip=True)
                # Бюджет
                pm = re.search(r"([\d\s]+)\s*(?:Руб|руб|₽)", full.replace("\xa0", " "))
                if pm:
                    val = float(pm.group(1).replace(" ", ""))
                    if val >= 100:
                        budget_min = val; budget_max = val

                # Категория — жирный текст
                bold = parent.find("b") or parent.find("strong")
                if bold:
                    cat_text = bold.get_text(strip=True)
                    if cat_text and len(cat_text) < 60 and cat_text != title:
                        category = cat_text

            return OrderDTO(
                external_id=str(ext_id), title=title, url=href,
                text=text[:500], budget_min=budget_min, budget_max=budget_max,
                category=category, exchange_name=self.name,
            )
        except Exception as e:
            logger.error(f"[freelance.ru] parse: {e}")
            return None
