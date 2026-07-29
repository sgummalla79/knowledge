from sqlalchemy import func, text

from app.domain.entities import ScoredChunk
from app.infrastructure.orm import Chunk


class ChunkRepository:
    def __init__(self, session):
        self._session = session

    def count_for_document(self, document_id) -> int:
        return self._session.query(Chunk).filter(Chunk.document_id == document_id).count()

    def count_all(self) -> int:
        return self._session.query(Chunk).count()

    def resize_embedding_column(self, dimensions: int) -> None:
        """Only ever called when count_all() == 0 (enforced by EmbeddingSettingsService's
        model-switch lock) — mirrors the one-time 1024->768 cutover migration 0007 did by hand,
        generalized into a runtime operation.

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

    def bulk_create(self, document_id, library_id, chunks: list[tuple[int, str, list[float]]]) -> None:
        models = [
            Chunk(
                document_id=document_id,
                library_id=library_id,
                chunk_index=chunk_index,
                content=content,
                embedding=embedding,
            )
            for chunk_index, content, embedding in chunks
        ]
        self._session.add_all(models)
        self._session.flush()

    def similarity_search(self, library_id, query_embedding: list[float], top_k: int) -> list[ScoredChunk]:
        distance = Chunk.embedding.cosine_distance(query_embedding)
        rows = (
            self._session.query(Chunk, distance.label("distance"))
            .filter(Chunk.library_id == library_id)
            .order_by(distance)
            .limit(top_k)
            .all()
        )
        # Cosine distance is 0 (identical) to 2 (opposite) — invert to a higher-is-better score so
        # ScoredChunk.score never mixes lower-is-better and higher-is-better conventions.
        return [
            ScoredChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=1 - distance,
            )
            for chunk, distance in rows
        ]

    def sparse_search(self, library_id, query_text: str, top_k: int) -> list[ScoredChunk]:
        tsquery = func.plainto_tsquery("english", query_text)
        rank = func.ts_rank_cd(Chunk.content_tsv, tsquery)
        rows = (
            self._session.query(Chunk, rank.label("rank"))
            .filter(Chunk.library_id == library_id)
            .filter(Chunk.content_tsv.op("@@")(tsquery))
            .order_by(rank.desc())
            .limit(top_k)
            .all()
        )
        return [
            ScoredChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=rank,
            )
            for chunk, rank in rows
        ]
