from uuid import UUID


def reciprocal_rank_fusion(ranked_id_lists: list[list[UUID]], k: int) -> list[tuple[UUID, float]]:
    """Fuse multiple ranked ID lists into one ordering via Reciprocal Rank Fusion.

    Each list contributes 1/(k + rank) to an id's score (rank is 1-based); ids absent from a list
    contribute nothing for it. Returns (id, fused_score) pairs sorted by score descending.
    """
    scores: dict[UUID, float] = {}
    for ranked_list in ranked_id_lists:
        for rank, doc_id in enumerate(ranked_list, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
