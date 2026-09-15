# Secure RAG system review — historical baseline

Review date: 2026-09-04 (baseline; implementation continued afterward)  
Scope: all application code, configuration, container/deployment files, documentation, and tests in this workspace.

> This document records the initial security review findings and is retained as an audit trail. It is not the current implementation status. The follow-up implementation added PostgreSQL persistence/migrations, immediate membership checks, refresh-session rotation, document revocation, async provider offloading, opaque document IDs, sanitized provider input, development-token environment guards, and the conversational query path. Re-run the security review against the current tree before production release.

## Executive summary

The existing unit suite passes (`16 passed`), Python compilation passes, and Ruff lint passes. The suite does not exercise the full HTTP/provider lifecycle, so several material defects remain. The highest-risk issues are authentication acceptance of non-expiring tokens, sensitive user input being sent to the model provider without sanitization, and an enabled development token issuer that can mint arbitrary tenant/admin claims outside production.

## Findings

### H-01 — JWTs without an expiration claim are accepted

Severity: High  
Category: OWASP A07 — Authentication Failures  
Status: Confirmed

Evidence: [`app/security/auth.py:15-22`](/home/adi/Projects/rag-guardrails/app/security/auth.py:15) calls `jwt.decode` with issuer and audience validation but does not require `exp`. PyJWT validates `exp` only when the claim is present. The subsequent claim parsing requires `sub` and `tenant_id`, but not expiration.

Impact: A validly signed token issued without `exp` remains usable indefinitely. This defeats token lifetime controls and makes compromise or failure to revoke an identity materially worse.

Remediation: Require `exp`, `iat`, `sub`, and `tenant_id` in the JWT decode options; enforce a bounded maximum lifetime and add revocation/key-rotation handling appropriate to the identity provider.

Regression test: Decode a correctly signed token with no `exp` and assert HTTP 401; test expired and excessively long-lived tokens as well.

### H-02 — Development token issuance is not restricted to development

Severity: High when enabled in staging or a shared environment  
Category: OWASP A01/A07 — Broken Access Control / Authentication Failures  
Status: Confirmed conditional configuration gap

Evidence: [`app/main.py:107-130`](/home/adi/Projects/rag-guardrails/app/main.py:107) allows an unauthenticated caller to choose `user_id`, `tenant_id`, groups, `classification_max`, and `can_manage_access`. [`app/config.py:65-74`](/home/adi/Projects/rag-guardrails/app/config.py:65) rejects this only when `environment == "production"`; staging and other shared environments can still enable it.

Impact: Anyone who can reach the endpoint can mint a token for another tenant with restricted classification and access-management privileges. This can expose or alter all data reachable through that tenant's namespace if the deployment contains non-test data.

Remediation: Make the endpoint compile-time/local-development-only or require `environment == "development"` plus an explicit loopback-only binding. Remove the caller-controlled administrative claim; use a fixed synthetic tenant and fixed low-privilege identity. Add a startup failure for any non-development environment with this flag enabled.

Regression test: Instantiate staging settings with `ALLOW_LOCAL_DEV_TOKENS=true` and assert configuration failure; verify the endpoint is unavailable from a non-development app.

### H-03 — Sensitive query input is forwarded to external providers unsanitized

Severity: High for confidential/regulated data  
Category: OWASP A06 — Insecure Design (external-provider data boundary)  
Status: Confirmed

Evidence: [`app/rag.py:50-68`](/home/adi/Projects/rag-guardrails/app/rag.py:50) inspects the query but then passes the original `query` to moderation and embedding. [`app/rag.py:148-149`](/home/adi/Projects/rag-guardrails/app/rag.py:148) places the original query in the generation prompt. Only retrieved document text is replaced with `policy.sanitized_text`.

Reproduction: A query containing `test@example.com` was observed unchanged in the fake provider's moderation, embedding, and generation calls.

Impact: User-entered email addresses, phone numbers, and recognizable API/private-token formats are disclosed to the external moderation, embedding, and generation services. This contradicts the documented “before model context” control and may violate data-handling requirements.

Remediation: Define the provider data boundary explicitly. At minimum use the sanitized query for every provider call and generation prompt; for high-confidence secrets, refuse rather than forwarding a redacted approximation. Apply the same policy before moderation if moderation is an external service.

Regression test: Assert that no detected secret or PII value appears in any provider call, not only in the final generation prompt.

### H-04 — Document access cannot be revoked or deactivated

Severity: High for incident response and ACL changes  
Category: OWASP A01/A06 — Broken Access Control / Insecure Design  
Status: Confirmed implementation gap

Evidence: [`app/ingest.py:112-127`](/home/adi/Projects/rag-guardrails/app/ingest.py:112) writes every vector with `active=True` and `version=1`. There is no document update, delete, ACL-revoke, or version-management API; the only exposed data operation is upload/query ([`app/main.py:136-228`](/home/adi/Projects/rag-guardrails/app/main.py:136)).

Impact: Operators cannot promptly remove a leaked document, revoke a group, or deactivate poisoned content. Existing vectors remain queryable until an unrelated re-upload happens, and the advertised `active`/`version` controls are not operational lifecycle controls.

Remediation: Add an authorization-checked document lifecycle backed by a source-of-truth store: revoke/deactivate before deleting vectors, maintain monotonically increasing versions, and make query filtering select only the current active version. Define owner/admin rules and audit every change.

Regression test: Upload a document, revoke it, and assert it is excluded even if Pinecone still returns the old vector; test cross-user and cross-tenant revoke denial.

### M-01 — Synchronous provider work blocks the async upload event loop

Severity: Medium/High availability risk  
Category: OWASP A10 — Mishandling of Exceptional Conditions  
Status: Confirmed

Evidence: [`app/main.py:138-164`](/home/adi/Projects/rag-guardrails/app/main.py:138) defines `upload_document` as `async` but directly calls synchronous [`ingest_document`](/home/adi/Projects/rag-guardrails/app/ingest.py:61), which performs synchronous OpenAI calls and Pinecone upserts.

Impact: One slow provider request or large upload blocks the event loop and delays unrelated health, auth, and query requests. Concurrent uploads can make the service appear unavailable even though the process is alive.

Remediation: Either make the route synchronous so FastAPI moves it to its worker pool, or explicitly run the blocking ingestion in a bounded thread/process pool. Add an overall operation deadline and concurrency limit.

Regression test: Run a deliberately blocking fake ingestion and assert an independent async health request remains responsive; test the configured concurrency ceiling.

### M-02 — Partial Pinecone writes are exposed as a failed-but-queryable document

Severity: Medium  
Category: OWASP A08/A10 — Data Integrity / Exceptional Conditions  
Status: Confirmed

Evidence: [`app/providers/pinecone_provider.py:35-44`](/home/adi/Projects/rag-guardrails/app/providers/pinecone_provider.py:35) upserts batches sequentially with no transaction or rollback. [`app/ingest.py:131`](/home/adi/Projects/rag-guardrails/app/ingest.py:131) returns only after all batches succeed.

Reproduction: A fake Pinecone provider that failed on batch two retained batch one while the API-level operation failed.

Impact: A caller receives a 503, but authorized users can retrieve an incomplete document. Retries and concurrent re-uploads can leave inconsistent content and citations.

Remediation: Stage records under a unique version, write a manifest/status record, and make query visibility conditional on a completed manifest. On failure, delete the staged version or mark it inactive; use idempotency keys for retries.

Regression test: Fail each batch in turn and assert no incomplete version is returned by query.

### M-03 — Content hash is used as a document identity and overwrites metadata

Severity: Medium; can become an ACL integrity issue  
Category: OWASP A01/A08 — Access-Control/Data Integrity  
Status: Confirmed

Evidence: [`app/ingest.py:92-107`](/home/adi/Projects/rag-guardrails/app/ingest.py:92) derives `document_id` from only the first 24 characters of the content hash and uses it in every vector ID. Filename, classification, groups, source URI, owner, and version are not part of the identity.

Reproduction: Uploading identical bytes twice with different filenames/classification produced the same `document_id`; the second upload replaced the stored metadata.

Impact: Re-uploading the same bytes silently changes the existing document's title, provenance, classification, and ACL metadata. A user with access to the bytes can unintentionally or deliberately alter another logical document, and a 24-hex-character prefix also has a collision risk at scale.

Remediation: Use a server-generated opaque document ID or an immutable source-system ID. Treat content hash as provenance/deduplication metadata only. Version and ACL changes must be explicit, authorized operations rather than implicit vector overwrites.

Regression test: Upload identical content as two logical documents and assert independent IDs and metadata; test an explicit update path separately.

### M-04 — Citation presence is treated as proof of grounding

Severity: Medium integrity risk  
Category: OWASP A06 — Insecure Design  
Status: Confirmed

Evidence: [`app/rag.py:169-190`](/home/adi/Projects/rag-guardrails/app/rag.py:169) checks only that the generated text contains one citation pair belonging to a retrieved chunk. It does not verify that claims are entailed by that chunk, that cited chunks support the claims, or that all factual claims have citations.

Reproduction: The answer `The evidence proves an unrelated claim. [doc:d1 chunk:d1:0]` was returned with `grounded=True` even though the chunk stated something different.

Impact: Clients may trust unsupported or hallucinated statements because the response advertises them as grounded. This weakens the primary integrity guarantee of the service.

Remediation: Use structured generation with claim-to-citation fields, validate citation IDs against retrieved evidence, and run a bounded entailment/grounding check or return an explicitly unverified answer state. Do not equate citation syntax with factual support.

Regression test: Include contradictory, partially supported, and uncited claims and assert refusal or `grounded=False`.

### M-05 — File parsing is extension-based and lacks decompression/parser resource limits

Severity: Medium availability/security risk  
Category: OWASP A10 — Mishandling of Exceptional Conditions (resource exhaustion)  
Status: Confirmed

Evidence: [`app/ingest.py:16-30`](/home/adi/Projects/rag-guardrails/app/ingest.py:16) selects parsers from the client-controlled filename suffix. The upload byte limit is checked before extraction, but there are no MIME/signature checks, PDF page/object limits, DOCX/ZIP expansion limits, parser timeout, or extracted-structure limits beyond total text length.

Impact: A small malformed file or compression bomb can consume excessive CPU/memory in `pypdf` or `python-docx`; a polyglot or mislabeled file can be processed by an unexpected parser. The text-length check occurs after parsing, so it does not protect parser resource use.

Remediation: Validate magic bytes and permitted MIME types, inspect archive expansion before parsing, cap pages/relationships/paragraphs, isolate parsing with resource/time limits, and reject malformed or ambiguous files.

Regression test: Exercise mislabeled files, oversized PDF page counts, and ZIP-bomb fixtures under a bounded parser worker.

### M-06 — Provider retry policy amplifies cost and request occupancy

Severity: Medium  
Category: OWASP A06/A10 — Insecure Design / Resource Exhaustion  
Status: Confirmed

Evidence: [`app/providers/openai_provider.py:11-58`](/home/adi/Projects/rag-guardrails/app/providers/openai_provider.py:11) retries timeout, connection, server, and rate-limit failures three times for embeddings and moderation; generation has the same policy ([`app/providers/openai_provider.py:60-76`](/home/adi/Projects/rag-guardrails/app/providers/openai_provider.py:60)). A query can therefore perform up to three attempts for each of three provider operations, while API limiting is primarily by remote IP ([`app/main.py:36-40`](/home/adi/Projects/rag-guardrails/app/main.py:36)).

Impact: Distributed callers can multiply provider spend and hold worker capacity during an outage or rate-limit event. Retrying rate-limit responses can worsen upstream throttling.

Remediation: Use bounded total request deadlines, retry only explicitly retryable failures, honor provider retry metadata, add per-tenant/user concurrency and spend quotas, and use a circuit breaker for sustained provider failure.

Regression test: Count provider attempts for timeout/rate-limit scenarios and assert the total budget and circuit-breaker behavior.

### M-07 — Dependency resolution is not reproducible or integrity-pinned

Severity: Medium supply-chain risk  
Category: OWASP A03 — Software Supply Chain Failures  
Status: Confirmed

Evidence: [`pyproject.toml:5-25`](/home/adi/Projects/rag-guardrails/pyproject.toml:5) uses version ranges, and [`Dockerfile:5-8`](/home/adi/Projects/rag-guardrails/Dockerfile:5) installs directly from the live package index without a lock file or hashes.

Impact: Rebuilding the same source can select different transitive dependencies, including a vulnerable or incompatible release. This also makes incident reproduction and patch verification difficult.

Remediation: Commit a lock file with hashes, use a controlled package index or provenance policy, pin the base image by digest, and run dependency/SBOM/vulnerability checks in CI.

Regression/check: Rebuild from a clean environment and verify the resolved dependency set is identical; fail CI on unapproved dependency changes.

### M-08 — Index creation explicitly disables deletion protection

Severity: Medium availability/data-loss risk  
Category: OWASP A02 — Security Misconfiguration  
Status: Confirmed

Evidence: [`app/providers/pinecone_provider.py:26-33`](/home/adi/Projects/rag-guardrails/app/providers/pinecone_provider.py:26) creates the index with `deletion_protection="disabled"`, and [`scripts/create_index.py:4-7`](/home/adi/Projects/rag-guardrails/scripts/create_index.py:4) has no environment guard.

Impact: Running the setup script with production credentials permits an operational mistake or compromised credential to delete the entire vector index without a provider-side safety barrier.

Remediation: Enable deletion protection by default for staging/production, require an explicit narrowly scoped override for disposable development indexes, and separate index provisioning credentials from runtime query/upsert credentials.

Regression/check: Assert production settings reject a disposable-index configuration and inspect the created index for deletion protection.

## Lower-priority gaps and observations

- `ruff check .` passes, but `ruff format --check .` fails on [`app/config.py:31`](/home/adi/Projects/rag-guardrails/app/config.py:31). This is a CI/reproducibility gap because `BUILD_STATUS.md` says formatting checks passed.
- The application has no HTTP-level tests for authentication enforcement, upload limits, provider failures, rate limits, response headers, or readiness. The current tests are useful unit tests but cannot catch route wiring and deployment behavior.
- Audit events cover successful queries and selected provider/ingestion failures, but invalid-token attempts, token issuance attempts that are disabled, ACL/filter anomalies, and document lifecycle changes are not consistently recorded. Add redacted security-event metrics with alerting and retention controls.
- The configured default chat model is not validated at startup or in a smoke test ([`app/config.py:18`](/home/adi/Projects/rag-guardrails/app/config.py:18)). If `gpt-5.6-luna` is not an available deployment/model alias, every generation request fails only at runtime. Make the model an explicit deployment setting and verify it during readiness or release acceptance.

## Recommended remediation order

1. Require JWT expiry and close the non-development token-issuer path.
2. Stop forwarding unsanitized user input to external providers.
3. Add document revoke/delete/version semantics and atomic visibility for ingestion.
4. Move parsing and ingestion behind bounded workers with parser/resource limits.
5. Replace citation-only grounding with claim-level validation.
6. Add dependency locking, provider quotas/circuit breaking, and production index deletion protection.
7. Add HTTP/provider integration tests and make formatting status reproducible.
