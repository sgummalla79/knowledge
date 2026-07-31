"""web_crawl_settings: admin-configurable User-Agent for outbound page fetches

Some sites (e.g. developer.salesforce.com) return 403 for the honest default identifying UA
(app/infrastructure/web/fetcher.py). Rather than hardcoding a single fixed workaround, this is a
single global row — mirrors search_settings (migration 0003): an absent row is not an error,
WebCrawlSettingsService falls back to DEFAULT_WEB_CRAWL_USER_AGENT.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "web_crawl_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_agent", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("web_crawl_settings")
