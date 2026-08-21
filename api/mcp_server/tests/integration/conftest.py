from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from testcontainers.postgres import PostgresContainer

# Duplicated from api/tests/integration/conftest.py rather than imported — api/tests/ has no
# __init__.py (pytest doesn't need one for collection), so there's no clean package path to import
# its fixtures from; this is ~20 lines, smaller than restructuring how that directory is packaged
# just to share it.

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


@pytest.fixture(autouse=True)
def _patch_session_local(postgres_url, monkeypatch):
    """mcp_server/db.py's session_scope() (used by both tools.py and auth.py) opens its own
    SessionLocal() rather than taking an injected session — realistic for how the real process
    runs (no Flask g to share one from), but that name is bound to api.infrastructure.orm's
    module-level engine, which was constructed from DATABASE_URL at import time (the bogus
    default in tests/conftest.py), not this session's testcontainers URL. Point it at the real
    one for the duration of each test so tool calls actually see the data a test set up."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(postgres_url)
    monkeypatch.setattr("api.mcp_server.db.SessionLocal", sessionmaker(bind=engine))
    yield
    engine.dispose()


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
                "shelves, application_api_keys, application_oauth_clients, application_scopes, "
                "authorization_codes, refresh_tokens, applications, mcp_settings, "
                "org_members, profile_permissions, profiles, identities, organizations "
                "CASCADE"
            )
        )
        session.commit()
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _clear_auth_context():
    yield
    auth_context_var.set(None)


def authenticate_as(org_id, identity_id, scopes, mcp_access=True):
    """Simulates an already-authenticated connection the same way
    mcp.server.auth.middleware.auth_context.AuthContextMiddleware would for a real request — auth
    resolution itself (KnowledgeTokenVerifier) is unit-tested separately (test_auth.py)."""
    access_token = AccessToken(
        token="irrelevant",
        client_id=str(uuid4()),
        scopes=list(scopes),
        claims={
            "org_id": str(org_id),
            "identity_id": str(identity_id),
            "auth_method": "api_key",
            "mcp_access": mcp_access,
        },
    )
    auth_context_var.set(AuthenticatedUser(access_token))


def enable_tier(db_session, org_id, *, rag=False, read=False, write=False):
    """Seeds/updates the org's mcp_settings row directly (bypassing MCPSettingsService, which
    needs a real identity for last_modified_by) — every tool call gates on this being on for its
    tier before the caller's own scopes are even checked."""
    from api.infrastructure.repositories.mcp_settings_repository import MCPSettingsRepository

    MCPSettingsRepository(db_session).upsert(org_id, rag, read, write, None)
    db_session.commit()
