# Security controls matrix

| Threat | Control | Enforcement point |
|---|---|---|
| Unauthorized retrieval | Fail-closed JWT + tenant check + groups + classification + post-filter re-check | API + Pinecone filter + application |
| Membership revocation | Active membership is re-read from PostgreSQL on every data request | API dependency + PostgreSQL |
| Cross-tenant leakage | one namespace per tenant | Pinecone |
| Credential/session theft | scrypt password hashes, short-lived access JWTs, hashed rotating refresh sessions in HttpOnly cookies, refresh-token reuse detection | Auth service + PostgreSQL |
| Prompt injection in documents | untrusted-data prompt + heuristic detection | retrieval/prompt assembly |
| Data poisoning | provenance + active/version metadata, inactive vector staging until complete, sanitized untrusted evidence | ingestion + retrieval |
| Hallucination | minimum score + grounded response + citation validation | retrieval/generation |
| PII leakage | PII pattern scan/redaction before model context and on output | retrieval + output |
| Secret leakage | secret pattern scan/redaction before model context and on output | retrieval + output |
| Harmful content | OpenAI moderation | input/output |
| Abuse / DoS | rate limit + input size limits | API |
| Audit gaps | structured security events | app |
| Dangerous future tools | explicit action policy | tool boundary |
| Sensitive logs | redaction before audit | audit logger |
| Resource exhaustion | bounded streaming uploads, parser/archive/page limits, retrieval/context limits, bounded provider retries | API + providers |
| Container compromise blast radius | non-root runtime user and production docs disabled | Docker + API |

## Security principles

1. The model is not an authorization engine.
2. Retrieved documents are data, not instructions.
3. Authorization is deterministic and testable outside the model.
4. Deny by default when evidence or permissions are insufficient.
5. Every answer should be traceable to retrieved source chunks.
6. Provider responses are untrusted until count, shape, authorization, and size checks pass.
