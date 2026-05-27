"""
Каталог категорий — как на биржах.
Пользователь выбирает из готового списка, а не пишет руками.
Категории соотносятся с категориями на биржах при парсинге.
"""

# ── Дерево категорий ──────────────────────────────
# Формат: {код: (emoji, название, [подкатегории])}

CATEGORIES = {
    "dev": ("💻", "Разработка", {
        "dev_web":     ("🌐", "Веб-разработка"),
        "dev_mobile":  ("📱", "Мобильная разработка"),
        "dev_bot":     ("🤖", "Боты / автоматизация"),
        "dev_backend": ("⚙️",  "Backend"),
        "dev_frontend":("🎨", "Frontend"),
        "dev_desktop": ("🖥",  "Десктоп-приложения"),
        "dev_gamedev": ("🎮", "Gamedev"),
        "dev_1c":      ("📊", "1С-программирование"),
        "dev_scripts":  ("📜", "Скрипты / парсеры"),
        "dev_db":      ("🗄",  "Базы данных"),
        "dev_api":     ("🔗", "API / интеграции"),
        "dev_wp":      ("📝", "WordPress / CMS"),
    }),
    "design": ("🎨", "Дизайн", {
        "des_web":     ("🖼",  "Веб-дизайн"),
        "des_ui":      ("📐", "UI/UX"),
        "des_logo":    ("✏️",  "Логотипы / брендинг"),
        "des_banner":  ("🏷",  "Баннеры / реклама"),
        "des_3d":      ("🧊", "3D-графика"),
        "des_motion":  ("🎬", "Моушн-дизайн"),
        "des_illustr": ("🖌",  "Иллюстрации"),
        "des_present": ("📊", "Презентации"),
    }),
    "text": ("📝", "Тексты", {
        "txt_copy":    ("✍️",  "Копирайтинг"),
        "txt_seo":     ("🔍", "SEO-тексты"),
        "txt_transl":  ("🌍", "Переводы"),
        "txt_edit":    ("📖", "Редактура / корректура"),
        "txt_tech":    ("📋", "Техническая документация"),
        "txt_content": ("📰", "Контент-менеджмент"),
    }),
    "marketing": ("📢", "Маркетинг", {
        "mrk_smm":     ("📱", "SMM"),
        "mrk_seo":     ("📈", "SEO-продвижение"),
        "mrk_context": ("🎯", "Контекстная реклама"),
        "mrk_target":  ("🎯", "Таргетированная реклама"),
        "mrk_email":   ("📧", "Email-маркетинг"),
        "mrk_analyt":  ("📊", "Аналитика"),
    }),
    "admin": ("🔧", "Администрирование", {
        "adm_server":  ("🖥",  "Серверы / DevOps"),
        "adm_support": ("🆘", "Техподдержка"),
        "adm_data":    ("📊", "Обработка данных"),
        "adm_testing": ("🧪", "Тестирование / QA"),
    }),
    "video": ("🎬", "Видео / аудио", {
        "vid_edit":    ("🎞",  "Видеомонтаж"),
        "vid_voice":   ("🎙",  "Озвучка"),
        "vid_anim":    ("🎭", "Анимация"),
        "vid_music":   ("🎵", "Музыка / звук"),
    }),
    "biz": ("💼", "Бизнес / консалтинг", {
        "biz_consult": ("💡", "Консалтинг"),
        "biz_finance": ("💰", "Финансы / бухгалтерия"),
        "biz_legal":   ("⚖️",  "Юридические услуги"),
        "biz_pm":      ("📋", "Управление проектами"),
    }),
}

# ── Flat-список для быстрого поиска ───────────────

def get_all_subcategories() -> dict[str, tuple[str, str, str]]:
    """Возвращает {код: (emoji, название, код_родителя)}"""
    result = {}
    for parent_code, (_, _, subs) in CATEGORIES.items():
        for sub_code, (emoji, name) in subs.items():
            result[sub_code] = (emoji, name, parent_code)
    return result

ALL_SUBCATS = get_all_subcategories()

def get_category_name(code: str) -> str:
    """Получить название по коду."""
    if code in ALL_SUBCATS:
        emoji, name, _ = ALL_SUBCATS[code]
        return f"{emoji} {name}"
    for parent_code, (emoji, name, _) in CATEGORIES.items():
        if code == parent_code:
            return f"{emoji} {name}"
    return code

def get_parent_categories() -> list[tuple[str, str, str]]:
    """[(код, emoji, название)]"""
    return [(code, emoji, name) for code, (emoji, name, _) in CATEGORIES.items()]

def get_subcategories(parent_code: str) -> list[tuple[str, str, str]]:
    """[(код, emoji, название)]"""
    if parent_code not in CATEGORIES:
        return []
    _, _, subs = CATEGORIES[parent_code]
    return [(code, emoji, name) for code, (emoji, name) in subs.items()]

# ── Маппинг категорий бирж → наши коды ────────────
# Парсеры маппят категории бирж на наши коды

EXCHANGE_CATEGORY_MAP = {
    # FL.ru категории (с сайта)
    "сайты": "dev_web", "дизайн": "des_web", "программирование": "dev_backend",
    "ai — искусственный интеллект": "dev_backend",
    "тексты": "txt_copy", "mobile": "dev_mobile",
    "продвижение сайтов (seo, geo)": "mrk_seo",
    "реклама и маркетинг": "mrk_context", "рекламa": "mrk_context",
    "аутсорсинг и консалтинг": "biz_consult",
    "аудио/видео/фото": "vid_edit", "3d графика": "des_3d",
    "автоматизация бизнеса": "dev_1c",
    "рисунки и иллюстрации": "des_illustr", "анимация": "vid_anim",
    "инжиниринг": "biz_consult",
    "фирменный стиль": "des_logo",
    "крипто и блокчейн": "dev_backend",
    "мессенджеры": "dev_bot", "интернет-магазины": "dev_web",
    "маркетплейс менеджмент": "mrk_smm",
    "социальные сети": "mrk_smm", "игры": "dev_gamedev",
    "браузеры": "dev_frontend",

    # Freelance.ru категории
    "веб-разработка и продуктовый дизайн": "dev_web",
    "графический дизайн": "des_web", "дизайн пространства": "des_web",
    "ит и разработка": "dev_backend", "искусственный интеллект": "dev_backend",
    "маркетинг и реклама": "mrk_context",
    "интернет продвижение": "mrk_seo",
    "медиа и моушен дизайн": "vid_anim",
    "музыка и звук": "vid_music", "переводы": "txt_transl",
    "арт и иллюстрации": "des_illustr",
    "обучение и образование": "biz_consult",
    "фотография": "vid_edit", "инженерия": "biz_consult",

    # Kwork
    "web-программирование": "dev_web",
    "мобильные приложения": "dev_mobile", "боты": "dev_bot",
    "парсинг": "dev_scripts", "скрипты": "dev_scripts",
    "wordpress": "dev_wp", "логотипы": "des_logo",
    "баннеры": "des_banner", "копирайтинг": "txt_copy",
    "seo": "mrk_seo", "smm": "mrk_smm",
    "видеомонтаж": "vid_edit", "озвучка": "vid_voice",
    "тестирование": "adm_testing",
    "разработка и it": "dev_backend",
    "тексты и переводы": "txt_copy",
    "seo и трафик": "mrk_seo",
    "соцсети и маркетинг": "mrk_smm",
    "аудио, видео, съемка": "vid_edit",
    "бизнес и жизнь": "biz_consult",

    # Weblancer
    "создание сайтов": "dev_web", "дизайн сайтов": "des_web",
    "adobe photoshop": "des_web", "figma": "des_ui",
    "telegram": "dev_bot", "python": "dev_backend",
    "javascript": "dev_frontend", "php": "dev_backend",
    "react": "dev_frontend", "нейросети": "dev_backend",
    "создание инфографики": "des_web",
    "создание карточек товаров": "des_web",
    "написание отзывов": "txt_copy",

    # Общие
    "реклама": "mrk_context",
}

def map_exchange_category(raw: str) -> str | None:
    """Привести категорию биржи к нашему коду."""
    if not raw:
        return None
    key = raw.strip().lower()
    # Точное совпадение
    if key in EXCHANGE_CATEGORY_MAP:
        return EXCHANGE_CATEGORY_MAP[key]
    # Частичное
    for pattern, code in EXCHANGE_CATEGORY_MAP.items():
        if pattern in key or key in pattern:
            return code
    return None


# ── Стеки / навыки ────────────────────────────────

POPULAR_SKILLS = [
    "Python", "JavaScript", "TypeScript", "React", "Vue.js", "Angular",
    "Node.js", "Django", "FastAPI", "Flask", "Laravel", "PHP",
    "Java", "Kotlin", "Swift", "Flutter", "React Native",
    "C#", ".NET", "C++", "Go", "Rust",
    "PostgreSQL", "MySQL", "MongoDB", "Redis",
    "Docker", "Kubernetes", "AWS", "Linux",
    "HTML/CSS", "Tailwind", "Bootstrap",
    "Figma", "Photoshop", "Illustrator",
    "WordPress", "Bitrix", "1С",
    "Telegram Bot", "Selenium", "Scrapy",
    "Unity", "Unreal Engine",
    "SEO", "SMM", "Google Ads", "Яндекс Директ",
    "Копирайтинг", "Переводы", "Видеомонтаж",
]
