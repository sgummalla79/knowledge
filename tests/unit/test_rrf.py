from uuid import uuid4

from app.application.rrf import reciprocal_rank_fusion


def test_single_list_preserves_order():
    a, b, c = uuid4(), uuid4(), uuid4()
    fused = reciprocal_rank_fusion([[a, b, c]], k=60)
    assert [doc_id for doc_id, _ in fused] == [a, b, c]


def test_disjoint_lists_interleave_by_rank():
    a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
    # a/c rank 1st in their own lists, so both score 1/(60+1) — a doc appearing 1st in only one
    # list should still outrank a doc that appears 2nd in a list it's also present in.
    fused = reciprocal_rank_fusion([[a, b], [c, d]], k=60)
    scores = dict(fused)
    assert scores[a] == scores[c]
    assert scores[a] > scores[b]
    assert scores[c] > scores[d]


def test_overlapping_doc_outranks_single_list_doc():
    a, b, c = uuid4(), uuid4(), uuid4()
    # `a` appears first in both lists; `b`/`c` only ever appear in one list each.
    fused = reciprocal_rank_fusion([[a, b], [a, c]], k=60)
    scores = dict(fused)
    assert scores[a] == 2 * (1.0 / 61)
    assert scores[a] > scores[b]
    assert scores[a] > scores[c]


def test_empty_lists_produce_empty_result():
    assert reciprocal_rank_fusion([], k=60) == []
    assert reciprocal_rank_fusion([[], []], k=60) == []


def test_doc_absent_from_a_list_gets_no_contribution_from_it():
    a, b = uuid4(), uuid4()
    fused = reciprocal_rank_fusion([[a, b]], k=60)
    scores = dict(fused)
    assert scores[a] == 1.0 / 61
    assert scores[b] == 1.0 / 62


def test_smaller_k_widens_the_gap_between_ranks():
    a, b = uuid4(), uuid4()
    small_k_scores = dict(reciprocal_rank_fusion([[a, b]], k=1))
    large_k_scores = dict(reciprocal_rank_fusion([[a, b]], k=1000))
    small_gap = small_k_scores[a] - small_k_scores[b]
    large_gap = large_k_scores[a] - large_k_scores[b]
    assert small_gap > large_gap
