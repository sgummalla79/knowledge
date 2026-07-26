from app.domain.entities import ScoredChunk
from app.infrastructure.orm import Chunk


class ChunkRepository:
    def __init__(self, session):
        self._session = session

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
        return [
            ScoredChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                distance=distance,
            )
            for chunk, distance in rows
        ]
