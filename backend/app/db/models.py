import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# ---------------------------------------------------------------------------
# 2.1 Справочники
# ---------------------------------------------------------------------------


class Company(Base):
    __tablename__ = "companies"

    company_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    info: Mapped[str | None] = mapped_column(Text)
    services: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contracts: Mapped[list["Contract"]] = relationship(back_populates="company")


class Contract(Base):
    __tablename__ = "contracts"

    contract_id: Mapped[str] = mapped_column(String, primary_key=True)
    contract_number: Mapped[str] = mapped_column(Text, nullable=False)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.company_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="contracts")
    products: Mapped[list["Product"]] = relationship(
        secondary="contract_products", back_populates="contracts"
    )


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contracts: Mapped[list["Contract"]] = relationship(
        secondary="contract_products", back_populates="products"
    )
    rates: Mapped[list["ProductRate"]] = relationship(back_populates="product")
    operations: Mapped[list["ProductOperation"]] = relationship(back_populates="product")


class ContractProduct(Base):
    __tablename__ = "contract_products"

    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.contract_id"), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), primary_key=True)


class ProductRate(Base):
    __tablename__ = "product_rates"

    price_id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), nullable=False)
    price_name: Mapped[str] = mapped_column(Text, nullable=False)
    measurement_name: Mapped[str | None] = mapped_column(Text)
    measurement_type: Mapped[str | None] = mapped_column(Text)

    product: Mapped["Product"] = relationship(back_populates="rates")


class ProductOperation(Base):
    __tablename__ = "product_operations"

    operation_id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), nullable=False)
    operation_name: Mapped[str] = mapped_column(Text, nullable=False)
    operation_order: Mapped[int | None] = mapped_column(Integer)

    product: Mapped["Product"] = relationship(back_populates="operations")


class CostCalculation(Base):
    __tablename__ = "cost_calculations"

    calc_id: Mapped[str] = mapped_column(String, primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.contract_id"), nullable=False)
    calc_name: Mapped[str] = mapped_column(Text, nullable=False)
    calc_start_date: Mapped[date | None] = mapped_column(Date)
    calc_end_date: Mapped[date | None] = mapped_column(Date)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.product_id"))

    stages: Mapped[list["CalculationStage"]] = relationship(back_populates="calc")


class CalculationStage(Base):
    __tablename__ = "calculation_stages"

    stage_id: Mapped[str] = mapped_column(String, primary_key=True)
    calc_id: Mapped[str] = mapped_column(ForeignKey("cost_calculations.calc_id"), nullable=False)
    parent_stage_id: Mapped[str | None] = mapped_column(ForeignKey("calculation_stages.stage_id"))
    stage_name: Mapped[str] = mapped_column(Text, nullable=False)
    stage_start_date: Mapped[date | None] = mapped_column(Date)
    stage_end_date: Mapped[date | None] = mapped_column(Date)
    stage_order_num: Mapped[int | None] = mapped_column(Integer)
    stage_documentation_list: Mapped[str | None] = mapped_column(Text)

    calc: Mapped["CostCalculation"] = relationship(back_populates="stages")


# ---------------------------------------------------------------------------
# 2.2 Шаблоны ТЗ
# ---------------------------------------------------------------------------


class TzTemplate(Base):
    __tablename__ = "tz_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    minio_docx_key: Mapped[str] = mapped_column(Text, nullable=False)
    blocks_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    blocks: Mapped[list["TzTemplateBlock"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", order_by="TzTemplateBlock.block_order"
    )
    stages: Mapped[list["TzTemplateStage"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", order_by="TzTemplateStage.stage_order"
    )


class TzTemplateBlock(Base):
    __tablename__ = "tz_template_blocks"
    __table_args__ = ({"sqlite_autoincrement": True},)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tz_templates.id", ondelete="CASCADE"), nullable=False
    )
    block_code: Mapped[str] = mapped_column(Text, nullable=False)
    block_name: Mapped[str] = mapped_column(Text, nullable=False)
    block_order: Mapped[int] = mapped_column(Integer, nullable=False)
    json_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)

    template: Mapped["TzTemplate"] = relationship(back_populates="blocks")


class TzTemplateStage(Base):
    __tablename__ = "tz_template_stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tz_templates.id", ondelete="CASCADE"), nullable=False
    )
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(Text, nullable=False)
    default_requirements: Mapped[str | None] = mapped_column(Text)
    default_results: Mapped[str | None] = mapped_column(Text)

    template: Mapped["TzTemplate"] = relationship(back_populates="stages")


# ---------------------------------------------------------------------------
# 2.3 Заявки и конструктор ТЗ
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, default="customer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[str | None] = mapped_column(Text, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")

    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.company_id"))
    contract_id: Mapped[str | None] = mapped_column(ForeignKey("contracts.contract_id"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.product_id"))
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    cost_total: Mapped[float | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(Text, default="RUB")
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)

    chat_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tz: Mapped["RequestTz | None"] = relationship(back_populates="request", uselist=False, cascade="all, delete-orphan")
    documents: Mapped[list["RequestDocument"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class RequestTz(Base):
    __tablename__ = "request_tz"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requests.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tz_templates.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    completeness_pct: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    request: Mapped["Request"] = relationship(back_populates="tz")
    template: Mapped["TzTemplate"] = relationship()
    blocks: Mapped[list["RequestTzBlock"]] = relationship(back_populates="tz", cascade="all, delete-orphan")
    stages: Mapped[list["RequestTzStage"]] = relationship(
        back_populates="tz", cascade="all, delete-orphan", order_by="RequestTzStage.stage_order"
    )
    analyses: Mapped[list["RequestTzAnalysis"]] = relationship(back_populates="tz", cascade="all, delete-orphan")


class RequestTzBlock(Base):
    __tablename__ = "request_tz_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("request_tz.id", ondelete="CASCADE"), nullable=False)
    block_code: Mapped[str] = mapped_column(Text, nullable=False)
    block_name: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    filled_by: Mapped[str] = mapped_column(Text, default="manual")
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    completeness_pct: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tz: Mapped["RequestTz"] = relationship(back_populates="blocks")


class RequestTzStage(Base):
    __tablename__ = "request_tz_stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("request_tz.id", ondelete="CASCADE"), nullable=False)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text)
    expected_results: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    stage_start_date: Mapped[date | None] = mapped_column(Date)
    stage_end_date: Mapped[date | None] = mapped_column(Date)
    filled_by: Mapped[str] = mapped_column(Text, default="manual")

    tz: Mapped["RequestTz"] = relationship(back_populates="stages")


class RequestTzAnalysis(Base):
    __tablename__ = "request_tz_analysis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("request_tz.id", ondelete="CASCADE"), nullable=False)
    completeness_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    risks: Mapped[list] = mapped_column(JSONB, default=list)
    recommendations: Mapped[list] = mapped_column(JSONB, default=list)
    block_completeness: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tz: Mapped["RequestTz"] = relationship(back_populates="analyses")


class TzCompletenessLog(Base):
    __tablename__ = "tz_completeness_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("request_tz.id", ondelete="CASCADE"), nullable=False)
    completeness_pct: Mapped[int | None] = mapped_column(Integer)
    triggered_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RequestDocument(Base):
    __tablename__ = "request_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("requests.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text)
    minio_bucket: Mapped[str] = mapped_column(Text, nullable=False)
    minio_key: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    generated_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    request: Mapped["Request"] = relationship(back_populates="documents")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("requests.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    actions: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    payload: Mapped[dict | None] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(settings.llm_embedding_dim))
    embedding_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
