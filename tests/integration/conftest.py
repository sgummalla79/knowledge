from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from testcontainers.postgres import PostgresContainer

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        url = postgres.get_connection_url()
        alembic_cfg = AlembicConfig(str(REPO_ROOT / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
        alembic_cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(alembic_cfg, "head")
        yield url


@pytest.fixture()
def app_context():
    # Needed by anything touching jwt_tokens.issue_access_token/decode_access_token, which read
    # current_app.config["SECRET_KEY"] — a plain app context is enough, no request/client needed.
    from app import create_app

    app = create_app(testing=True)
    with app.app_context():
        yield app


def seed_active_embedding_provider(
    session, provider, model, api_key, dimensions, chunk_size, chunk_overlap, base_url=None
):
    """Test-only convenience: configures and enables a provider in one call, standing in for what
    was previously a single EmbeddingSettingsRepository.upsert() before embedding config became
    per-provider (see EmbeddingProviderConfigService). Most integration tests just need "some
    provider is the active one" and don't care about the enable/disable lock semantics.

    embedding_models rows are per-org now, so this ensures the default org exists first — most
    callers never otherwise bootstrap one, and the db_session fixture truncates organizations
    between tests."""
    from app.infrastructure.auth.bootstrap import bootstrap_default_organization
    from app.infrastructure.repositories.embedding_provider_settings_repository import (
        EmbeddingProviderSettingsRepository,
    )

    bootstrap_default_organization(session)
    repo = EmbeddingProviderSettingsRepository(session)
    repo.upsert_config(provider, model, api_key, base_url, dimensions, chunk_size, chunk_overlap)
    repo.set_enabled(provider, True)


@pytest.fixture()
def db_session(postgres_url):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(postgres_url)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(
            text(
                "TRUNCATE TABLE chunks, documents, embedding_models, ingestion_jobs, sources, "
                "document_tags, tags, categories, query_results, queries, user_shelf_access, document_shelves, "
                "shelves, search_settings, router_settings, users, organizations, applications, refresh_tokens "
                "CASCADE"
            )
        )
        session.commit()
        session.close()
        engine.dispose()
