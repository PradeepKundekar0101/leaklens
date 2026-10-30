"""Reference and master data."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Json, Money


class Procedure(Base):
    __tablename__ = "procedures"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64))
    icd10: Mapped[str] = mapped_column(String(32))
    base_rate: Mapped[Money]
    typical_los: Mapped[int] = mapped_column(Integer)
    typical_pharmacy_share: Mapped[float] = mapped_column(Numeric(5, 3))
    age_profile: Mapped[Json]  # {"mean": 55, "sd": 12, "min": 18, "max": 90}
    frequency: Mapped[float] = mapped_column(Numeric(6, 3))
    waiting_category: Mapped[str] = mapped_column(String(32))  # none / listed_condition


class Item(Base):
    __tablename__ = "items"

    item_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(32))
    mrp: Mapped[Money]
    non_payable: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(255))


class Multiplier(Base):
    __tablename__ = "multipliers"

    factor_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[float] = mapped_column(Numeric(6, 3))


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(64))
    city_tier: Mapped[int] = mapped_column(Integer)
    hospital_tier: Mapped[int] = mapped_column(Integer)
    nabh: Mapped[bool] = mapped_column(Boolean)
    beds: Mapped[int] = mapped_column(Integer)
    network: Mapped[bool] = mapped_column(Boolean)
    joined_at: Mapped[date] = mapped_column(Date)


class Tariff(Base):
    __tablename__ = "tariffs"

    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), primary_key=True)
    procedure_code: Mapped[str] = mapped_column(ForeignKey("procedures.code"), primary_key=True)
    package_rate: Mapped[Money]


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    channel: Mapped[str] = mapped_column(String(32))


class Member(Base):
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(1))
    city: Mapped[str] = mapped_column(String(64))
    member_since: Mapped[date] = mapped_column(Date)
    declared_conditions: Mapped[Json]
    bank_account_hash: Mapped[str] = mapped_column(String(64))
    phone_hash: Mapped[str] = mapped_column(String(64))


class PolicyProduct(Base):
    __tablename__ = "policy_products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(16))
    wording_key: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="active")


class PolicyParams(Base):
    __tablename__ = "policy_params"

    product_id: Mapped[str] = mapped_column(ForeignKey("policy_products.id"), primary_key=True)
    room_rent_cap_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    icu_cap_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    copay_pct: Mapped[float] = mapped_column(Numeric(6, 3), default=0)
    deductible: Mapped[Money]
    sub_limits: Mapped[Json]  # {"CATARACT": "40000.00"}
    waiting_periods: Mapped[Json]  # {"initial_days": 30, "listed_conditions_months": 24, "pre_existing_months": 36}
    clause_refs: Mapped[Json]  # {"room_rent_cap_pct": "4.2", ...}
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposed: Mapped[Json | None]  # parameters extracted from the wording, awaiting approval


class MemberPolicy(Base):
    __tablename__ = "member_policies"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("policy_products.id"))
    sum_insured: Mapped[Money]
    balance: Mapped[Money]
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
