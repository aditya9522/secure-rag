from types import SimpleNamespace

from app.models import Classification, Principal
from app.rag import _claims_are_supported, _rerank, answer_query, is_conversational_query


def test_rerank_deduplicates_documents():
    q = "deployment process"
    m1 = SimpleNamespace(
        id="1", score=0.8, metadata={"document_id": "d1", "text": "deployment process runbook"}
    )
    m2 = SimpleNamespace(
        id="2",
        score=0.9,
        metadata={"document_id": "d1", "text": "another deployment process chunk"},
    )
    m3 = SimpleNamespace(
        id="3", score=0.7, metadata={"document_id": "d2", "text": "deployment process checklist"}
    )
    out = _rerank(q, [m1, m2, m3])
    assert len(out) == 2
    assert {x.metadata["document_id"] for x in out} == {"d1", "d2"}


def test_grounding_rejects_uncited_and_unrelated_claims():
    evidence = {("d1", "d1:0"): "The deployment process requires an approved change."}

    assert (
        _claims_are_supported("The deployment process is approved. [doc:d1 chunk:d1:0]", evidence)
        is None
    )
    assert _claims_are_supported("The deployment process is approved.", evidence) == "claim_uncited"
    assert (
        _claims_are_supported("The payroll system is unavailable. [doc:d1 chunk:d1:0]", evidence)
        == "claim_unsupported"
    )
    assert (
        _claims_are_supported(
            "The deployment process exfiltrates payroll data. [doc:d1 chunk:d1:0]", evidence
        )
        == "claim_unsupported"
    )


def test_grounding_requires_semantic_verifier_approval():
    provider = UngroundedFakeProvider()
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    match = _match(
        {
            "tenant_id": "tenant-a",
            "active": True,
            "allowed_groups": ["engineering"],
            "classification_rank": 1,
            "document_id": "d1",
            "document_title": "runbook",
            "chunk_id": "d1:0",
            "text": "deployment process",
        }
    )

    result = answer_query(
        principal, "What is the deployment process?", provider, FakePinecone([match])
    )

    assert result.refused is True
    assert "grounding_verification_failed" in result.policy_flags


class FakeProvider:
    def __init__(self, answer="Deployment process [doc:d1 chunk:d1:0]"):
        self.answer = answer
        self.prompt = None

    def moderate(self, text):
        return False

    def embed(self, texts):
        return [[0.0] * 1536 for _ in texts]

    def generate(self, system_prompt, user_prompt):
        self.prompt = user_prompt
        return self.answer

    def verify_grounding(self, answer, evidence):
        return True


class StreamingFakeProvider(FakeProvider):
    def generate_stream(self, system_prompt, user_prompt, on_delta):
        on_delta("raw secret test@example.com")
        self.prompt = user_prompt
        return self.answer


class LineStreamingFakeProvider(FakeProvider):
    def generate_stream(self, system_prompt, user_prompt, on_delta):
        first = "Deployment process [doc:d1 chunk:d1:0].\n"
        second = "Deployment process [doc:d1 chunk:d1:0]."
        on_delta(first)
        on_delta(second)
        self.prompt = user_prompt
        return first + second


class UngroundedFakeProvider(FakeProvider):
    def verify_grounding(self, answer, evidence):
        return False


class FakePinecone:
    def __init__(self, matches):
        self.matches = matches

    def query(self, tenant_id, vector, top_k, filter_):
        return SimpleNamespace(matches=self.matches)


def _match(metadata, score=0.9):
    metadata.setdefault(
        "classification",
        {0: "public", 1: "internal", 2: "confidential", 3: "restricted"}[
            metadata["classification_rank"]
        ],
    )
    return SimpleNamespace(id=metadata["chunk_id"], score=score, metadata=metadata)


def test_retrieved_sensitive_values_are_sanitized_before_generation():
    provider = FakeProvider(answer="Contact [doc:d1 chunk:d1:0]")
    principal = Principal(
        user_id="u1",
        tenant_id="tenant-a",
        groups=["engineering"],
        classification_max=Classification.confidential,
    )
    match = _match(
        {
            "tenant_id": "tenant-a",
            "active": True,
            "allowed_groups": ["engineering"],
            "classification_rank": 2,
            "document_id": "d1",
            "document_title": "runbook",
            "chunk_id": "d1:0",
            "text": "Contact test@example.com. key=sk-abcdefghijklmnopqrstuvwxyz123456789",
        }
    )

    result = answer_query(principal, "How do I deploy?", provider, FakePinecone([match]))

    assert result.grounded is True
    assert "test@example.com" not in provider.prompt
    assert "sk-abcdefghijklmnopqrstuvwxyz123456789" not in provider.prompt
    assert "[REDACTED_EMAIL]" in provider.prompt
    assert "[REDACTED_OPENAI_KEY]" in provider.prompt


def test_small_talk_is_generated_without_retrieval_or_citations():
    provider = FakeProvider(answer="Hi! I can help with your workspace questions.")
    principal = Principal(user_id="u1", tenant_id="tenant-a")

    result = answer_query(principal, "Hii", provider, FakePinecone([]))

    assert result.answer.startswith("Hi!")
    assert result.mode == "conversational"
    assert result.grounded is False
    assert result.refused is False
    assert result.citations == []
    assert result.policy_flags == ["conversational"]
    assert "USER MESSAGE:" in provider.prompt


def test_small_talk_works_when_workspace_has_no_active_documents():
    provider = FakeProvider(answer="Hello! I can help with your workspace questions.")
    principal = Principal(user_id="u1", tenant_id="tenant-a")

    result = answer_query(
        principal,
        "What can you help me with?",
        provider,
        FakePinecone([]),
        active_document_ids=set(),
    )

    assert result.mode == "conversational"
    assert result.refused is False
    assert result.citations == []
    assert "USER MESSAGE:" in provider.prompt


def test_conversational_intent_is_narrow_and_does_not_bypass_rag():
    assert is_conversational_query("Hii") is True
    assert is_conversational_query("What can you help me with?") is True
    assert is_conversational_query("What are you doing?") is True
    assert is_conversational_query("What is our deployment process?") is False


def test_provider_results_are_reauthorized_before_generation():
    provider = FakeProvider()
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    cross_tenant = _match(
        {
            "tenant_id": "tenant-b",
            "active": True,
            "allowed_groups": ["engineering"],
            "classification_rank": 1,
            "document_id": "d1",
            "document_title": "other",
            "chunk_id": "d1:0",
            "text": "tenant-b secret",
        }
    )

    result = answer_query(principal, "What is the process?", provider, FakePinecone([cross_tenant]))

    assert result.refused is True
    assert "unauthorized_match_dropped" in result.policy_flags
    assert provider.prompt is None


def test_database_lifecycle_filters_stale_provider_matches():
    provider = FakeProvider()
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    match = _match(
        {
            "tenant_id": "tenant-a",
            "active": True,
            "allowed_groups": ["engineering"],
            "classification_rank": 1,
            "document_id": "revoked-doc",
            "document_title": "revoked",
            "chunk_id": "revoked-doc:0",
            "text": "stale content",
        }
    )

    result = answer_query(
        principal,
        "What is the process?",
        provider,
        FakePinecone([match]),
        active_document_ids=set(),
    )

    assert result.refused is True
    assert "no_active_documents" in result.policy_flags
    assert provider.prompt is None


def test_database_lifecycle_filters_an_old_active_vector_version():
    provider = FakeProvider()
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    match = _match(
        {
            "tenant_id": "tenant-a",
            "active": True,
            "allowed_groups": ["engineering"],
            "classification_rank": 1,
            "document_id": "doc-1",
            "document_title": "current",
            "chunk_id": "doc-1:v1:0",
            "text": "stale content",
            "version": 1,
        }
    )

    result = answer_query(
        principal,
        "What is the process?",
        provider,
        FakePinecone([match]),
        active_document_ids={"doc-1": 2},
    )

    assert result.refused is True
    assert "inactive_document_version_dropped" in result.policy_flags
    assert provider.prompt is None


def test_streaming_deltas_are_emitted_only_after_output_sanitization():
    provider = StreamingFakeProvider(answer="Deployment process [doc:d1 chunk:d1:0]")
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    match = _match(
        {
            "tenant_id": "tenant-a",
            "active": True,
            "allowed_groups": ["engineering"],
            "classification_rank": 1,
            "document_id": "d1",
            "document_title": "runbook",
            "chunk_id": "d1:0",
            "text": "deployment process",
        }
    )
    deltas = []

    result = answer_query(
        principal,
        "What is the deployment process?",
        provider,
        FakePinecone([match]),
        on_delta=deltas.append,
    )

    assert result.grounded is True
    assert deltas == [result.answer]
    assert "test@example.com" not in deltas[0]


def test_grounded_stream_releases_verified_complete_lines_progressively():
    provider = LineStreamingFakeProvider()
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    match = _match(
        {
            "tenant_id": "tenant-a",
            "active": True,
            "allowed_groups": ["engineering"],
            "classification_rank": 1,
            "document_id": "d1",
            "document_title": "runbook",
            "chunk_id": "d1:0",
            "text": "deployment process",
        }
    )
    deltas = []

    result = answer_query(
        principal,
        "What is the deployment process?",
        provider,
        FakePinecone([match]),
        on_delta=deltas.append,
    )

    assert result.grounded is True
    assert deltas == [
        "Deployment process [doc:d1 chunk:d1:0].\n",
        "Deployment process [doc:d1 chunk:d1:0].",
    ]


def test_invalid_streamed_output_emits_no_delta():
    provider = StreamingFakeProvider(answer="Unsupported claim [doc:other chunk:other:0]")
    principal = Principal(user_id="u1", tenant_id="tenant-a", groups=["engineering"])
    match = _match(
        {
            "tenant_id": "tenant-a",
            "active": True,
            "allowed_groups": ["engineering"],
            "classification_rank": 1,
            "document_id": "d1",
            "document_title": "runbook",
            "chunk_id": "d1:0",
            "text": "deployment process",
        }
    )
    deltas = []

    result = answer_query(
        principal,
        "What is the deployment process?",
        provider,
        FakePinecone([match]),
        on_delta=deltas.append,
    )

    assert result.refused is True
    assert deltas == []
