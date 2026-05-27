"""
Weblancer.net — парсим 3 страницы.
URL: https://www.weblancer.net/jobs/?page=N
"""
from __future__ import annotations
import logging, re
from typing import Optional
from bs4 import BeautifulSoup
from parser.base import BaseParser, OrderDTO, extract_budget

logger = logging.getLogger(__name__)


class WeblancerParser(BaseParser):
    name = "weblancer"
    base_url = "https://www.weblancer.net"

    async def fetch_orders(self) -> list[OrderDTO]:
        orders = []
        seen = set()

        for page in range(1, self.pages_to_parse + 1):
            url = f"https://www.weblancer.net/jobs/?page={page}"
            html = await self._get(url)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            page_orders = 0

            # Заголовки заказов: h2 > a[href*="/jobs/"]
            for h2 in soup.find_all("h2"):
                link = h2.find("a", href=re.compile(r"/freelance/.*\d+/$|/jobs/"))
                if not link:
                    continue
                o = self._parse_project(link, h2)
                if o and o.external_id not in seen:
                    seen.add(o.external_id)
                    orders.append(o)
                    page_orders += 1

            logger.debug(f"[weblancer] page {page}: {page_orders}")
            if page_orders == 0:
                break

        logger.info(f"[weblancer] total: {len(orders)} orders")
        return orders

    def _parse_project(self, link, h2) -> Optional[OrderDTO]:
        try:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href and not href.startswith("http"):
                href = self.base_url + href
            if not title or not href or len(title) < 5:
                return None

            # ID из URL: ...-1267056/
            m = re.search(r"-(\d+)/?$", href)
            ext_id = m.group(1) if m else href

            container = h2.parent or h2
            full = container.get_text(separator="\n", strip=True)
            lines = [l.strip() for l in full.split("\n") if l.strip() and l.strip() != title]

            # Описание
            text = ""
            for line in lines:
                if len(line) > 30 and not re.match(r"^\d", line):
                    text = line
                    break

            # Бюджет: "6500 $" или "2 $"
            budget_min = budget_max = None
            for line in lines:
                pm = re.match(r"^([\d\s]+)\s*\$", line.replace("\xa0", " "))
                if pm:
                    num = pm.group(1).replace(" ", "")
                    if num.isdigit():
                        val = float(num) * 90  # USD → RUB примерно
                        budget_min = val
                        budget_max = val
                        break
                bmin, bmax = extract_budget(line)
                if bmin or bmax:
                    budget_min, budget_max = bmin, bmax
                    break

            # Теги как категория
            tags = []
            for tag_link in container.find_all("a", href=re.compile(r"/freelance/[^/]+/$")):
                t = tag_link.get_text(strip=True)
                if t and len(t) < 30:
                    tags.append(t)

            category = tags[0] if tags else None

            return OrderDTO(
                external_id=str(ext_id), title=title, url=href,
                text=text[:500], budget_min=budget_min, budget_max=budget_max,
                category=category, tags=",".join(tags) if tags else None,
                exchange_name=self.name,
            )
        except Exception as e:
            logger.error(f"[weblancer] parse: {e}")
            return None
