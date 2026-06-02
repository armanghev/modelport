from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from app.config import AppConfig
from app.security import mask_secret


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)


class Provider(TimestampMixin, Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    credentials: Mapped[list["ProviderCredential"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
    )


class ProviderCredential(TimestampMixin, Base):
    __tablename__ = "provider_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    api_key_env: Mapped[str | None] = mapped_column(String(255))
    encrypted_api_key: Mapped[str | None] = mapped_column(Text)
    key_hint: Mapped[str | None] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    provider: Mapped[Provider] = relationship(back_populates="credentials")


class PricingOverride(TimestampMixin, Base):
    __tablename__ = "pricing_overrides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    input_per_1m_usd: Mapped[float] = mapped_column(Float, nullable=False)
    output_per_1m_usd: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(16), default="USD", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProviderHealthCheck(Base):
    __tablename__ = "provider_health_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_model_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AppSetting(TimestampMixin, Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, future=True)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def initialize_database(session_factory: sessionmaker[Session]) -> None:
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        if session.get(SchemaVersion, 1) is None:
            session.add(SchemaVersion(version=1))
            session.commit()


def get_setting(session: Session, key: str, default: dict) -> dict:
    record = session.get(AppSetting, key)
    if record is None:
        return default
    return json.loads(record.value_json)


def set_setting(session: Session, key: str, value: dict) -> AppSetting:
    payload = json.dumps(value)
    record = session.get(AppSetting, key)
    if record is None:
        record = AppSetting(key=key, value_json=payload)
        session.add(record)
    else:
        record.value_json = payload
    session.flush()
    return record


def resolve_env_secret(credential: ProviderCredential) -> str | None:
    if credential.source != "env" or not credential.api_key_env:
        return None
    return os.environ.get(credential.api_key_env)


def resolved_key_hint(credential: ProviderCredential) -> str:
    if credential.source == "env":
        return mask_secret(resolve_env_secret(credential))
    return credential.key_hint or "Configured"


def is_credential_configured(credential: ProviderCredential) -> bool:
    if credential.source == "env":
        return bool(resolve_env_secret(credential))
    return bool(credential.encrypted_api_key)


def clear_default_credentials(session: Session, provider_id: str, exclude_id: str | None = None) -> None:
    credentials = session.scalars(
        select(ProviderCredential).where(ProviderCredential.provider_id == provider_id)
    ).all()
    for credential in credentials:
        if credential.id != exclude_id:
            credential.is_default = False


def seed_admin_data(session_factory: sessionmaker[Session], config: AppConfig) -> None:
    with session_factory() as session:
        has_providers = session.scalar(select(Provider.id).limit(1))
        if has_providers is not None:
            return

        for provider_id, provider_config in config.providers.items():
            provider = Provider(
                id=provider_id,
                display_name=provider_config.display_name,
                provider_type=provider_config.type,
                base_url=provider_config.base_url,
                enabled=True,
            )
            session.add(provider)
            session.flush()

            if provider_config.api_key_env:
                secret = os.environ.get(provider_config.api_key_env)
                session.add(
                    ProviderCredential(
                        provider_id=provider_id,
                        display_name=f"{provider_config.display_name} Env",
                        source="env",
                        api_key_env=provider_config.api_key_env,
                        key_hint=mask_secret(secret),
                        is_default=True,
                        enabled=True,
                    )
                )

        set_setting(
            session,
            "tracking",
            {
                "request_logging": True,
                "cost_tracking": True,
                "retention_days": 30,
            },
        )
        set_setting(
            session,
            "appearance",
            {
                "theme": "system",
                "refresh_interval_seconds": 30,
            },
        )
        session.commit()
