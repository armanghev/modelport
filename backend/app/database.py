from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    delete,
    inspect,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from app.ids import generate_api_request_id


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

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
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
    rate_card_json: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="legacy_seed", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ModelMetadata(Base):
    __tablename__ = "model_metadata"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    canonical_slug: Mapped[str | None] = mapped_column(String(255), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    context_length: Mapped[int | None] = mapped_column(Integer)
    architecture_json: Mapped[str | None] = mapped_column(Text)
    input_modalities_json: Mapped[str | None] = mapped_column(Text)
    output_modalities_json: Mapped[str | None] = mapped_column(Text)
    supported_parameters_json: Mapped[str | None] = mapped_column(Text)
    input_per_1m_usd: Mapped[float | None] = mapped_column(Float)
    output_per_1m_usd: Mapped[float | None] = mapped_column(Float)
    top_provider_json: Mapped[str | None] = mapped_column(Text)
    expiration_date: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="openrouter")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ApiRequest(Base):
    __tablename__ = "api_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_api_request_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    input_format: Mapped[str] = mapped_column(String(32), nullable=False)
    output_format: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(255))
    requested_model: Mapped[str | None] = mapped_column(String(255))
    resolved_model: Mapped[str | None] = mapped_column(String(255))
    provider: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_source: Mapped[str | None] = mapped_column(String(64))
    uncached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_write_5m_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_write_1h_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    cost_input_usd: Mapped[float | None] = mapped_column(Float)
    cost_output_usd: Mapped[float | None] = mapped_column(Float)
    cost_reasoning_usd: Mapped[float | None] = mapped_column(Float)
    cost_cache_read_usd: Mapped[float | None] = mapped_column(Float)
    cost_cache_write_usd: Mapped[float | None] = mapped_column(Float)
    cost_tools_usd: Mapped[float | None] = mapped_column(Float)
    cost_modalities_usd: Mapped[float | None] = mapped_column(Float)
    pricing_units_json: Mapped[str | None] = mapped_column(Text)
    context_tier: Mapped[str | None] = mapped_column(String(32))
    service_tier: Mapped[str | None] = mapped_column(String(32))
    pricing_source: Mapped[str | None] = mapped_column(String(64))
    ttfb_ms: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status_code: Mapped[int | None] = mapped_column(Integer)
    completion_reason: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    streamed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(255))
    request_body: Mapped[str | None] = mapped_column(Text)
    response_body: Mapped[str | None] = mapped_column(Text)


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


class ProxyResponseResource(Base):
    __tablename__ = "proxy_response_resources"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_model: Mapped[str] = mapped_column(String(255), nullable=False)
    upstream_model: Mapped[str] = mapped_column(String(255), nullable=False)
    upstream_response_id: Mapped[str | None] = mapped_column(String(255))
    response_json: Mapped[str | None] = mapped_column(Text)
    input_items_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return
    path_part = database_url[len(prefix) :]
    if not path_part or path_part == ":memory:":
        return
    db_path = Path(path_part)
    if db_path.parent != db_path:
        db_path.parent.mkdir(parents=True, exist_ok=True)


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    _ensure_sqlite_parent_dir(database_url)
    engine = create_engine(database_url, future=True)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def initialize_database(session_factory: sessionmaker[Session]) -> None:
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)
    ensure_runtime_columns(engine)
    migrate_provider_schema_v2(engine, session_factory)

    with session_factory() as session:
        if session.get(SchemaVersion, 1) is None:
            session.add(SchemaVersion(version=1))
        if session.get(SchemaVersion, 2) is None:
            session.add(SchemaVersion(version=2))
        if session.get(SchemaVersion, 3) is None:
            session.add(SchemaVersion(version=3))
        if session.get(SchemaVersion, 4) is None:
            session.add(SchemaVersion(version=4))
        if session.get(SchemaVersion, 5) is None:
            session.add(SchemaVersion(version=5))
        session.commit()


def migrate_provider_schema_v2(engine, session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        if session.get(SchemaVersion, 2) is not None:
            return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "providers" in table_names:
        provider_columns = {column["name"] for column in inspector.get_columns("providers")}
        if "slug" not in provider_columns:
            with engine.begin() as connection:
                connection.exec_driver_sql("DROP TABLE IF EXISTS provider_credentials")
                connection.exec_driver_sql("DROP TABLE IF EXISTS pricing_overrides")
                connection.exec_driver_sql("DROP TABLE IF EXISTS provider_health_checks")
                connection.exec_driver_sql("DROP TABLE IF EXISTS providers")

    Provider.__table__.create(engine, checkfirst=True)
    ProviderCredential.__table__.create(engine, checkfirst=True)
    PricingOverride.__table__.create(engine, checkfirst=True)
    ProviderHealthCheck.__table__.create(engine, checkfirst=True)


def ensure_runtime_columns(engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "api_requests" in table_names:
        existing_columns = {column["name"] for column in inspector.get_columns("api_requests")}
        statements: list[str] = []
        if "ttfb_ms" not in existing_columns:
            statements.append("ALTER TABLE api_requests ADD COLUMN ttfb_ms INTEGER")
        if "completion_reason" not in existing_columns:
            statements.append("ALTER TABLE api_requests ADD COLUMN completion_reason VARCHAR(64)")
        if "request_body" not in existing_columns:
            statements.append("ALTER TABLE api_requests ADD COLUMN request_body TEXT")
        if "response_body" not in existing_columns:
            statements.append("ALTER TABLE api_requests ADD COLUMN response_body TEXT")

        breakdown_columns = {
            "uncached_input_tokens": "INTEGER",
            "cache_read_tokens": "INTEGER",
            "cache_write_5m_tokens": "INTEGER",
            "cache_write_1h_tokens": "INTEGER",
            "cost_input_usd": "FLOAT",
            "cost_output_usd": "FLOAT",
            "reasoning_tokens": "INTEGER",
            "cost_reasoning_usd": "FLOAT",
            "cost_cache_read_usd": "FLOAT",
            "cost_cache_write_usd": "FLOAT",
            "cost_tools_usd": "FLOAT",
            "cost_modalities_usd": "FLOAT",
            "pricing_units_json": "TEXT",
            "context_tier": "VARCHAR(32)",
            "service_tier": "VARCHAR(32)",
        }
        for column_name, column_type in breakdown_columns.items():
            if column_name not in existing_columns:
                statements.append(
                    f"ALTER TABLE api_requests ADD COLUMN {column_name} {column_type}"
                )

        if statements:
            with engine.begin() as connection:
                for statement in statements:
                    connection.exec_driver_sql(statement)

    if "pricing_overrides" in table_names:
        pricing_columns = {column["name"] for column in inspector.get_columns("pricing_overrides")}
        pricing_statements: list[str] = []
        if "rate_card_json" not in pricing_columns:
            pricing_statements.append("ALTER TABLE pricing_overrides ADD COLUMN rate_card_json TEXT")
        if "source" not in pricing_columns:
            pricing_statements.append(
                "ALTER TABLE pricing_overrides ADD COLUMN source VARCHAR(32) DEFAULT 'legacy_seed'"
            )
        if pricing_statements:
            with engine.begin() as connection:
                for statement in pricing_statements:
                    connection.exec_driver_sql(statement)

    if "proxy_response_resources" not in table_names:
        return

    proxy_response_columns = {
        column["name"] for column in inspector.get_columns("proxy_response_resources")
    }
    if "expires_at" not in proxy_response_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE proxy_response_resources ADD COLUMN expires_at DATETIME"
            )


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


def purge_expired_tracking_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        retention_days = get_setting(session, "tracking", {}).get("retention_days")
        if not isinstance(retention_days, int) or retention_days <= 0:
            return
        cutoff = utc_now() - timedelta(days=retention_days)
        session.execute(delete(ApiRequest).where(ApiRequest.created_at < cutoff))
        session.execute(delete(ProxyResponseResource).where(ProxyResponseResource.created_at < cutoff))
        session.commit()


def get_provider_by_slug(session: Session, slug: str) -> Provider | None:
    normalized = slug.strip().lower()
    if not normalized:
        return None
    return session.scalar(select(Provider).where(Provider.slug == normalized))

def resolved_key_hint(credential: ProviderCredential) -> str:
    return credential.key_hint or "Not configured"


def is_credential_configured(credential: ProviderCredential) -> bool:
    return bool(credential.encrypted_api_key)


def clear_default_credentials(session: Session, provider_id: str, exclude_id: str | None = None) -> None:
    credentials = session.scalars(
        select(ProviderCredential).where(ProviderCredential.provider_id == provider_id)
    ).all()
    for credential in credentials:
        if credential.id != exclude_id:
            credential.is_default = False


def seed_admin_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        if session.get(AppSetting, "tracking") is not None:
            return

        set_setting(
            session,
            "tracking",
            {
                "io_logging": False,
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
