# Knowledge Intelligence Service Council Transcript

**Evaluation date:** 2026-05-05  
**BRD evaluated:** `docs/knowledge-intelligence-service-brd.md` draft v0.1  
**Method:** Five-advisor adversarial review with anonymized peer review and chairman synthesis.  
**Execution note:** The requested adversarial-idea-evaluator workflow was followed locally in this session. Sub-agents were not spawned because explicit sub-agent delegation was not requested in the user instruction available to this turn.

## Original Question

Prepare a separate BRD for a reusable Knowledge Intelligence Service using the existing features of the PS-WMS intelligence-service, validate it through adversarial evaluation, then update the BRD with recommendations.

## Framed Decision

Should the current PS-WMS intelligence-service capability be generalized into a standalone Knowledge Intelligence Service with domain-admin managed knowledge bases, graph, vector store, wiki, LLM provider governance, API-key maintenance, privacy controls, retrieval evaluation, and reusable APIs for compliant-parser and other future applications?

What is at stake:

- Avoiding duplicated RAG implementations across applications.
- Preserving proven PS-WMS features such as hybrid retrieval, graph, wiki, reasoning patterns, LLM router, prompt governance, evaluation sets, and PII redaction.
- Preventing a platform service from becoming overbroad, insecure, difficult to operate, or too slow to deliver.
- Ensuring domain administrators can self-serve without weakening platform governance.

## Advisor Analyses

### Advisor 1: The Proponent

The BRD is directionally strong because it recognizes the correct product boundary: this is not a compliant-parser feature, it is a platform service. The PS-WMS reference implementation already demonstrates the differentiated capability: document ingestion, chunks and embeddings, hybrid vector/graph/fact/wiki retrieval, reasoning patterns, prompt governance, provider routing, cost tracking, redaction, shadow mode, output fatigue, and golden-set evaluation. Generalizing those patterns into a reusable service avoids reimplementing RAG infrastructure for every domain.

The biggest advantage is governance. A domain-admin-maintained knowledge base with its own ontology, vector namespace, wiki, provider allowlist, and encrypted credentials gives each domain autonomy while preserving platform control. This is exactly the right compromise for regulated contexts: a police complaints domain needs legal sections, FIR drafting support, multilingual handling, and privacy controls; PS-WMS needs advisory facts, client preferences, SEBI style rules, NBA, and market reasoning. The same platform primitives can serve both if the ontology, prompts, providers, and policies are domain-scoped.

The BRD also has useful implementation specificity. It carries over PS-WMS concepts such as reasoning chains, graph node/edge upsert, wiki compilation, hybrid retrieval source fan-out, degraded context, and usage metrics. It defines enough data model and API surface for an AI builder to implement a first version.

The service should proceed, but with a productized platform path. Phase 1 must be intentionally narrow: domains, knowledge bases, source ingestion, chunks, vector search, audit, privacy, and a compliant-parser adapter. Graph, wiki, prompt governance, and full reasoning can follow once the core isolation and retrieval contracts are stable. The BRD should explicitly add platform-vs-domain responsibility boundaries and treat KIS as a control plane plus data plane service, not only a collection of endpoints.

### Advisor 2: The Contrarian

The fatal risk is that this becomes an overgrown internal platform before it proves its first reusable use case. The BRD includes domains, knowledge bases, source connectors, vector stores, graph, facts, wiki, prompts, LLM credentials, reasoning engines, feedback, shadow mode, A/B testing, audit, dashboards, and multiple provider integrations. That is product-platform scope, not a feature. If the team tries to build all of it at once, the result will likely be a complex service with broad abstractions, weak UX, and unclear adoption.

Security is another serious risk. The user explicitly proposed storing provider API keys in the database. The BRD correctly says encrypted or secret-manager references, but it should go further: plaintext should only exist in process memory during credential creation or provider invocation; tenant-specific key encryption should be supported; credential reads should be impossible by design; and key rotation should be tested. Domain admins can manage credentials, but security admins should control approval and revocation.

The privacy boundary also needs expansion. The BRD focuses on PII sent to LLM prompts. Embeddings are also model calls and can leak PII to external providers if raw chunks or queries are embedded. If an external embedding provider is used, KIS must either tokenize PII before embedding or require a domain policy that permits raw embedding with documented approval. Without this, the service might meet the literal LLM requirement while leaking sensitive content through embeddings.

The BRD also underestimates multi-tenant isolation. An `app_id` style filter is not enough for a reusable platform. The updated BRD should mandate defense-in-depth: domain_id on every row, query-layer checks, optional PostgreSQL row-level security, service principal scopes, regression tests that attempt cross-domain reads, and audit alerts for denied access. The recommendation is to proceed only if v1 is sharply reduced and isolation/privacy are treated as release blockers.

### Advisor 3: The First Principles Thinker

The underlying problem is not "build RAG." It is "make domain knowledge operationally trustworthy for applications." That means the central artifacts are not vectors or LLMs; they are source authority, provenance, policy, domain ownership, and measurable retrieval quality. The BRD is strong where it focuses on citations, review workflow, provider governance, and evaluation. It is weaker where it assumes every domain needs the same full graph/wiki/reasoning stack.

The first-principles design should separate four concerns. The knowledge control plane manages domains, permissions, source lifecycle, ontology, provider policy, prompts, credentials, evaluations, and audit. The knowledge data plane executes ingestion, indexing, graph updates, wiki compile, search, and reasoning. The retrieval contract returns evidence with confidence and provenance. The consuming application decides how to present or act on the result. This separation should be explicit in the BRD because it prevents KIS from swallowing domain applications.

The service should also treat "published knowledge snapshot" as a core concept. A consuming application needs predictable behavior. If a curator edits an ontology or source document, production retrieval should not unpredictably change mid-request. Knowledge bases should support draft and published snapshots across documents, chunks, embeddings, graph, wiki, prompts, and retrieval profile. Rollback should restore a previous snapshot. This is more important than adding many connector types in v1.

The BRD should include a domain bootstrap pattern: create a domain from a template, seed ontology, seed prompts, import sources, run evaluation, publish snapshot, then allow applications to bind to a stable version. This makes reusable adoption practical. Without templates and snapshots, every domain admin will be forced to understand too many low-level primitives before getting value.

### Advisor 4: The Outsider

From an outsider perspective, the idea is valuable but intimidating. The BRD uses many terms: graph, wiki, vector namespace, ontology, facts, reasoning patterns, provider governance, prompt templates, evaluation sets, shadow mode, feature providers, and output fatigue. It explains each one, but the user journey is still heavy. A domain admin should not have to make a dozen technical choices before seeing a working knowledge base.

The strongest missing piece is a guided setup experience. The BRD should describe domain templates and wizards. For example, a police complaints domain template should create BNS section ontology, legal source types, default retrieval profile, FIR/BNS reasoning pattern, strict privacy policy, and default evaluation questions. A wealth-management template should create client/advisor/security ontology, advisory wiki domains, suitability prompts, SEBI-style policy rules, and PS-WMS feature connectors. This would make the platform reusable for non-platform teams.

The second missing piece is clear accountability. If an answer is wrong, who fixes it? The service should route feedback to the right artifact: source document, chunk, fact, graph edge, wiki article, prompt template, retrieval profile, or model provider. The BRD mentions feedback, but it should define issue categories and remediation workflow more concretely.

The third missing piece is a simple first release. If the first UI includes everything, it will be overwhelming. The first admin path should be: create domain, choose template, upload documents, review extracted facts/wiki, run playground query, publish snapshot, create API key. Advanced graph and provider tuning should be behind expert settings. The idea should proceed, but only with a curated operator experience.

### Advisor 5: The Executor

The fastest practical path is not to start by writing a new service from scratch. Start by extracting the reusable contracts and test cases from PS-WMS. Keep the compliant-parser integration target small: BNS legal knowledge, FIR draft support, hybrid retrieval, citations, and privacy. Build the minimum independent KIS around that.

Monday morning tasks should be concrete. First, freeze this BRD v1 after adding evaluation recommendations. Second, create an architecture decision record that chooses whether the service lives in this repo, a new repo, or a shared services workspace. Third, define the v1 database schema with domain_id, knowledge_base_id, documents, chunks, vector namespace, facts, graph nodes/edges, wiki articles, provider config, credentials, prompt templates, retrieval logs, reasoning runs, and audit. Fourth, port the PS-WMS retrieval tests and add cross-domain isolation tests. Fifth, implement only the APIs needed for compliant-parser: ingest legal sources, hybrid search, execute BNS mapping pattern, fetch citations, and admin provider setup.

The BRD is implementable but too broad for a first development cycle. It should add "MVP v1" acceptance criteria that explicitly exclude A/B testing, many connector types, and full dashboarding until the core service is stable. It should also require idempotency keys for ingestion and reasoning requests. Retrying an upload, graph build, wiki compile, or reasoning call must not create duplicate documents, duplicate edges, or duplicate external LLM charges.

The final recommendation: proceed, but update the BRD with control-plane/data-plane separation, published snapshots, templates, embedding privacy, idempotency, and a narrower MVP.

## Anonymous Peer Review

### Anonymized Mapping

- Response A: Proponent
- Response B: Contrarian
- Response C: First Principles Thinker
- Response D: Outsider
- Response E: Executor

### Reviewer 1

Strongest response: Response C. It reframes the entire service around trustworthy operational knowledge rather than RAG mechanics. The published snapshot idea is critical because without versioned snapshots, downstream applications cannot rely on stable behavior.

Biggest blind spot: Response A. It advocates well for the platform but does not fully confront the build complexity and security risks.

What all responses missed: Data deletion and legal hold require more explicit treatment. Knowledge services often need both deletion rights and preservation holds. The BRD should include retention, legal hold, and reindex-after-delete behavior.

### Reviewer 2

Strongest response: Response B. It catches the most dangerous gap: embeddings can leak PII just like LLM prompts. This matters immediately because KIS will generate embeddings for documents and queries.

Biggest blind spot: Response D. It focuses on usability but does not deeply address regulated operations, secret management, or isolation.

What all responses missed: Provider evaluations should include latency, cost, privacy capability, data retention terms, and region availability before a provider is approved for a domain.

### Reviewer 3

Strongest response: Response E. It gives a practical execution path and names the APIs needed for the first consuming app. Without that, the BRD remains too large.

Biggest blind spot: Response C. Published snapshots are important, but the migration from PS-WMS to KIS also needs concrete adapter and data migration plans.

What all responses missed: Backward compatibility for PS-WMS should be defined. Existing PS-WMS endpoints should either stay stable behind adapters or be versioned and deprecated gradually.

### Reviewer 4

Strongest response: Response D. It identifies the adoption problem. A platform that only expert developers can use will not satisfy the user request that domain admins should maintain their own knowledge.

Biggest blind spot: Response B. It is correct on risks but could overconstrain the first release if every enterprise control is required before any value is delivered.

What all responses missed: Human review queues need SLA and ownership. If extracted facts or wiki drafts pile up, the knowledge base becomes stale even if ingestion technically works.

### Reviewer 5

Strongest response: Response B and Response C together. B finds the security and privacy traps; C fixes the architecture framing.

Biggest blind spot: Response E. It may bias too strongly toward compliant-parser and underdeliver the reusable service ambition.

What all responses missed: The BRD should define quality gates for graph and wiki, not only vector retrieval. Broken wiki links, orphan articles, low-confidence edges, and contradictory facts should block or warn on publication.

## Chairman Synthesis

### Where the Council Agrees

- Building KIS as a standalone service is the right product boundary.
- The PS-WMS intelligence-service contains valuable platform patterns worth preserving.
- The first release must be narrower than the full target architecture.
- Domain isolation, privacy, encrypted credential management, audit, and provider governance are release blockers.
- Hybrid retrieval should be measured against vector-only retrieval with gold sets.
- Domain admins need guided setup, templates, and operational dashboards rather than raw low-level primitives only.

### Where the Council Clashes

- Scope ambition: The Proponent supports the full platform direction; the Contrarian and Executor argue for a sharply reduced MVP. The synthesis favors the full platform as target state, but a limited v1 as implementation path.
- Control strictness: The Contrarian would make strict security controls mandatory early. The synthesis agrees for privacy, secrets, and isolation, but defers less critical features such as A/B testing and full dashboarding.
- Domain flexibility: First Principles favors stable snapshots and contracts; Outsider favors simpler templates. These are compatible and should both be added.

### Blind Spots Caught

- Embeddings are model-provider calls and may leak PII if raw chunks or queries are sent externally.
- Published knowledge snapshots and rollback are essential for stable consuming applications.
- Domain templates are needed to make admin self-service realistic.
- Idempotency is required for ingestion, graph builds, wiki compilation, and reasoning calls.
- Legal hold, deletion, and reindex-after-delete behavior need explicit requirements.
- PS-WMS backward compatibility and migration adapters need a formal plan.
- Graph and wiki need quality gates, not only retrieval evaluation.

### Risk Register

| Risk | Severity | Source | Mitigation |
|---|---|---|---|
| Platform scope too broad for v1 | High | Contrarian, Executor | Add MVP scope, defer advanced features, anchor first integration to compliant-parser. |
| PII leakage through embeddings | Critical | Contrarian, Peer Review | Extend privacy controls to embeddings and query embedding calls. |
| Weak multi-domain isolation | Critical | Contrarian | Require domain_id on all rows, query checks, optional RLS, and cross-domain negative tests. |
| Secrets exposed through database or logs | Critical | Contrarian | Use KMS or secret manager, never return plaintext, add rotation and audit controls. |
| Retrieval changes break consuming apps | High | First Principles | Add published knowledge snapshots and rollback. |
| Admin UI too technical | Medium | Outsider | Add domain templates, guided setup, and expert settings split. |
| Duplicate side effects on retry | Medium | Executor | Require idempotency keys for mutating APIs and external LLM-chargeable calls. |
| Stale review queues | Medium | Peer Review | Add review SLA, queue ownership, and stale-item notifications. |
| Poor graph/wiki quality | Medium | Peer Review | Add graph and wiki quality gates for contradiction, broken links, orphan articles, and low-confidence edges. |
| PS-WMS migration disruption | Medium | Peer Review | Add adapter compatibility, versioned deprecation, and migration verification. |

### Recommendation

Proceed with a standalone KIS BRD and implementation plan. Update the BRD before implementation to explicitly add:

1. Control-plane and data-plane separation.
2. Published knowledge snapshots and rollback.
3. Domain templates and guided setup.
4. PII controls for embeddings as well as LLM prompts.
5. Defense-in-depth domain isolation.
6. Idempotency for ingestion, indexing, wiki, graph, and reasoning APIs.
7. Quality gates for vector, graph, facts, wiki, and citations.
8. Legal hold, deletion, retention, and reindex-after-delete behavior.
9. Narrow MVP acceptance criteria anchored on compliant-parser.
10. PS-WMS backward-compatible migration adapters.

### The One Thing To Do First

Update the BRD with these recommendations and add a short "MVP v1 service boundary" section so implementation starts with a buildable, secure, reusable core instead of the full platform surface.
