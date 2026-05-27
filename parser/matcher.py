"""
Матчинг заказов по профилю пользователя.

Логика:
1. Если у заказа есть категория → проверяем совпадение с профилем
2. Если у заказа нет категории → проверяем навыки в тексте
3. Если ничего не совпало → НЕ показываем

Важно: заказы без категории тоже матчатся по навыкам!
"""
from __future__ import annotations
from core.models import Order, User


def order_matches_profile(order: Order, user: User) -> bool:
    """Проверяет, подходит ли заказ под профиль пользователя."""
    user_cats = user.categories_list
    user_skills = user.skills_list

    if not user_cats and not user_skills:
        return False  # профиль пустой — ничего не показываем

    text = f"{order.title} {order.text or ''} {order.tags_str or ''} {order.category_raw or ''}".lower()
    matched = False

    # 1. Совпадение по категориям
    if user_cats and order.category:
        if order.category in user_cats:
            matched = True
        else:
            # Проверяем родительскую: "dev_web" → пользователь выбрал "dev"
            parent = order.category.split("_")[0] if "_" in order.category else order.category
            if parent in user_cats:
                matched = True

    # 2. Совпадение по навыкам (ищем в тексте заказа)
    if user_skills:
        for skill in user_skills:
            if skill.lower() in text:
                matched = True
                break

    # 3. Если у заказа нет нашей категории, но есть raw-категория,
    #    проверяем её текстом по навыкам и категориям юзера
    if not matched and not order.category:
        # Пробуем матчить по ключевым словам категорий
        from core.categories import CATEGORIES
        for parent_code in user_cats:
            if parent_code in CATEGORIES:
                _, parent_name, subs = CATEGORIES[parent_code]
                if parent_name.lower() in text:
                    matched = True
                    break
                for sub_code, (_, sub_name) in subs.items():
                    if sub_code in user_cats and sub_name.lower() in text:
                        matched = True
                        break
            else:
                # Это подкатегория — ищем её название в тексте
                from core.categories import ALL_SUBCATS
                if parent_code in ALL_SUBCATS:
                    _, sub_name, _ = ALL_SUBCATS[parent_code]
                    if sub_name.lower() in text:
                        matched = True
                        break

    # 4. Фильтр по мин. бюджету из профиля
    if matched and user.profile_min_budget:
        order_budget = order.budget_max or order.budget_min
        if order_budget is not None and order_budget < user.profile_min_budget:
            return False

    return matched


def match_orders_for_user(orders: list[Order], filters: list,
                           user: User | None = None) -> list[Order]:
    """Возвращает заказы, подходящие под профиль пользователя."""
    if not user:
        return []

    if not user.categories_list and not user.skills_list:
        return []

    return [o for o in orders if order_matches_profile(o, user)]
