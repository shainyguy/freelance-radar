"""
📊 Рейтинг конкурентоспособности заказа.

Формула: стоит ли откликаться?
Учитывает: бюджет, кол-во откликов, срочность, AI-скор, возраст заказа.

Результат: "🟢 Высокий / 🟡 Средний / 🔴 Низкий" + число 0-100
"""
from __future__ import annotations
from datetime import datetime, timezone


def calc_competitiveness(
    budget_max: float | None,
    responses_count: int | None,
    is_urgent: bool,
    ai_score: int | None,
    posted_at: datetime | None,
) -> dict:
    """
    Возвращает:
    {
      "score": 78,
      "level": "high",       # high / medium / low
      "emoji": "🟢",
      "factors": {
        "budget_per_response": 85,
        "freshness": 90,
        "urgency_bonus": 10,
        "ai_quality": 70,
      },
      "verdict": "Мало откликов + хороший бюджет. Стоит откликаться!"
    }
    """
    score = 50  # базовый
    factors = {}

    # 1. Бюджет / откликов — ключевой фактор
    # Много денег + мало откликов = отлично
    resp = responses_count or 0
    budget = budget_max or 0

    if budget > 0 and resp >= 0:
        if resp == 0:
            budget_per_resp = 100
        else:
            # ₽ на отклик: чем больше, тем лучше
            ratio = budget / max(resp, 1)
            if ratio >= 5000: budget_per_resp = 100
            elif ratio >= 2000: budget_per_resp = 80
            elif ratio >= 1000: budget_per_resp = 60
            elif ratio >= 500: budget_per_resp = 40
            else: budget_per_resp = 20
        factors["budget_per_response"] = budget_per_resp
        score = budget_per_resp * 0.4 + score * 0.6
    elif resp == 0:
        factors["budget_per_response"] = 90
        score += 15
    elif resp <= 3:
        factors["budget_per_response"] = 70
        score += 5
    elif resp <= 10:
        factors["budget_per_response"] = 50
    elif resp <= 20:
        factors["budget_per_response"] = 30
        score -= 10
    else:
        factors["budget_per_response"] = 10
        score -= 20

    # 2. Свежесть — чем свежее, тем лучше
    if posted_at:
        now = datetime.utcnow()
        age_hours = (now - posted_at).total_seconds() / 3600
        if age_hours <= 1: freshness = 100
        elif age_hours <= 3: freshness = 90
        elif age_hours <= 6: freshness = 75
        elif age_hours <= 12: freshness = 60
        elif age_hours <= 24: freshness = 40
        else: freshness = 20
        factors["freshness"] = freshness
        score = score * 0.7 + freshness * 0.3

    # 3. Срочность — бонус
    if is_urgent:
        factors["urgency_bonus"] = 15
        score += 10

    # 4. AI-качество
    if ai_score is not None:
        factors["ai_quality"] = ai_score
        score = score * 0.8 + ai_score * 0.2

    # Нормализация
    score = max(0, min(100, int(score)))

    # Уровень
    if score >= 70:
        level, emoji = "high", "🟢"
    elif score >= 40:
        level, emoji = "medium", "🟡"
    else:
        level, emoji = "low", "🔴"

    # Вердикт
    verdicts = {
        "high": _high_verdict(resp, budget),
        "medium": "Средние шансы. Подготовь хороший отклик.",
        "low": _low_verdict(resp, budget),
    }

    return {
        "score": score,
        "level": level,
        "emoji": emoji,
        "factors": factors,
        "verdict": verdicts[level],
    }


def _high_verdict(resp: int, budget: float) -> str:
    parts = []
    if resp <= 3: parts.append("Мало откликов")
    if budget >= 10000: parts.append("хороший бюджет")
    parts.append("Стоит откликаться! 🚀")
    return " + ".join(parts) if len(parts) > 1 else parts[0]


def _low_verdict(resp: int, budget: float) -> str:
    parts = []
    if resp >= 20: parts.append("Много конкурентов")
    if budget > 0 and budget < 2000: parts.append("низкий бюджет")
    parts.append("Лучше пропустить или выделиться AI-откликом.")
    return " + ".join(parts) if len(parts) > 1 else parts[0]


def format_competitiveness(data: dict) -> str:
    """Красивый текст для Telegram."""
    txt = f"{data['emoji']} **Конкурентоспособность: {data['score']}/100**\n\n"

    f = data["factors"]
    if "budget_per_response" in f:
        txt += f"💰 Бюджет/откликов: {f['budget_per_response']}/100\n"
    if "freshness" in f:
        txt += f"⏱ Свежесть: {f['freshness']}/100\n"
    if "urgency_bonus" in f:
        txt += f"🔴 Бонус за срочность: +{f['urgency_bonus']}\n"
    if "ai_quality" in f:
        txt += f"🎯 AI-качество: {f['ai_quality']}/100\n"

    txt += f"\n💡 {data['verdict']}"
    return txt
