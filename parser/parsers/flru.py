"""
FL.ru — парсим 3 страницы https://www.fl.ru/projects/?page=N
"""
from __future__ import annotations
import logging, re
from typing import Optional
from bs4 import BeautifulSoup
from parser.base import BaseParser, OrderDTO, extract_budget

logger = logging.getLogger(__name__)


class FLRuParser(BaseParser):
    name = "fl"
    base_url = "https://www.fl.ru"

    async def fetch_orders(self) -> list[OrderDTO]:
        orders = []
        seen_ids = set()

        for page in range(1, self.pages_to_parse + 1):
            url = f"https://www.fl.ru/projects/?page={page}"
            html = await self._get(url)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            page_orders = 0

            for h2 in soup.find_all("h2"):
                link = h2.find("a", href=re.compile(r"/projects/\d+"))
                if not link:
                    continue
                o = self._parse_project(link, h2)
                if o and o.external_id not in seen_ids:
                    seen_ids.add(o.external_id)
                    orders.append(o)
                    page_orders += 1

            logger.debug(f"[fl.ru] page {page}: {page_orders} orders")
            if page_orders == 0:
                break

        logger.info(f"[fl.ru] total: {len(orders)} orders")
        return orders

    def _parse_project(self, link, h2) -> Optional[OrderDTO]:
        try:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href and not href.startswith("http"):
                href = self.base_url + href
            if not title or not href:
                return None

            m = re.search(r"/projects/(\d+)/", href)
            ext_id = m.group(1) if m else href

            container = h2.parent or h2
            full_text = container.get_text(separator="\n", strip=True)
            lines = [l.strip() for l in full_text.split("\n") if l.strip() and l.strip() != title]

            text = ""
            for line in lines:
                if len(line) > 30:
                    text = line; break

            budget_min = budget_max = None
            for line in lines:
                bmin, bmax = extract_budget(line)
                if bmin or bmax:
                    budget_min, budget_max = bmin, bmax; break

            if not budget_min and not budget_max:
                pm = re.search(r"([\d\s]+)\s*(?:руб|₽)", full_text.replace("\xa0", " "))
                if pm:
                    val = float(pm.group(1).replace(" ", ""))
                    if val >= 100: budget_min = val; budget_max = val

            responses = None
            rm = re.search(r"(\d+)\s*(?:ответ|отклик)", full_text.lower())
            if rm: responses = int(rm.group(1))

            category = None
            # FL.ru показывает категорию — ищем ссылки /projects/category/
            cat_link = container.find("a", href=re.compile(r"/projects/category/"))
            if cat_link:
                category = cat_link.get_text(strip=True)

            return OrderDTO(
                external_id=str(ext_id), title=title, url=href,
                text=text[:500], budget_min=budget_min, budget_max=budget_max,
                category=category, responses_count=responses,
                exchange_name=self.name,
            )
        except Exception as e:
            logger.error(f"[fl.ru] parse: {e}")
            return None
