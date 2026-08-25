from sqlalchemy import func, text

from api.domain.entities import Chunk as ChunkEntity
from api.domain.entities import ScoredChunk
from api.infrastructure.orm import Chunk, Document


def _to_entity(model: Chunk) -> ChunkEntity:
    return ChunkEntity(
        id=model.id,
        document_id=model.document_id,
        ordinal=model.ordinal,
        content=model.content,
        token_count=model.token_count,
        created_at=model.created_at,
    )


class ChunkRepository:
    def __init__(self, session):
        self._session = session

    def count_for_document(self, document_id) -> int:
        return self._session.query(Chunk).filter(Chunk.document_id == document_id).count()

    def count_all(self) -> int:
        return self._session.query(Chunk).count()

    def count_for_org(self, org_id) -> int:
        return self._session.query(Chunk).filter(Chunk.org_id == org_id).count()

    def delete_for_document(self, document_id) -> None:
        """Called at the start of IngestionService._process() (every attempt, not just a retry) so
        a retry after a partial failure can't leave duplicate chunks behind. Now that chunks are
        persisted in batches as they're embedded (see INGESTION_EMBED_BATCH_SIZE) rather than all
        at once at the end, a failure partway through a document can leave some batches already
        committed -- a no-op the first time any given document is ingested, since there's nothing
        to delete yet."""
        self._session.query(Chunk).filter(Chunk.document_id == document_id).delete()

    def list_for_document(self, document_id, limit: int, offset: int) -> list[ChunkEntity]:
        models = (
            self._session.query(Chunk)
            .filter(Chunk.document_id == document_id)
            .order_by(Chunk.ordinal.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_to_entity(model) for model in models]

    def resize_embedding_column(self, dimensions: int) -> None:
        """Only ever called when count_all() == 0 (enforced by EmbeddingProviderConfigService's
        model-switch lock) — a runtime operation since `chunks.embedding` is dimensionless (see
        the ORM class docstring: per-org "bring your own model" means a single fixed-width column
        can't represent every org's chosen dimensions).

        `vector(N)` is a type modifier, not a data value — Postgres doesn't accept a bind
        parameter there, so `dimensions` is interpolated directly. Safe only because it's an
        int (pydantic-validated upstream as `gt=0`), never a caller-supplied string.
        """
        if not isinstance(dimensions, int) or dimensions <= 0:
            raise ValueError(f"dimensions must be a positive int, got {dimensions!r}")
        self._session.execute(text("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw"))
        self._session.execute(text(f"ALTER TABLE chunks ALTER COLUMN embedding TYPE vector({dimensions})"))
        self._session.execute(
            text("CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")
        )

    def bulk_create(
        self, document_id, org_id, embedding_model_id, chunks: list[tuple[int, str, int, list[float]]]
    ) -> None:
        models = [
            Chunk(
                document_id=document_id,
                org_id=org_id,
                embedding_model_id=embedding_model_id,
                ordinal=ordinal,
                content=content,
                token_count=token_count,
                embedding=embedding,
            )
            for ordinal, content, token_count, embedding in chunks
        ]
        # A SAVEPOINT, not the outer transaction directly. A flush failure here (e.g. content
        # Postgres rejects outright, like an embedded NUL byte) otherwise poisons the *entire*
        # session — every later statement on it raises PendingRollbackError until an explicit
        # rollback(), including IngestionService._process()'s own except block trying to mark the
        # document "failed". That's a real incident this fixed: the document row (already flushed
        # earlier in the same uncommitted transaction) got silently wiped by the eventual rollback,
        # and the ingestion job never reached completed *or* failed — it just hung forever from the
        # client's point of view. Scoping the insert to a nested transaction means a failure here
        # only rolls back this savepoint, leaving the rest of the job's work intact and the session
        # perfectly usable for the "mark failed" write that follows.
        with self._session.begin_nested():
            self._session.add_all(models)
            self._session.flush()

    def similarity_search(
        self, org_id, query_embedding: list[float], top_k: int, category_id=None
    ) -> list[ScoredChunk]:
        distance = Chunk.embedding.cosine_distance(query_embedding)
        query = self._session.query(Chunk, distance.label("distance")).filter(Chunk.org_id == org_id)
        if category_id is not None:
            # Chunks don't carry category_id directly (only org_id, denormalized for RLS/ANN) —
            # scoping to a category means joining through the parent document, the only place
            # category_id actually lives.
            query = query.join(Document, Document.id == Chunk.document_id).filter(
                Document.category_id == category_id
            )
        rows = query.order_by(distance).limit(top_k).all()
        # Cosine distance is 0 (identical) to 2 (opposite) — invert to a higher-is-better score so
        # ScoredChunk.score never mixes lower-is-better and higher-is-better conventions.
        return [
            ScoredChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                ordinal=chunk.ordinal,
                content=chunk.content,
                score=1 - distance,
            )
            for chunk, distance in rows
        ]

    def sparse_search(self, org_id, query_text: str, top_k: int, category_id=None) -> list[ScoredChunk]:
        tsquery = func.plainto_tsquery("english", query_text)
        rank = func.ts_rank_cd(Chunk.content_tsv, tsquery)
        query = (
            self._session.query(Chunk, rank.label("rank"))
            .filter(Chunk.org_id == org_id)
            .filter(Chunk.content_tsv.op("@@")(tsquery))
        )
        if category_id is not None:
            query = query.join(Document, Document.id == Chunk.document_id).filter(
                Document.category_id == category_id
            )
        rows = query.order_by(rank.desc()).limit(top_k).all()
        return [
            ScoredChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                ordinal=chunk.ordinal,
                content=chunk.content,
                score=rank,
            )
            for chunk, rank in rows
        ]
