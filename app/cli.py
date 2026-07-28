import argparse
import sys

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from app.constants import EMBEDDING_DIM
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.orm import SessionLocal

_DEFAULT_BATCH_SIZE = 100

# Lightweight Core table (not the ORM Chunk model) so this script can read/write the transitional
# `embedding_new` column, which migration 0007 renames away — keeping it out of the permanent ORM
# model that the rest of the app uses.
_chunks = sa.table(
    "chunks",
    sa.column("id"),
    sa.column("content"),
    sa.column("embedding_new", Vector(EMBEDDING_DIM)),
)


def reembed_chunks(
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    batch_size: int = _DEFAULT_BATCH_SIZE,
) -> int:
    """Backfills chunks.embedding_new for every row where it's still NULL, using the already-
    persisted `content` (original source files aren't stored, so no re-parsing/re-chunking is
    needed). Resumable: re-running only processes rows still missing embedding_new. Explicit,
    human-triggered operation — never invoked by the Dockerfile CMD or any migration. Must be run
    to completion (see the returned/logged total against a `SELECT count(*) ... WHERE embedding_new
    IS NULL`) before migration 0007 is applied.
    """
    provider_instance = EmbeddingProviderRegistry.resolve(provider, model, api_key, base_url)
    session = SessionLocal()
    total = 0
    try:
        while True:
            rows = session.execute(
                sa.select(_chunks.c.id, _chunks.c.content)
                .where(_chunks.c.embedding_new.is_(None))
                .order_by(_chunks.c.id)
                .limit(batch_size)
            ).all()
            if not rows:
                break

            vectors = provider_instance.embed_documents([row.content for row in rows])
            for row, vector in zip(rows, vectors):
                session.execute(
                    sa.update(_chunks).where(_chunks.c.id == row.id).values(embedding_new=vector)
                )
            session.commit()

            total += len(rows)
            print(f"reembed-chunks: {total} chunks processed", flush=True)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"reembed-chunks: done, {total} chunks total", flush=True)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    reembed_parser = subparsers.add_parser(
        "reembed-chunks",
        help="Backfill chunks.embedding_new for existing rows ahead of migration 0007's cutover.",
    )
    reembed_parser.add_argument("--provider", required=True)
    reembed_parser.add_argument("--model", required=True)
    reembed_parser.add_argument("--api-key", default=None)
    reembed_parser.add_argument("--base-url", default=None)
    reembed_parser.add_argument("--batch-size", type=int, default=_DEFAULT_BATCH_SIZE)

    args = parser.parse_args()

    if args.command == "reembed-chunks":
        try:
            reembed_chunks(args.provider, args.model, args.api_key, args.base_url, args.batch_size)
        except Exception as error:
            print(f"reembed-chunks: failed: {error}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
