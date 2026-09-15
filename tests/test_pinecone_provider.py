import pytest

from app.providers.pinecone_provider import PineconeProvider


class FakeIndex:
    def __init__(self):
        self.updates = []

    def update(self, **kwargs):
        self.updates.append(kwargs)


def test_activate_document_uses_exact_vector_ids():
    provider = object.__new__(PineconeProvider)
    provider._index = FakeIndex()

    provider.activate_document("tenant-a", "doc-1", ["doc-1:0", "doc-1:1"])

    assert provider._index.updates == [
        {"id": "doc-1:0", "namespace": "tenant-a", "set_metadata": {"active": True}},
        {"id": "doc-1:1", "namespace": "tenant-a", "set_metadata": {"active": True}},
    ]


def test_activate_document_rejects_vectors_from_another_document():
    provider = object.__new__(PineconeProvider)
    provider._index = FakeIndex()

    with pytest.raises(ValueError, match="invalid vector IDs"):
        provider.activate_document("tenant-a", "doc-1", ["doc-2:0"])
