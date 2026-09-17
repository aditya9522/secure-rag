from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from docx import Document
from pypdf import PdfReader

from app.chunking import chunk_text
from app.config import settings
from app.models import Classification, Principal
from app.providers.openai_provider import OpenAIProvider
from app.providers.pinecone_provider import PineconeProvider


def extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        return content.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        import io

        if not content.startswith(b"%PDF-"):
            raise ValueError("The uploaded PDF signature is invalid")
        reader = PdfReader(io.BytesIO(content), strict=True)
        if len(reader.pages) > settings.max_pdf_pages:
            raise ValueError("PDF contains too many pages")
        extracted: list[str] = []
        extracted_chars = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            extracted_chars += len(page_text)
            if extracted_chars > settings.max_doc_chars:
                raise ValueError("Extracted document too large")
            extracted.append(page_text)
        return "\n".join(extracted)
    if suffix == ".docx":
        import io

        if not content.startswith(b"PK"):
            raise ValueError("The uploaded DOCX signature is invalid")
        try:
            with ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                uncompressed_bytes = sum(entry.file_size for entry in entries)
                if len(entries) > settings.max_archive_entries:
                    raise ValueError("DOCX contains too many archive entries")
                if uncompressed_bytes > settings.max_archive_uncompressed_bytes:
                    raise ValueError("DOCX expands beyond the parser resource limit")
                if "word/document.xml" not in archive.namelist():
                    raise ValueError("DOCX document content is missing")
        except BadZipFile as exc:
            raise ValueError("The uploaded DOCX archive is invalid") from exc
        doc = Document(io.BytesIO(content))
        extracted: list[str] = []
        extracted_chars = 0
        for paragraph in doc.paragraphs:
            extracted_chars += len(paragraph.text)
            if extracted_chars > settings.max_doc_chars:
                raise ValueError("Extracted document too large")
            extracted.append(paragraph.text)
        return "\n".join(extracted)
    raise ValueError("Unsupported file type; use .txt, .md, .csv, .json, .pdf, or .docx")


def validate_source_uri(source_uri: str | None) -> str | None:
    if source_uri is None:
        return None
    source_uri = source_uri.strip()
    if not source_uri or len(source_uri) > 2048:
        raise ValueError("source_uri must be a non-empty URI of at most 2048 characters")
    parsed = urlparse(source_uri)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError("source_uri must be an HTTP(S) URI without embedded credentials")
    return source_uri


# Keep the former private name available for callers that imported it while
# the API route adopts the explicit validation helper.
_validate_source_uri = validate_source_uri


def _embed_in_batches(provider: OpenAIProvider, chunks: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for start in range(0, len(chunks), settings.embedding_batch_size):
        embeddings.extend(provider.embed(chunks[start : start + settings.embedding_batch_size]))
    if len(embeddings) != len(chunks):
        raise RuntimeError("Embedding provider returned an incomplete document response")
    if any(len(vector) != settings.embedding_dimension for vector in embeddings):
        raise RuntimeError("Embedding provider returned an unexpected vector dimension")
    return embeddings


def _cleanup_vectors(
    pinecone: PineconeProvider, tenant_id: str, document_id: str, ids: list[str]
) -> None:
    cleanup = getattr(pinecone, "delete_document", None)
    if not callable(cleanup):
        return
    cleanup(tenant_id, document_id, ids)


def ingest_document(
    *,
    principal: Principal,
    filename: str,
    content: bytes,
    classification: Classification,
    allowed_groups: list[str],
    source_uri: str | None,
    provider: OpenAIProvider,
    pinecone: PineconeProvider,
    document_id: str | None = None,
    version: int = 1,
    activate: bool = True,
) -> dict:
    if not principal.can_read_classification(classification):
        raise PermissionError("Principal is not allowed to ingest at this classification")
    if len(content) > settings.max_upload_bytes:
        raise ValueError("Document too large")
    text = extract_text(filename, content)
    if len(text) > settings.max_doc_chars:
        raise ValueError("Extracted document too large")
    clean_groups = sorted({g.strip() for g in allowed_groups if g.strip()})
    if not clean_groups:
        clean_groups = [f"org:{principal.tenant_id}"]
    if f"user:{principal.user_id}" not in clean_groups:
        clean_groups.append(f"user:{principal.user_id}")
    principal_groups = set(principal.groups) | {
        f"org:{principal.tenant_id}",
        f"user:{principal.user_id}",
    }
    if not principal.can_manage_access and not set(clean_groups).issubset(principal_groups):
        raise PermissionError(
            "Principal cannot grant document access to groups outside its own scope"
        )
    if len(clean_groups) > 50 or any(len(group) > 128 for group in clean_groups):
        raise ValueError("Too many or overly long access groups")
    source_uri = validate_source_uri(source_uri)
    doc_hash = sha256(content).hexdigest()
    # A content hash is provenance, not identity: the same bytes can be two
    # independently governed documents with different ACLs and lifecycles.
    document_id = document_id or str(uuid4())
    chunks = chunk_text(text, settings.max_chunk_chars)
    if not chunks:
        raise ValueError("Document has no extractable text")
    embeddings = _embed_in_batches(provider, chunks)
    now = datetime.now(UTC).isoformat()
    rank = {
        Classification.public: 0,
        Classification.internal: 1,
        Classification.confidential: 2,
        Classification.restricted: 3,
    }[classification]
    records = []
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{document_id}:v{version}:{i}"
        records.append(
            {
                "id": chunk_id,
                "values": vector,
                "metadata": {
                    "tenant_id": principal.tenant_id,
                    "document_id": document_id,
                    "document_title": Path(filename).name[:256],
                    "chunk_id": chunk_id,
                    "chunk_number": i,
                    "text": chunk,
                    "allowed_groups": clean_groups,
                    "owner_user_id": principal.user_id,
                    "classification": classification.value,
                    "classification_rank": rank,
                    # Vectors stay invisible until every batch is written and
                    # the provider explicitly activates the document.
                    "active": False,
                    "source_uri": source_uri or "",
                    "source_hash": doc_hash,
                    "ingested_at": now,
                    "version": version,
                },
            }
        )
    record_ids = [record["id"] for record in records]
    try:
        pinecone.upsert(principal.tenant_id, records)
    except Exception as exc:
        try:
            _cleanup_vectors(pinecone, principal.tenant_id, document_id, record_ids)
        except Exception as cleanup_exc:
            raise RuntimeError(
                "Document indexing failed and staged vectors could not be cleaned"
            ) from cleanup_exc
        raise RuntimeError("Document indexing failed; staged vectors were cleaned") from exc
    if activate:
        pinecone.activate_document(principal.tenant_id, document_id, record_ids)
    return {
        "document_id": document_id,
        "chunks_indexed": len(records),
        "classification": classification,
        "source_uri": source_uri,
        "_record_ids": record_ids,
        "provenance": {"sha256": doc_hash, "ingested_at": now, "version": version},
    }
