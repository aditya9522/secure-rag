import re
from dataclasses import dataclass

from app.models import CLASSIFICATION_RANK, Classification, Principal

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+the\s+system\s+message",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"print\s+(the\s+)?api\s*key",
    r"disregard\s+(all\s+)?instructions",
    r"follow\s+these\s+instructions\s+instead",
    r"dump\s+(the\s+)?database",
]

SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (
        re.compile(
            r"-----BEGIN (?:RSA|EC|OPENSSH|PRIVATE) KEY-----.*?-----END (?:RSA|EC|OPENSSH|PRIVATE) KEY-----",
            re.DOTALL,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
]

PII_PATTERNS = [
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "[REDACTED_EMAIL]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (re.compile(r"\b(?:\+?\d[ -]?)?(?:\(?\d{3}\)?[ -]?)\d{3}[ -]?\d{4}\b"), "[REDACTED_PHONE]"),
]


@dataclass
class PolicyResult:
    allowed: bool
    flags: list[str]
    sanitized_text: str


def inspect_text(text: str) -> PolicyResult:
    flags: list[str] = []
    lowered = text.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            flags.append("prompt_injection_suspected")
            break
    sanitized = text
    for pattern, repl in SECRET_PATTERNS:
        if pattern.search(sanitized):
            flags.append("secret_detected")
            sanitized = pattern.sub(repl, sanitized)
    for pattern, repl in PII_PATTERNS:
        if pattern.search(sanitized):
            flags.append("pii_detected")
            sanitized = pattern.sub(repl, sanitized)
    return PolicyResult(
        allowed="prompt_injection_suspected" not in flags,
        flags=sorted(set(flags)),
        sanitized_text=sanitized,
    )


def sanitize_output(text: str) -> tuple[str, list[str]]:
    result = inspect_text(text)
    return result.sanitized_text, result.flags


def acl_filter(
    principal: Principal, active_document_versions: dict[str, int] | None = None
) -> dict:
    # AND clauses are intentionally generated only from authenticated claims.
    groups = list(
        dict.fromkeys(
            principal.groups + [f"org:{principal.tenant_id}", f"user:{principal.user_id}"]
        )
    )
    rank = {
        Classification.public: 0,
        Classification.internal: 1,
        Classification.confidential: 2,
        Classification.restricted: 3,
    }[principal.classification_max]
    clauses = [
        {"tenant_id": {"$eq": principal.tenant_id}},
        {"active": {"$eq": True}},
        {"allowed_groups": {"$in": groups}},
        {"classification_rank": {"$lte": rank}},
    ]
    if active_document_versions is not None:
        clauses.append(
            {
                "$or": [
                    {
                        "$and": [
                            {"document_id": {"$eq": document_id}},
                            {"version": {"$eq": version}},
                        ]
                    }
                    for document_id, version in active_document_versions.items()
                ]
            }
        )
    return {"$and": clauses}


def is_authorized_metadata(metadata: dict, principal: Principal) -> bool:
    """Re-check provider results before they cross into the model context."""
    if metadata.get("tenant_id") != principal.tenant_id or metadata.get("active") is not True:
        return False
    try:
        classification_rank = int(metadata["classification_rank"])
        classification = Classification(metadata["classification"])
    except (KeyError, TypeError, ValueError):
        return False
    allowed_groups = metadata.get("allowed_groups")
    if not isinstance(allowed_groups, list) or not all(
        isinstance(group, str) for group in allowed_groups
    ):
        return False
    principal_groups = set(principal.groups) | {
        f"org:{principal.tenant_id}",
        f"user:{principal.user_id}",
    }
    return (
        0 <= classification_rank <= max(CLASSIFICATION_RANK.values())
        and CLASSIFICATION_RANK[classification] == classification_rank
        and classification_rank <= CLASSIFICATION_RANK[principal.classification_max]
        and bool(principal_groups.intersection(allowed_groups))
    )


def can_view_document(
    *,
    status: str,
    classification: Classification | str,
    allowed_groups: list[str],
    principal: Principal,
) -> bool:
    """Apply the same visibility boundary to PostgreSQL document metadata."""
    if principal.can_manage_access:
        return True
    try:
        document_classification = Classification(classification)
    except ValueError:
        return False
    if status != "active" or not principal.can_read_classification(document_classification):
        return False
    principal_groups = set(principal.groups) | {
        f"org:{principal.tenant_id}",
        f"user:{principal.user_id}",
    }
    return bool(principal_groups.intersection(allowed_groups))
