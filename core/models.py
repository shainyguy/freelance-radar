"""
ORM-модели — все таблицы БД.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float,
    ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── User ──────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)

    tier: Mapped[str] = mapped_column(String(20), default="free")
    subscription_until: Mapped[Optional[datetime]] = mapped_column(DateTime)

    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[Optional[str]] = mapped_column(String(10))

    quiet_hours_start: Mapped[Optional[int]] = mapped_column(Integer)
    quiet_hours_end: Mapped[Optional[int]] = mapped_column(Integer)
    notifications_today: Mapped[int] = mapped_column(Integer, default=0)
    notifications_reset_date: Mapped[Optional[str]] = mapped_column(String(10))

    ai_credits_left: Mapped[int] = mapped_column(Integer, default=3)
    ai_credits_reset_date: Mapped[Optional[str]] = mapped_column(String(10))

    # ── Профиль-резюме ────────────────────────────
    profile_description: Mapped[Optional[str]] = mapped_column(Text)
    profile_skills: Mapped[Optional[str]] = mapped_column(Text)        # "Python,Django,React"
    profile_categories: Mapped[Optional[str]] = mapped_column(Text)    # "dev_web,dev_bot,dev_backend"
    profile_experience_years: Mapped[Optional[int]] = mapped_column(Integer)
    profile_hourly_rate: Mapped[Optional[int]] = mapped_column(Integer)  # ₽/час
    profile_min_budget: Mapped[Optional[int]] = mapped_column(Integer)   # мин. бюджет заказа
    response_style: Mapped[Optional[str]] = mapped_column(Text)
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(500))
    settings_json: Mapped[Optional[str]] = mapped_column(Text)

    # ── Фишки ─────────────────────────────────────
    total_responses: Mapped[int] = mapped_column(Integer, default=0)     # всего AI-откликов
    total_saved: Mapped[int] = mapped_column(Integer, default=0)
    referral_code: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    referred_by: Mapped[Optional[int]] = mapped_column(BigInteger)       # tg_id пригласившего
    earnings_total: Mapped[float] = mapped_column(Float, default=0.0)    # заработок через CRM
    reaction_avg_seconds: Mapped[Optional[int]] = mapped_column(Integer) # ср. время реакции

    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    filters: Mapped[List["UserFilter"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    payments: Mapped[List["Payment"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    saved_orders: Mapped[List["SavedOrder"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    achievements: Mapped[List["Achievement"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    templates: Mapped[List["ResponseTemplate"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    blacklist: Mapped[List["BlacklistEntry"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    crm_entries: Mapped[List["CRMEntry"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    team: Mapped[Optional["Team"]] = relationship(back_populates="members")

    @property
    def skills_list(self) -> list[str]:
        if not self.profile_skills: return []
        return [s.strip() for s in self.profile_skills.split(",") if s.strip()]

    @property
    def categories_list(self) -> list[str]:
        if not self.profile_categories: return []
        return [c.strip() for c in self.profile_categories.split(",") if c.strip()]


# ── Exchange ──────────────────────────────────────

class Exchange(Base):
    __tablename__ = "exchanges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    parser_class: Mapped[str] = mapped_column(String(100), nullable=False)
    last_parsed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    parse_errors_count: Mapped[int] = mapped_column(Integer, default=0)

    orders: Mapped[List["Order"]] = relationship(back_populates="exchange", cascade="all,delete-orphan")


# ── Order ─────────────────────────────────────────

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("exchange_id", "external_id", name="uq_order_exchange_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange_id: Mapped[int] = mapped_column(Integer, ForeignKey("exchanges.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    text: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)

    budget_min: Mapped[Optional[float]] = mapped_column(Float)
    budget_max: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="RUB")

    category: Mapped[Optional[str]] = mapped_column(String(255))    # наш код: "dev_web"
    category_raw: Mapped[Optional[str]] = mapped_column(String(255))# оригинал с биржи
    tags_str: Mapped[Optional[str]] = mapped_column(Text)

    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    client_rating: Mapped[Optional[float]] = mapped_column(Float)
    client_reviews_count: Mapped[Optional[int]] = mapped_column(Integer)
    responses_count: Mapped[Optional[int]] = mapped_column(Integer)

    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    parsed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    deadline: Mapped[Optional[str]] = mapped_column(String(100))     # "3 дня", "1 неделя"
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)

    ai_score: Mapped[Optional[int]] = mapped_column(Integer)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)
    ai_scam_flags: Mapped[Optional[str]] = mapped_column(Text)
    ai_estimated_price: Mapped[Optional[float]] = mapped_column(Float)

    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Сколько юзеров откликнулось через нас
    our_responses_count: Mapped[int] = mapped_column(Integer, default=0)

    exchange: Mapped["Exchange"] = relationship(back_populates="orders")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="order")
    saved_by: Mapped[List["SavedOrder"]] = relationship(back_populates="order")


# ── UserFilter ────────────────────────────────────

class UserFilter(Base):
    __tablename__ = "user_filters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="Основной")
    keywords: Mapped[Optional[str]] = mapped_column(Text)
    exclude_keywords: Mapped[Optional[str]] = mapped_column(Text)
    categories: Mapped[Optional[str]] = mapped_column(Text)        # "dev_web,dev_bot"
    min_budget: Mapped[Optional[float]] = mapped_column(Float)
    max_budget: Mapped[Optional[float]] = mapped_column(Float)
    exchanges: Mapped[Optional[str]] = mapped_column(Text)
    min_client_rating: Mapped[Optional[float]] = mapped_column(Float)
    min_ai_score: Mapped[Optional[int]] = mapped_column(Integer)
    only_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship(back_populates="filters")

    @property
    def keywords_list(self) -> list[str]:
        if not self.keywords: return []
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]

    @property
    def exclude_keywords_list(self) -> list[str]:
        if not self.exclude_keywords: return []
        return [k.strip().lower() for k in self.exclude_keywords.split(",") if k.strip()]

    @property
    def exchanges_list(self) -> list[str]:
        if not self.exchanges: return []
        return [e.strip() for e in self.exchanges.split(",") if e.strip()]

    @property
    def categories_list(self) -> list[str]:
        if not self.categories: return []
        return [c.strip() for c in self.categories.split(",") if c.strip()]


# ── Notification ──────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user_action: Mapped[str] = mapped_column(String(20), default="sent")
    reaction_seconds: Mapped[Optional[int]] = mapped_column(Integer)  # сек до первого действия

    user: Mapped["User"] = relationship(back_populates="notifications")
    order: Mapped["Order"] = relationship(back_populates="notifications")


# ── Payment ───────────────────────────────────────

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    yookassa_payment_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    amount: Mapped[float] = mapped_column(Float)
    tier: Mapped[str] = mapped_column(String(20))
    months: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="payments")


# ── ResponseTemplate ─────────────────────────────

class ResponseTemplate(Base):
    __tablename__ = "response_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped[Optional["User"]] = relationship(back_populates="templates")


# ── SavedOrder ────────────────────────────────────

class SavedOrder(Base):
    __tablename__ = "saved_orders"
    __table_args__ = (UniqueConstraint("user_id", "order_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship(back_populates="saved_orders")
    order: Mapped["Order"] = relationship(back_populates="saved_by")


# ── Achievement ───────────────────────────────────

class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("user_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(100))
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship(back_populates="achievements")


# ── BlacklistEntry ────────────────────────────────

class BlacklistEntry(Base):
    __tablename__ = "blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    client_name: Mapped[str] = mapped_column(String(255))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship(back_populates="blacklist")


# ── CRMEntry ──────────────────────────────────────

class CRMEntry(Base):
    __tablename__ = "crm_entries"
    __table_args__ = (UniqueConstraint("user_id", "order_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="new")
    price_agreed: Mapped[Optional[float]] = mapped_column(Float)      # согласованная цена
    notes: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="crm_entries")
    order: Mapped["Order"] = relationship()


# ── Team ──────────────────────────────────────────

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    owner_tg_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    members: Mapped[List["User"]] = relationship(back_populates="team")


# ── AdminAuditLog ─────────────────────────────────

class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_tg_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(255))
    target_type: Mapped[Optional[str]] = mapped_column(String(50))
    target_id: Mapped[Optional[int]] = mapped_column(Integer)
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


# ── OrderDigest — еженедельный дайджест ───────────

class OrderDigest(Base):
    __tablename__ = "order_digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    week_start: Mapped[str] = mapped_column(String(10))  # "2026-05-18"
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    matched_orders: Mapped[int] = mapped_column(Integer, default=0)
    avg_budget: Mapped[Optional[float]] = mapped_column(Float)
    top_categories: Mapped[Optional[str]] = mapped_column(Text)  # "dev_web:15,dev_bot:8"
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
