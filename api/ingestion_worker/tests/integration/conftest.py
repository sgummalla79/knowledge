from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from testcontainers.postgres import PostgresContainer

from api.infrastructure.storage.upload_storage import UploadStorage

# Duplicated from api/tests/integration/conftest.py rather than imported — api/tests/ has no
# __init__.py (pytest doesn't need one for collection), so there's no clean package path to import
# its fixtures from. Same precedent api/mcp_server/tests/integration/conftest.py already
# established.

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        url = postgres.get_connection_url()
        alembic_cfg = AlembicConfig(str(REPO_ROOT / "api" / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "api" / "migrations"))
        alembic_cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(alembic_cfg, "head")
        yield url


@pytest.fixture()
def session_factory(postgres_url):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(postgres_url)
    yield sessionmaker(bind=engine)
    engine.dispose()


def seed_active_embedding_provider(
    session, provider, model, api_key, dimensions, chunk_size, chunk_overlap, base_url=None
):
    """Same helper as api/tests/integration/conftest.py's — see that file's docstring."""
    from api.infrastructure.auth.bootstrap import bootstrap_default_organization
    from api.infrastructure.repositories.embedding_provider_settings_repository import (
        EmbeddingProviderSettingsRepository,
    )

    org_id = bootstrap_default_organization(session).id
    repo = EmbeddingProviderSettingsRepository(session)
    repo.upsert_config(org_id, provider, model, api_key, base_url, dimensions, chunk_size, chunk_overlap)
    repo.set_enabled(org_id, provider, True)
    return org_id


@pytest.fixture()
def storage(tmp_path):
    return UploadStorage(tmp_path)


@pytest.fixture()
def db_session(session_factory):
    from sqlalchemy import text

    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(
            text(
                "TRUNCATE TABLE chunks, documents, embedding_models, ingestion_jobs, sources, "
                "document_tags, tags, categories, query_results, queries, user_shelf_access, document_shelves, "
                "shelves, application_oauth_clients, applications, personal_access_tokens, "
                "mcp_settings, org_members, profile_permissions, profiles, identities, organizations "
                "CASCADE"
            )
        )
        session.commit()
        session.close()
