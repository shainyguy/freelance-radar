"""
Матчинг заказов по фильтрам пользователей.
+ Профильный автоподбор: если у юзера нет фильтров, но есть профиль —
  матчим по категориям и навыкам из профиля.
"""
from __future__ import annotations
from core.models import Order, UserFilter, User


def order_matches_filter(order: Order, f: UserFilter) -> bool:
    # Биржа
    ex_list = f.exchanges_list
    if ex_list:
        ex_name = order.exchange.name if order.exchange else ""
        if ex_name not in ex_list:
            return False

    # Категории
    cat_list = f.categories_list
    if cat_list and order.category:
        if order.category not in cat_list:
            # Проверяем родительскую: "dev_web" → "dev"
            parent = order.category.split("_")[0] if "_" in order.category else None
            if parent not in cat_list:
                return False

    # Только срочные
    if f.only_urgent and not order.is_urgent:
        return False

    # Бюджет (мин)
    if f.min_budget is not None:
        order_budget = order.budget_max or order.budget_min
        if order_budget is not None and order_budget < f.min_budget:
            return False

    # Бюджет (макс)
    if f.max_budget is not None:
        order_budget = order.budget_min or order.budget_max
        if order_budget is not None and order_budget > f.max_budget:
            return False

    # Рейтинг клиента
    if f.min_client_rating is not None and order.client_rating is not None:
        if order.client_rating < f.min_client_rating:
            return False

    # AI Score
    if f.min_ai_score is not None and order.ai_score is not None:
        if order.ai_score < f.min_ai_score:
            return False

    # Ключевые слова (хотя бы одно)
    kw_list = f.keywords_list
    if kw_list:
        text = f"{order.title} {order.text or ''}".lower()
        if not any(kw in text for kw in kw_list):
            return False

    # Стоп-слова (ни одного)
    excl = f.exclude_keywords_list
    if excl:
        text = f"{order.title} {order.text or ''}".lower()
        if any(kw in text for kw in excl):
            return False

    return True


def order_matches_profile(order: Order, user: User) -> bool:
    """
    Автоподбор по профилю пользователя (без явных фильтров).
    Используется когда у юзера нет активных фильтров, но заполнен профиль.
    """
    matched = False

    # По категориям профиля
    user_cats = user.categories_list
    if user_cats and order.category:
        if order.category in user_cats:
            matched = True
        else:
            parent = order.category.split("_")[0] if "_" in order.category else None
            if parent and parent in user_cats:
                matched = True

    # По навыкам профиля
    user_skills = user.skills_list
    if user_skills:
        text = f"{order.title} {order.text or ''}".lower()
        if any(skill.lower() in text for skill in user_skills):
            matched = True

    # Фильтр по мин. бюджету из профиля
    if matched and user.profile_min_budget:
        order_budget = order.budget_max or order.budget_min
        if order_budget is not None and order_budget < user.profile_min_budget:
            return False

    return matched


def match_orders_for_user(orders: list[Order], filters: list[UserFilter],
                           user: User | None = None) -> list[Order]:
    """Возвращает заказы, подходящие под фильтры или профиль."""
    active = [f for f in filters if f.is_active]

    if active:
        # Стандартный матчинг по фильтрам
        matched = []
        for order in orders:
            for f in active:
                if order_matches_filter(order, f):
                    matched.append(order)
                    break
        return matched

    # Нет фильтров — пробуем автоподбор по профилю
    if user and (user.categories_list or user.skills_list):
        return [o for o in orders if order_matches_profile(o, user)]

    return []
