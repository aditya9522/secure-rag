# Threat model

## Assets

- Customer/employee documents.
- Tenant boundaries and ACLs.
- OpenAI/Pinecone credentials.
- Generated answers and citations.
- Audit records.

## Adversaries

- Unauthenticated caller.
- Authenticated user attempting privilege escalation.
- Malicious tenant user.
- Attacker who can upload poisoned documents.
- Attacker attempting prompt injection or data exfiltration.

## Primary abuse cases

### Cross-tenant retrieval
Mitigated using a tenant-derived Pinecone namespace and a required tenant metadata filter.

### ACL bypass
Every query derives its Pinecone filter server-side from JWT claims; user-supplied filters are not trusted. Returned metadata is re-authorized in application code before prompt assembly in case the vector provider returns an unexpected record.

### Document prompt injection
Retrieved text is wrapped as untrusted evidence; it cannot override system policy. High-risk instruction phrases are flagged.

### Knowledge poisoning
Documents carry provenance and ownership metadata. Production deployments should add source approval workflows.

### Hallucinated answers
The service refuses when there is insufficient evidence and requires citations.

### Sensitive output
Output is scanned for common emails, phone numbers, SSNs, API keys, bearer tokens, and private keys.

Retrieved evidence is sanitized before it is sent to the model; output-only redaction is not treated as sufficient protection.

Grounded answers also require each substantive sentence to carry a citation and
share meaningful terms with the cited evidence. This deterministic check is a
fail-closed baseline, not a substitute for a future structured entailment
service.

### Abuse
Rate limiting, bounded request size, and bounded retrieval top-k reduce resource exhaustion.
