"""
Kwork — парсим 3 страницы https://kwork.ru/projects?page=N
"""
from __future__ import annotations
import logging, re
from typing import Optional
from bs4 import BeautifulSoup
from parser.base import BaseParser, OrderDTO, extract_budget

logger = logging.getLogger(__name__)


class KworkParser(BaseParser):
    name = "kwork"
    base_url = "https://kwork.ru"

    async def fetch_orders(self) -> list[OrderDTO]:
        orders = []
        seen_ids = set()

        for page in range(1, self.pages_to_parse + 1):
            url = f"https://kwork.ru/projects?page={page}"
            html = await self._get(url)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            page_orders = 0

            for heading in soup.select("h1"):
                link = heading.find("a", href=re.compile(r"/projects/\d+"))
                if not link:
                    continue
                o = self._parse_project(link, heading)
                if o and o.external_id not in seen_ids:
                    seen_ids.add(o.external_id)
                    orders.append(o)
                    page_orders += 1

            logger.debug(f"[kwork] page {page}: {page_orders} orders")
            if page_orders == 0:
                break  # нет заказов — дальше не ходим

        logger.info(f"[kwork] total: {len(orders)} orders from {min(page, self.pages_to_parse)} pages")
        return orders

    def _parse_project(self, link, heading) -> Optional[OrderDTO]:
        try:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not href.startswith("http"):
                href = self.base_url + href
            if not title or not href:
                return None

            m = re.search(r"/projects/(\d+)", href)
            ext_id = m.group(1) if m else href

            # Поднимаемся к карточке
            card = heading
            for _ in range(6):
                card = card.parent
                if card is None:
                    break
                if card.name == "div":
                    break

            text = ""
            budget_min = budget_max = None
            responses = None
            deadline = None

            if card and card.name:
                full = card.get_text(separator="\n", strip=True)
                lines = [l.strip() for l in full.split("\n") if l.strip() and l.strip() != title]

                # Описание — первая строка >50 символов
                for line in lines:
                    if len(line) > 50:
                        text = line; break

                # Бюджет
                for line in lines:
                    bmin, bmax = extract_budget(line)
                    if bmin or bmax:
                        budget_min, budget_max = bmin, bmax; break

                if not budget_min and not budget_max:
                    pm = re.search(r"([\d\s]+)₽", full.replace("\xa0", " "))
                    if pm:
                        val = float(pm.group(1).replace(" ", ""))
                        if val >= 100: budget_max = val

                # Откликов
                rm = re.search(r"Предложений:\s*(\d+)", full)
                if rm: responses = int(rm.group(1))

                # Дедлайн
                dm = re.search(r"Осталось:\s*(.+?)(?:\n|$)", full)
                if dm: deadline = dm.group(1).strip()

            return OrderDTO(
                external_id=str(ext_id), title=title, url=href,
                text=text[:500], budget_min=budget_min, budget_max=budget_max,
                responses_count=responses, deadline=deadline,
                exchange_name=self.name,
            )
        except Exception as e:
            logger.error(f"[kwork] parse: {e}")
            return None
