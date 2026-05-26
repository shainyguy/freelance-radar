"""
GigaChat AI — через Authorization Key (OAuth client_credentials).

В Railway Variables:
  GIGACHAT_AUTH_KEY=MDE5YmUx...base64...
  GIGACHAT_SCOPE=GIGACHAT_API_PERS
"""
from __future__ import annotations
import json, logging, uuid
from typing import Optional
import httpx
from core.config import settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

_access_token: Optional[str] = None


async def _get_token() -> str:
    global _access_token
    if _access_token:
        return _access_token

    auth_key = settings.GIGACHAT_AUTH_KEY
    if not auth_key:
        raise RuntimeError(
            "GIGACHAT_AUTH_KEY не задан! Добавьте в Railway Variables:\n"
            "GIGACHAT_AUTH_KEY = ваш_base64_ключ"
        )

    logger.info("GigaChat: получаю OAuth токен...")

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {auth_key}",
            },
            data={"scope": settings.GIGACHAT_SCOPE},
        )

        if resp.status_code != 200:
            error_text = resp.text[:500]
            logger.error(f"GigaChat OAuth FAILED: {resp.status_code} — {error_text}")
            raise RuntimeError(f"GigaChat OAuth ошибка {resp.status_code}: {error_text}")

        data = resp.json()
        _access_token = data["access_token"]
        logger.info("GigaChat: токен получен ✅")
        return _access_token


async def _chat(system: str, user_msg: str, temperature: float = 0.7) -> str:
    global _access_token

    for attempt in range(2):
        try:
            token = await _get_token()
            async with httpx.AsyncClient(verify=False, timeout=30) as client:
                resp = await client.post(
                    CHAT_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Authorization": f"Bearer {token}",
                    },
                    json={
                        "model": "GigaChat",
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user_msg},
                        ],
                        "temperature": temperature,
                        "max_tokens": 1500,
                    },
                )

                if resp.status_code == 401:
                    logger.warning("GigaChat: токен истёк, обновляю...")
                    _access_token = None
                    continue

                if resp.status_code != 200:
                    error_text = resp.text[:500]
                    logger.error(f"GigaChat API error: {resp.status_code} — {error_text}")
                    raise RuntimeError(f"GigaChat {resp.status_code}: {error_text}")

                return resp.json()["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and attempt == 0:
                _access_token = None
                continue
            raise
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"GigaChat unexpected error: {e}")
            raise RuntimeError(f"GigaChat ошибка: {e}")

    raise RuntimeError("GigaChat: не удалось авторизоваться после 2 попыток")


# ── Публичные функции ─────────────────────────────

async def generate_response(order_title: str, order_text: str,
                             user_profile: str = "", user_skills: str = "",
                             experience_years: int | None = None,
                             response_style: str = "", template: str = "") -> str:
    profile = ""
    if user_profile: profile += f"\nПрофиль: {user_profile}"
    if user_skills:  profile += f"\nНавыки: {user_skills}"
    if experience_years: profile += f"\nОпыт: {experience_years} лет"
    if response_style: profile += f"\nСтиль: {response_style}"
    tmpl = f"\nШаблон:\n{template}" if template else ""
    system = (
        "Ты — помощник фрилансера. Напиши эффективный отклик на заказ.\n"
        "Обращайся на «вы», покажи понимание задачи, кратко опиши опыт, "
        "предложи план, 3-5 абзацев, без штампов.\n" + profile + tmpl
    )
    return await _chat(system, f"Заказ: {order_title}\n\n{order_text}", 0.8)


async def score_order(order_title: str, order_text: str, budget: str = "",
                       client_rating: float | None = None,
                       responses_count: int | None = None) -> dict:
    system = (
        "Оцени фриланс-заказ 0-100. Критерии: чёткость (0-25), бюджет (0-25), "
        "клиент (0-25), прибыльность (0-25).\n"
        'Верни ТОЛЬКО JSON: {"score":75,"breakdown":{"clarity":20,"budget":15,'
        '"client":20,"profit":20},"summary":"...","recommendation":"..."}'
    )
    extra = ""
    if budget: extra += f"\nБюджет: {budget}"
    if client_rating is not None: extra += f"\nРейтинг: {client_rating}"
    if responses_count is not None: extra += f"\nОткликов: {responses_count}"
    raw = await _chat(system, f"Заказ: {order_title}\n{order_text}{extra}", 0.3)
    try: return json.loads(raw)
    except json.JSONDecodeError: return {"score": 50, "summary": raw}


async def summarize_order(order_title: str, order_text: str) -> str:
    return await _chat("TL;DR заказа в 2-3 предложения. Что делать, стек, сроки.",
                        f"{order_title}\n\n{order_text}", 0.3)


async def detect_scam(order_title: str, order_text: str, budget: str = "") -> dict:
    system = (
        "Проанализируй заказ на мошенничество.\n"
        'Верни ТОЛЬКО JSON: {"is_suspicious":false,"risk_level":"low",'
        '"flags":[],"explanation":"..."}'
    )
    extra = f"\nБюджет: {budget}" if budget else ""
    raw = await _chat(system, f"{order_title}\n{order_text}{extra}", 0.2)
    try: return json.loads(raw)
    except: return {"is_suspicious": False, "risk_level": "low", "flags": [], "explanation": raw}


async def negotiate(conversation: str, context: str = "") -> str:
    system = "Эксперт по переговорам на фрилансе. Подскажи ответ заказчику."
    msg = f"Переписка:\n{conversation}"
    if context: msg += f"\n\nКонтекст:\n{context}"
    return await _chat(system, msg, 0.7)


async def estimate_price(order_title: str, order_text: str) -> dict:
    system = (
        "Оцени стоимость задачи на рынке РФ/СНГ.\n"
        'Верни ТОЛЬКО JSON: {"min_price":5000,"max_price":15000,'
        '"recommended_price":10000,"estimated_hours":10,"explanation":"..."}'
    )
    raw = await _chat(system, f"{order_title}\n\n{order_text}", 0.3)
    try: return json.loads(raw)
    except: return {"explanation": raw}


async def ai_test(prompt: str) -> str:
    return await _chat("Ты — полезный ассистент.", prompt, 0.7)
