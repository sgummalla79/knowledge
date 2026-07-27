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
                "TRUNCATE TABLE chunks, documents, libraries, embedding_settings, search_settings, "
                "users, applications, refresh_tokens CASCADE"
            )
        )
        session.commit()
        session.close()
        engine.dispose()
