import pytest

from app.chunking import chunk_text


def test_chunking_is_bounded():
    chunks = chunk_text("a" * 15000, max_chars=1000, overlap=100)
    assert chunks
    assert all(len(c) <= 1000 for c in chunks)


@pytest.mark.parametrize(("max_chars", "overlap"), [(0, 0), (10, 10), (10, 11)])
def test_chunking_rejects_non_progressing_limits(max_chars, overlap):
    with pytest.raises(ValueError):
        chunk_text("content", max_chars=max_chars, overlap=overlap)
