from pinecone import Pinecone, ServerlessSpec

from app.config import settings


class PineconeProvider:
    def __init__(self) -> None:
        if not settings.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY is required")
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = settings.pinecone_index_name
        self._index = None

    @property
    def index(self):
        if self._index is None:
            self._index = self.pc.Index(self.index_name)
        return self._index

    def check_ready(self) -> None:
        self.pc.describe_index(self.index_name)

    @classmethod
    def create_index_if_needed(cls) -> None:
        pc = Pinecone(api_key=settings.pinecone_api_key)
        if not pc.has_index(settings.pinecone_index_name):
            pc.create_index(
                name=settings.pinecone_index_name,
                dimension=settings.embedding_dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud=settings.pinecone_cloud, region=settings.pinecone_region),
                deletion_protection=settings.pinecone_deletion_protection,
                tags={"environment": "secure-rag"},
            )

    def upsert(self, tenant_id: str, records: list[dict]) -> None:
        # Keep request sizes bounded so large documents do not monopolize one API call.
        for start in range(0, len(records), settings.embedding_batch_size):
            self.index.upsert(
                vectors=records[start : start + settings.embedding_batch_size],
                namespace=tenant_id,
            )

    def delete_document(
        self, tenant_id: str, document_id: str, record_ids: list[str] | None = None
    ) -> None:
        """Remove staged or revoked vectors without relying on metadata visibility."""
        if record_ids is not None:
            if not record_ids:
                return
            self.index.delete(ids=record_ids, namespace=tenant_id)
            return
        self.index.delete(
            namespace=tenant_id,
            filter={"document_id": {"$eq": document_id}},
        )

    def query(self, tenant_id: str, vector: list[float], top_k: int, filter_: dict):
        return self.index.query(
            namespace=tenant_id,
            vector=vector,
            top_k=top_k,
            filter=filter_,
            include_metadata=True,
            include_values=False,
        )

    def activate_document(self, tenant_id: str, document_id: str, record_ids: list[str]) -> None:
        """Make exactly the staged vectors for one document retrievable."""
        expected_prefix = f"{document_id}:"
        if not record_ids or any(
            not record_id.startswith(expected_prefix) for record_id in record_ids
        ):
            raise ValueError("Document activation received invalid vector IDs")
        # The Pinecone data-plane update API updates one vector by ID. Updating
        # exact IDs avoids unsupported filter-based updates and cross-document
        # activation when a namespace contains several staged uploads.
        for record_id in record_ids:
            self.index.update(
                id=record_id,
                namespace=tenant_id,
                set_metadata={"active": True},
            )
