import pytest

from api.infrastructure.chunking.chunker import TextChunker


def test_split_produces_overlapping_windows():
    chunker = TextChunker(chunk_size=10, chunk_overlap=2)
    chunks = chunker.split("abcdefghijklmnopqrstuvwxyz")
    assert chunks == ["abcdefghij", "ijklmnopqr", "qrstuvwxyz"]


def test_split_empty_text_returns_no_chunks():
    chunker = TextChunker(chunk_size=10, chunk_overlap=2)
    assert chunker.split("") == []


def test_split_text_shorter_than_chunk_size_returns_single_chunk():
    chunker = TextChunker(chunk_size=100, chunk_overlap=10)
    assert chunker.split("short text") == ["short text"]


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        TextChunker(chunk_size=10, chunk_overlap=10)
