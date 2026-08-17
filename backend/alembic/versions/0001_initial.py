"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-17

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

from alembic import op
from app.core.config import get_settings

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = get_settings().llm_embedding_dim


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "companies",
        sa.Column("company_id", sa.String(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("info", sa.Text()),
        sa.Column("services", sa.Text()),
        sa.Column("rating", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "contracts",
        sa.Column("contract_id", sa.String(), primary_key=True),
        sa.Column("contract_number", sa.Text(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.company_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "products",
        sa.Column("product_id", sa.String(), primary_key=True),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "contract_products",
        sa.Column("contract_id", sa.String(), sa.ForeignKey("contracts.contract_id"), primary_key=True),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.product_id"), primary_key=True),
    )

    op.create_table(
        "product_rates",
        sa.Column("price_id", sa.String(), primary_key=True),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("price_name", sa.Text(), nullable=False),
        sa.Column("measurement_name", sa.Text()),
        sa.Column("measurement_type", sa.Text()),
    )

    op.create_table(
        "product_operations",
        sa.Column("operation_id", sa.String(), primary_key=True),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("operation_name", sa.Text(), nullable=False),
        sa.Column("operation_order", sa.Integer()),
    )

    op.create_table(
        "cost_calculations",
        sa.Column("calc_id", sa.String(), primary_key=True),
        sa.Column("contract_id", sa.String(), sa.ForeignKey("contracts.contract_id"), nullable=False),
        sa.Column("calc_name", sa.Text(), nullable=False),
        sa.Column("calc_start_date", sa.Date()),
        sa.Column("calc_end_date", sa.Date()),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.product_id")),
    )

    op.create_table(
        "calculation_stages",
        sa.Column("stage_id", sa.String(), primary_key=True),
        sa.Column("calc_id", sa.String(), sa.ForeignKey("cost_calculations.calc_id"), nullable=False),
        sa.Column("parent_stage_id", sa.String(), sa.ForeignKey("calculation_stages.stage_id")),
        sa.Column("stage_name", sa.Text(), nullable=False),
        sa.Column("stage_start_date", sa.Date()),
        sa.Column("stage_end_date", sa.Date()),
        sa.Column("stage_order_num", sa.Integer()),
        sa.Column("stage_documentation_list", sa.Text()),
    )

    op.create_table(
        "tz_templates",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("minio_docx_key", sa.Text(), nullable=False),
        sa.Column("blocks_schema", pg.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tz_template_blocks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("template_id", pg.UUID(as_uuid=True), sa.ForeignKey("tz_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_code", sa.Text(), nullable=False),
        sa.Column("block_name", sa.Text(), nullable=False),
        sa.Column("block_order", sa.Integer(), nullable=False),
        sa.Column("json_schema", pg.JSONB(), nullable=False),
        sa.UniqueConstraint("template_id", "block_code"),
    )

    op.create_table(
        "tz_template_stages",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("template_id", pg.UUID(as_uuid=True), sa.ForeignKey("tz_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.Text(), nullable=False),
        sa.Column("default_requirements", sa.Text()),
        sa.Column("default_results", sa.Text()),
    )

    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("full_name", sa.Text()),
        sa.Column("role", sa.Text(), server_default="customer"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "requests",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("number", sa.Text(), unique=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.company_id")),
        sa.Column("contract_id", sa.String(), sa.ForeignKey("contracts.contract_id")),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.product_id")),
        sa.Column("title", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("cost_total", sa.Numeric(14, 2)),
        sa.Column("currency", sa.Text(), server_default="RUB"),
        sa.Column("date_start", sa.Date()),
        sa.Column("date_end", sa.Date()),
        sa.Column("chat_session_id", pg.UUID(as_uuid=True)),
        sa.Column("metadata", pg.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "request_tz",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", pg.UUID(as_uuid=True), sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("template_id", pg.UUID(as_uuid=True), sa.ForeignKey("tz_templates.id"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("completeness_pct", sa.Integer(), server_default="0"),
        sa.Column("payload", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "request_tz_blocks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tz_id", pg.UUID(as_uuid=True), sa.ForeignKey("request_tz.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_code", sa.Text(), nullable=False),
        sa.Column("block_name", sa.Text(), nullable=False),
        sa.Column("content", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("filled_by", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("is_complete", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("completeness_pct", sa.Integer(), server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tz_id", "block_code"),
    )

    op.create_table(
        "request_tz_stages",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tz_id", pg.UUID(as_uuid=True), sa.ForeignKey("request_tz.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text()),
        sa.Column("expected_results", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("stage_start_date", sa.Date()),
        sa.Column("stage_end_date", sa.Date()),
        sa.Column("filled_by", sa.Text(), server_default="manual"),
    )

    op.create_table(
        "request_tz_analysis",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tz_id", pg.UUID(as_uuid=True), sa.ForeignKey("request_tz.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completeness_pct", sa.Integer(), nullable=False),
        sa.Column("risks", pg.JSONB(), nullable=False, server_default="[]"),
        sa.Column("recommendations", pg.JSONB(), nullable=False, server_default="[]"),
        sa.Column("block_completeness", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tz_completeness_log",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tz_id", pg.UUID(as_uuid=True), sa.ForeignKey("request_tz.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completeness_pct", sa.Integer()),
        sa.Column("triggered_by", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "request_documents",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", pg.UUID(as_uuid=True), sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text()),
        sa.Column("minio_bucket", sa.Text(), nullable=False),
        sa.Column("minio_key", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("generated_by_ai", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", pg.UUID(as_uuid=True), sa.ForeignKey("requests.id", ondelete="CASCADE")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", pg.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("actions", pg.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("payload", pg.JSONB()),
        sa.Column("result", pg.JSONB()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "embeddings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM)),
        sa.Column("metadata", pg.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute(
        "CREATE INDEX embeddings_embedding_ivfflat_idx ON embeddings USING ivfflat (embedding vector_cosine_ops)"
    )
    op.create_index("ix_embeddings_entity", "embeddings", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("embeddings")
    op.drop_table("jobs")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("request_documents")
    op.drop_table("tz_completeness_log")
    op.drop_table("request_tz_analysis")
    op.drop_table("request_tz_stages")
    op.drop_table("request_tz_blocks")
    op.drop_table("request_tz")
    op.drop_table("requests")
    op.drop_table("users")
    op.drop_table("tz_template_stages")
    op.drop_table("tz_template_blocks")
    op.drop_table("tz_templates")
    op.drop_table("calculation_stages")
    op.drop_table("cost_calculations")
    op.drop_table("product_operations")
    op.drop_table("product_rates")
    op.drop_table("contract_products")
    op.drop_table("products")
    op.drop_table("contracts")
    op.drop_table("companies")
