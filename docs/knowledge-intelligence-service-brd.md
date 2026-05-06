# Knowledge Intelligence Service BRD

**Document Status:** Revised v0.2 after adversarial evaluation  
**Date:** 2026-05-05  
**Classification:** Confidential  
**Reference Implementation Reviewed:** `/Users/n15318/PS-WMS/services/intelligence-service`  
**Validation Report:** `doc/evaluations/knowledge-intelligence-service-council-report-20260505-004559.html`  

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Scope and Boundaries](#2-scope-and-boundaries)
3. [User Roles and Permissions](#3-user-roles-and-permissions)
4. [Data Model](#4-data-model)
5. [Functional Requirements](#5-functional-requirements)
6. [User Interface Requirements](#6-user-interface-requirements)
7. [API and Integration Requirements](#7-api-and-integration-requirements)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Workflow and State Diagrams](#9-workflow-and-state-diagrams)
10. [Notification and Communication Requirements](#10-notification-and-communication-requirements)
11. [Reporting and Analytics](#11-reporting-and-analytics)
12. [Migration and Launch Plan](#12-migration-and-launch-plan)
13. [Glossary](#13-glossary)
14. [Appendices](#14-appendices)

# 1. Executive Summary

## 1.1 Project Name

Knowledge Intelligence Service, abbreviated as KIS.

## 1.2 Project Description

KIS is a reusable, domain-governed knowledge and reasoning service that provides document ingestion, semantic chunking, vector search, graph construction, wiki compilation, hybrid retrieval, LLM reasoning, prompt governance, privacy controls, and admin maintenance for multiple business domains. The service will generalize the proven PS-WMS intelligence-service capabilities into a standalone platform component that can be used by the compliant-parser application, PS-WMS, and future knowledge/RAG use cases without duplicating retrieval infrastructure inside each application.

KIS is explicitly split into a control plane and a data plane. The control plane manages domains, permissions, templates, policies, credentials, prompts, ontology, quality gates, published snapshots, and audit. The data plane executes ingestion, indexing, graph updates, wiki compilation, retrieval, embedding generation, and reasoning runs. Consuming applications receive stable APIs and published knowledge snapshots; they do not import KIS internals or depend on draft knowledge changes.

## 1.3 Business Objectives

- Build one reusable knowledge intelligence platform instead of embedding separate RAG stacks in every application.
- Allow each permitted domain administrator to create and manage that domain's knowledge base, graph, wiki, vector namespace, ontology, LLM providers, and API credentials.
- Improve reasoning quality by combining vector similarity, graph traversal, extracted facts, curated wiki articles, and structured domain features.
- Enforce privacy and governance so PII and domain secrets are protected before LLM calls and all model usage is auditable.
- Provide measurable retrieval quality, citation traceability, and operational health so downstream applications can rely on KIS for regulated workflows.
- Provide stable published knowledge snapshots so production applications can bind to a known version and roll back safely.

## 1.4 Target Users and Pain Points

| User | Pain Point | KIS Response |
|---|---|---|
| Platform administrator | Multiple teams create inconsistent RAG stacks with weak governance. | Central service with tenant/domain controls, policies, and observability. |
| Domain administrator | Domain experts cannot maintain their own graph, wiki, ontology, vector store, or LLM provider settings. | Admin console and APIs for domain-scoped maintenance. |
| Knowledge curator | Uploaded source content is hard to approve, version, and cite. | Ingestion lifecycle with review, publishing, versioning, source citations, and rollback. |
| Application developer | Every app has to build its own retrieval, embedding, and prompt orchestration. | Stable query, ingestion, admin, and reasoning APIs. |
| Compliance or security officer | LLM calls can expose PII, secrets, or unapproved providers. | PII protection, encrypted credentials, policy checks, audit logs, and provider allowlists. |
| End user in a consuming app | Answers are incomplete, hallucinated, or unsupported by source documents. | Hybrid retrieval, evidence citations, confidence scoring, and answer provenance. |

## 1.5 Success Metrics

| KPI | Target |
|---|---|
| Retrieval answer citation coverage | At least 95 percent of production answers include source citations. |
| PII leakage to LLM providers | Zero confirmed high-risk PII leakage incidents. |
| Hybrid retrieval improvement | At least 20 percent higher gold-set recall than vector-only retrieval for evaluated domains. |
| Ingestion reliability | At least 99 percent of valid ingestion jobs complete or fail with actionable error details. |
| Query latency | P95 hybrid retrieval response under 2.5 seconds for top 10 results, excluding downstream LLM generation. |
| Admin self-service | Domain admins can create a knowledge base, upload sources, publish wiki articles, and configure permitted LLMs without developer intervention. |

# 2. Scope and Boundaries

## 2.1 In Scope

- Standalone FastAPI service with independent deployment, database schema, admin UI, and API key or OAuth based service authentication.
- Multi-domain administration with strict domain isolation.
- Knowledge base creation and lifecycle management.
- Source document upload, metadata capture, parsing, chunking, embedding, and processing status tracking.
- OCR-ready ingestion interface so calling applications can pass raw text, extracted text, or file references.
- Vector namespaces backed by pgvector or a pluggable vector provider.
- Domain ontology maintenance for graph node types, edge types, extraction rules, and allowed relationship semantics.
- Knowledge graph nodes, edges, extracted facts, temporal validity, confidence, and source provenance.
- Wiki compilation from source documents into curated articles with review workflow, wikilinks, tags, and source citations.
- Hybrid retrieval using vector search, graph traversal, extracted facts, wiki lookup, and optional structured feature providers.
- Reasoning patterns with rules, analytics, and LLM steps.
- LLM provider and model governance per domain, including encrypted API key storage.
- Prompt template registry, approval workflow, versioning, traffic split, and rollback.
- PII masking, tokenization, encryption, restoration, and leakage scanning for LLM-bound payloads.
- Cost budgets, token budgets, usage metering, provider fallback, model routing, and rate limits.
- Admin dashboards for ingestion health, graph health, wiki health, retrieval quality, LLM usage, audit events, and policy violations.
- API endpoints for consuming applications such as compliant-parser to query knowledge, request reasoning, and retrieve citations.
- Test coverage for data isolation, retrieval quality, provider governance, privacy controls, and lifecycle transitions.
- Published knowledge snapshots that package source versions, chunks, vector index version, graph version, wiki version, prompt versions, ontology version, retrieval profile, and policy versions.
- Domain templates and guided setup for common domains such as police complaint intelligence and PS-WMS advisory intelligence.
- Privacy controls for external embedding calls as well as LLM prompt and completion calls.
- Idempotency keys for mutating ingestion, indexing, graph, wiki, and reasoning APIs.
- Retention, legal hold, delete, and reindex-after-delete workflows.
- PS-WMS compatibility adapter and gradual migration plan.

## 2.2 Out of Scope

- Replacing Google Document AI or other OCR engines inside consuming applications.
- Building a general-purpose document management system unrelated to knowledge retrieval.
- Human case workflow management for police complaints, PS-WMS portfolios, or other domain-specific transactions.
- Training proprietary foundation models.
- Storing plaintext external API keys.
- Allowing cross-domain knowledge access without an explicit sharing policy.
- Real-time collaborative wiki editing in v1.
- Public anonymous access to query APIs.
- Full A/B testing, output fatigue routing, and advanced delivery-channel orchestration in MVP v1; these remain target-state features after the core service is stable.

## 2.3 Assumptions

- PostgreSQL with pgvector is available for v1 unless a deployment explicitly selects another vector provider.
- Redis or a compatible queue/stream is available for asynchronous ingestion events and job progress.
- Existing compliant-parser LLM privacy rules can be reused or adapted for KIS.
- Domain administrators are internal trusted users, but their permissions remain scoped to assigned domains.
- LLM providers include OpenAI, Google Gemini, Anthropic, and self-hosted OpenAI-compatible endpoints.
- Consuming applications will call KIS through internal service credentials, not browser-exposed secrets.

## 2.4 Constraints

- All high-risk PII must be masked before outbound LLM calls.
- API credentials must be encrypted using KMS, envelope encryption, or an approved secret manager reference.
- All stored prompts, retrieval results, and LLM outputs must be traceable to domain, knowledge base, user or service principal, and request ID.
- Retrieval responses must preserve citations to original source documents, chunks, wiki articles, graph facts, or structured feature sources.
- Domain isolation must be enforced at the database query layer and API layer.
- KIS must support a low-complexity v1 path for compliant-parser while preserving a reusable platform architecture.
- External embedding providers are treated as model providers for privacy purposes. Domain policy must either mask PII before embedding calls or explicitly approve raw embedding for a trusted private provider.
- Production releases must include cross-domain negative tests and optional PostgreSQL row-level security for defense-in-depth isolation.
- Retrying a mutating request must not duplicate documents, chunks, graph edges, wiki articles, reasoning runs, or external provider charges.

## 2.5 MVP v1 Service Boundary

MVP v1 must deliver a secure reusable core for compliant-parser while preserving the target architecture for PS-WMS and future domains.

In MVP v1:

- Platform admin can create domains and assign domain admins.
- Domain admin can create a knowledge base from a template or from a blank configuration.
- Domain admin or curator can ingest text or file-derived text, chunk, embed, and publish sources.
- KIS supports vector search and hybrid retrieval using vector, facts, graph, and wiki when configured.
- KIS supports BNS legal knowledge for compliant-parser with citations and a BNS mapping reasoning pattern.
- KIS supports encrypted provider credentials, model allowlists, prompt templates, PII masking, embedding privacy policy, usage logging, and audit events.
- KIS supports published snapshots and rollback.
- KIS exposes stable APIs for compliant-parser: ingest source, hybrid search, execute BNS mapping, fetch citations, and provider administration.

Deferred from MVP v1:

- Multiple external connector types beyond manual upload, object URI, and API ingestion.
- Full A/B testing UI.
- Complex output fatigue routing.
- Real-time collaborative wiki editing.
- Non-critical dashboards that are not needed for security, ingestion, query health, and retrieval quality.

# 3. User Roles and Permissions

## 3.1 Roles

| Role | Description |
|---|---|
| Platform Administrator | Manages global service configuration, domains, provider registry, audit policy, and platform health. |
| Security Administrator | Reviews privacy rules, credential storage, provider access, audit logs, and policy violations. |
| Domain Administrator | Manages one or more permitted domains, knowledge bases, sources, wiki articles, graph schema, and LLM provider allowlists. |
| Knowledge Curator | Uploads and reviews domain documents, extracted facts, graph updates, and wiki drafts. |
| Domain Reviewer | Approves publication of sources, facts, wiki articles, prompts, reasoning patterns, and ontology changes. |
| Application Developer | Creates service integrations, API keys, query clients, and callback subscriptions for permitted applications. |
| Consuming Application | Machine principal that submits ingestion, retrieval, or reasoning requests for permitted domains. |
| Auditor | Read-only access to audit events, provider usage, privacy events, and change history. |

## 3.2 Permissions Matrix

| Capability | Platform Admin | Security Admin | Domain Admin | Curator | Reviewer | Developer | Consuming App | Auditor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Create domain | Yes | No | No | No | No | No | No | No |
| Manage assigned domain settings | Yes | View | Yes | No | View | No | No | View |
| Manage platform provider catalog | Yes | Approve | No | No | No | No | No | View |
| Configure domain LLM provider | Yes | Approve | Yes | No | Review | No | No | View |
| View decrypted API keys | No | No | No | No | No | No | No | No |
| Rotate or revoke encrypted credentials | Yes | Yes | Yes, assigned domain | No | No | No | No | View event only |
| Create knowledge base | Yes | No | Yes | No | No | No | No | View |
| Upload source documents | Yes | No | Yes | Yes | No | API only | API only | View metadata |
| Approve source publication | Yes | No | Yes | No | Yes | No | No | View |
| Edit ontology | Yes | No | Yes | Propose | Approve | No | No | View |
| Publish wiki articles | Yes | No | Yes | Propose | Approve | No | No | View |
| Run retrieval query | Yes | No | Yes | Yes | Yes | Yes | Yes | View logs only |
| Execute reasoning pattern | Yes | No | Yes | Yes, if permitted | Yes | Yes | Yes | View logs only |
| Manage prompt templates | Yes | Review | Yes | Propose | Approve | No | No | View |
| Manage application API keys | Yes | Review | Yes, domain-scoped | No | No | Yes, own app | No | View event only |
| Delete domain data | Yes | Approve | Request | No | Approve | No | No | View event only |

# 4. Data Model

## 4.1 Common Field Rules

All persisted entities must include `id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `status`, and `is_deleted` unless explicitly marked as event-only. IDs are UUID strings. Timestamps are UTC ISO 8601. Soft-deleted records remain hidden from default reads and remain auditable.

## 4.2 Entity: Domain

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| code | string | Yes | 3 to 50 lowercase letters, numbers, hyphen | None |
| name | string | Yes | 3 to 120 characters | None |
| description | text | No | Max 2000 characters | Empty |
| data_residency | string | Yes | `in`, `us`, `eu`, `global` | `in` |
| pii_policy | json | Yes | Contains masking, retention, logging flags | Strict policy |
| status | string | Yes | `draft`, `active`, `suspended`, `archived` | `draft` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: Domain has many DomainMemberships, KnowledgeBases, LLMProviderConfigs, PolicyRules, AuditEvents.

Sample data:

| code | name | data_residency | status |
|---|---|---|---|
| `police-iqw` | Police Complaint Intelligence | `in` | `active` |
| `ps-wms` | Portfolio Services WMS | `in` | `active` |

## 4.3 Entity: User

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| email | string | Yes | Valid email, unique | None |
| display_name | string | Yes | 2 to 120 characters | None |
| auth_provider | string | Yes | `local`, `oidc`, `saml` | `oidc` |
| external_subject | string | No | Unique per provider | Null |
| platform_role | string | Yes | `platform_admin`, `security_admin`, `user`, `auditor` | `user` |
| status | string | Yes | `active`, `disabled`, `invited` | `invited` |
| last_login_at | datetime | No | UTC | Null |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | No | User ID | Null |
| updated_by | UUID | No | User ID | Null |
| is_deleted | boolean | Yes | True or false | false |

Relationships: User has many DomainMemberships, AuditEvents, approvals, API key ownership records.

Sample data:

| email | display_name | platform_role | status |
|---|---|---|---|
| `admin@example.gov` | `Platform Admin` | `platform_admin` | `active` |
| `curator@example.gov` | `Domain Curator` | `user` | `active` |

## 4.4 Entity: DomainMembership

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| user_id | UUID | Yes | FK User | None |
| role | string | Yes | `domain_admin`, `curator`, `reviewer`, `developer`, `auditor` | None |
| scopes | string array | Yes | Non-empty permissions list | Empty array |
| status | string | Yes | `active`, `suspended`, `expired` | `active` |
| expires_at | datetime | No | UTC | Null |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: DomainMembership belongs to Domain and User.

Sample data:

| domain_id | user_id | role | scopes |
|---|---|---|---|
| `police-iqw` | `curator-user` | `curator` | `["source:write","wiki:propose"]` |
| `ps-wms` | `reviewer-user` | `reviewer` | `["source:approve","prompt:approve"]` |

## 4.5 Entity: KnowledgeBase

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| code | string | Yes | Unique in domain | None |
| name | string | Yes | 3 to 160 characters | None |
| description | text | No | Max 3000 characters | Empty |
| default_language | string | Yes | ISO 639 code | `en` |
| supported_languages | string array | Yes | At least one language | `["en"]` |
| retrieval_profile | json | Yes | Vector, graph, fact, wiki weights | Default hybrid |
| status | string | Yes | `draft`, `active`, `suspended`, `archived` | `draft` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: KnowledgeBase has many SourceDocuments, VectorNamespaces, Ontologies, WikiArticles, ReasoningPatterns.

Sample data:

| code | name | supported_languages | status |
|---|---|---|---|
| `bns-legal` | `BNS Legal Knowledge` | `["en","hi","te"]` | `active` |
| `wms-advisory` | `WMS Advisory Knowledge` | `["en"]` | `active` |

## 4.6 Entity: SourceConnector

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| connector_type | string | Yes | `upload`, `gcs`, `s3`, `database`, `api`, `git`, `manual` | `upload` |
| name | string | Yes | 3 to 120 characters | None |
| config | json | Yes | No plaintext secrets | Empty object |
| credential_ref | string | No | Secret reference or encrypted credential ID | Null |
| sync_schedule | string | No | Cron expression | Null |
| status | string | Yes | `draft`, `active`, `paused`, `failed` | `draft` |
| last_sync_at | datetime | No | UTC | Null |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: SourceConnector has many SourceDocuments and IngestionJobs.

Sample data:

| connector_type | name | status | sync_schedule |
|---|---|---|---|
| `upload` | `Manual BNS Uploads` | `active` | Null |
| `git` | `WMS Knowledge Repository` | `active` | `0 */6 * * *` |

## 4.7 Entity: SourceDocument

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| source_connector_id | UUID | No | FK SourceConnector | Null |
| source_type | string | Yes | Domain-defined type | None |
| title | string | Yes | 1 to 250 characters | None |
| source_uri | string | No | URI or storage path | Null |
| raw_text | text | No | Stored if policy allows | Null |
| content_hash | string | Yes | SHA-256 hex | None |
| language | string | Yes | ISO 639 code | `en` |
| metadata | json | Yes | Flexible metadata | Empty object |
| classification | string | Yes | `public`, `internal`, `confidential`, `restricted` | `internal` |
| processing_status | string | Yes | `pending`, `processing`, `review_required`, `published`, `failed`, `archived` | `pending` |
| error_message | text | No | Max 4000 characters | Null |
| published_version | integer | Yes | Non-negative | 0 |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User or service ID | Caller |
| updated_by | UUID | Yes | User or service ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: SourceDocument has many DocumentChunks, ExtractedFacts, WikiArticles, GraphEdges, IngestionJobs.

Sample data:

| title | source_type | language | processing_status |
|---|---|---|---|
| `BNS Section Reference v1` | `legal_reference` | `en` | `published` |
| `Client Meeting Transcript 2026-04-18` | `call_transcript` | `en` | `published` |

## 4.8 Entity: DocumentChunk

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| source_document_id | UUID | Yes | FK SourceDocument | None |
| chunk_index | integer | Yes | Zero-based | None |
| chunk_text | text | Yes | Non-empty | None |
| normalized_text | text | No | Search-normalized | Null |
| token_count | integer | Yes | Greater than 0 | None |
| embedding | vector | No | Dimension matches namespace | Null |
| embedding_model | string | No | Provider model ID | Null |
| entities | json | Yes | Extracted entities | Empty array |
| topics | string array | Yes | Domain topic tags | Empty array |
| sentiment | float | No | -1.0 to 1.0 | Null |
| confidence | float | Yes | 0.0 to 1.0 | 0.0 |
| citation_ref | string | Yes | Stable source citation | Generated |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User or service ID | Caller |
| updated_by | UUID | Yes | User or service ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: DocumentChunk belongs to SourceDocument and has many RetrievalResults and ExtractedFacts.

Sample data:

| chunk_index | token_count | topics | confidence |
|---:|---:|---|---:|
| 0 | 488 | `["bns","theft"]` | 0.92 |
| 1 | 462 | `["client_preference","risk"]` | 0.86 |

## 4.9 Entity: VectorNamespace

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| name | string | Yes | Unique in knowledge base | None |
| provider | string | Yes | `pgvector`, `pinecone`, `weaviate`, `milvus` | `pgvector` |
| embedding_model | string | Yes | Model ID | None |
| dimensions | integer | Yes | Greater than 0 | 1536 |
| distance_metric | string | Yes | `cosine`, `l2`, `dot` | `cosine` |
| index_status | string | Yes | `empty`, `building`, `ready`, `stale`, `failed` | `empty` |
| last_indexed_at | datetime | No | UTC | Null |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: VectorNamespace belongs to KnowledgeBase and indexes DocumentChunks.

Sample data:

| name | provider | embedding_model | index_status |
|---|---|---|---|
| `police_bns_pgvector` | `pgvector` | `text-embedding-3-small` | `ready` |
| `wms_advisory_pgvector` | `pgvector` | `text-embedding-3-small` | `ready` |

## 4.10 Entity: OntologyType

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| kind | string | Yes | `node`, `edge`, `fact` | None |
| code | string | Yes | Unique per knowledge base and kind | None |
| label | string | Yes | 2 to 120 characters | None |
| schema | json | Yes | JSON schema for properties | Empty object |
| extraction_hints | json | Yes | Prompt/rule hints | Empty object |
| status | string | Yes | `draft`, `active`, `deprecated` | `draft` |
| version | integer | Yes | Greater than 0 | 1 |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: OntologyType constrains GraphNode, GraphEdge, and ExtractedFact records.

Sample data:

| kind | code | label | status |
|---|---|---|---|
| `node` | `bns_section` | `BNS Section` | `active` |
| `edge` | `maps_to_offence` | `Maps to Offence` | `active` |

## 4.11 Entity: GraphNode

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| node_type | string | Yes | Active node OntologyType code | None |
| external_id | string | Yes | Canonical domain ID | None |
| label | string | Yes | 1 to 250 characters | None |
| properties | json | Yes | Must match ontology schema | Empty object |
| confidence | float | Yes | 0.0 to 1.0 | 1.0 |
| source_document_id | UUID | No | FK SourceDocument | Null |
| status | string | Yes | `active`, `superseded`, `archived` | `active` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User or service ID | Caller |
| updated_by | UUID | Yes | User or service ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: GraphNode has many outgoing and incoming GraphEdges.

Sample data:

| node_type | external_id | label | confidence |
|---|---|---|---:|
| `bns_section` | `bns:303` | `BNS 303 Theft` | 0.99 |
| `preference` | `preference:exclusion:tobacco` | `Exclusion: Tobacco` | 0.87 |

## 4.12 Entity: GraphEdge

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| source_node_id | UUID | Yes | FK GraphNode | None |
| target_node_id | UUID | Yes | FK GraphNode | None |
| edge_type | string | Yes | Active edge OntologyType code | None |
| properties | json | Yes | Must match ontology schema | Empty object |
| confidence | float | Yes | 0.0 to 1.0 | 1.0 |
| source_document_id | UUID | No | FK SourceDocument | Null |
| valid_from | datetime | No | UTC | Null |
| valid_until | datetime | No | UTC, later than valid_from | Null |
| status | string | Yes | `active`, `superseded`, `archived` | `active` |
| superseded_by | UUID | No | FK GraphEdge | Null |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User or service ID | Caller |
| updated_by | UUID | Yes | User or service ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: GraphEdge belongs to source and target GraphNodes.

Sample data:

| edge_type | source | target | confidence |
|---|---|---|---:|
| `maps_to_offence` | `offence:theft` | `bns:303` | 0.93 |
| `has_preference` | `client:42` | `preference:exclusion:tobacco` | 0.88 |

## 4.13 Entity: ExtractedFact

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| fact_type | string | Yes | Active fact OntologyType code | None |
| subject_type | string | Yes | Domain entity type | None |
| subject_id | string | Yes | Domain entity ID | None |
| claim | text | Yes | Non-empty | None |
| structured_claim | json | Yes | Must match fact schema | Empty object |
| confidence | float | Yes | 0.0 to 1.0 | 0.5 |
| source_document_id | UUID | No | FK SourceDocument | Null |
| source_chunk_id | UUID | No | FK DocumentChunk | Null |
| confirmed_count | integer | Yes | Non-negative | 0 |
| contradicted_by | UUID | No | FK ExtractedFact | Null |
| expires_at | datetime | No | UTC | Null |
| status | string | Yes | `candidate`, `verified`, `rejected`, `expired` | `candidate` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User or service ID | Caller |
| updated_by | UUID | Yes | User or service ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: ExtractedFact may produce GraphNodes and GraphEdges.

Sample data:

| fact_type | subject_type | claim | confidence |
|---|---|---|---:|
| `legal_mapping` | `offence` | `Theft complaints may map to BNS 303 when movable property is dishonestly taken.` | 0.91 |
| `preference` | `client` | `Client avoids tobacco sector exposure.` | 0.86 |

## 4.14 Entity: WikiArticle

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| slug | string | Yes | Unique in knowledge base | None |
| title | string | Yes | 3 to 180 characters | None |
| domain_area | string | Yes | Domain category | `general` |
| content_markdown | text | Yes | Non-empty | None |
| source_document_ids | UUID array | Yes | At least one source for generated articles | Empty array |
| tags | string array | Yes | Tag list | Empty array |
| concepts | string array | Yes | Concept list | Empty array |
| wikilinks | json | Yes | Resolved and broken links | Empty object |
| review_status | string | Yes | `draft`, `in_review`, `approved`, `published`, `rejected`, `archived` | `draft` |
| version | integer | Yes | Greater than 0 | 1 |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User or service ID | Caller |
| updated_by | UUID | Yes | User or service ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: WikiArticle belongs to KnowledgeBase and cites SourceDocuments.

Sample data:

| slug | title | domain_area | review_status |
|---|---|---|---|
| `bns_303_theft` | `BNS 303 Theft` | `legal` | `published` |
| `suitability_review` | `Suitability Review` | `advisory` | `published` |

## 4.15 Entity: LLMProviderConfig

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| provider | string | Yes | `openai`, `gemini`, `anthropic`, `azure_openai`, `self_hosted` | None |
| display_name | string | Yes | 3 to 120 characters | None |
| base_url | string | No | HTTPS URL for API-compatible provider | Null |
| allowed_models | string array | Yes | Non-empty | Empty array |
| default_model | string | Yes | Must be in allowed_models | None |
| embedding_models | string array | Yes | Empty if unsupported | Empty array |
| credential_id | UUID | No | FK LLMCredential | Null |
| max_tokens_per_request | integer | Yes | Positive | 32000 |
| monthly_budget_cents | integer | Yes | Non-negative | 0 |
| fallback_provider_id | UUID | No | FK LLMProviderConfig | Null |
| status | string | Yes | `draft`, `pending_security_review`, `active`, `suspended`, `revoked` | `draft` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: LLMProviderConfig belongs to Domain and has many LLMUsageEvents.

Sample data:

| provider | display_name | default_model | status |
|---|---|---|---|
| `openai` | `OpenAI Police Domain` | `gpt-4o-mini` | `active` |
| `self_hosted` | `Internal vLLM Endpoint` | `llama-3.1-70b` | `pending_security_review` |

## 4.16 Entity: LLMCredential

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| secret_name | string | Yes | Unique in domain | None |
| encrypted_secret | text | No | Ciphertext only | Null |
| secret_manager_ref | string | No | Secret manager URI | Null |
| encryption_key_ref | string | Yes | KMS or envelope key reference | None |
| last_rotated_at | datetime | No | UTC | Null |
| expires_at | datetime | No | UTC | Null |
| status | string | Yes | `active`, `rotation_due`, `revoked`, `expired` | `active` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: LLMCredential may be referenced by LLMProviderConfig. Plaintext secret is never returned by API.

Sample data:

| secret_name | secret_manager_ref | status | expires_at |
|---|---|---|---|
| `openai-police-prod` | `gcp-secret://kis/openai-police-prod` | `active` | `2026-08-01T00:00:00Z` |
| `gemini-wms-prod` | `gcp-secret://kis/gemini-wms-prod` | `rotation_due` | `2026-05-31T00:00:00Z` |

## 4.17 Entity: PromptTemplate

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | No | FK KnowledgeBase | Null |
| template_key | string | Yes | Unique per domain and version | None |
| version | integer | Yes | Greater than 0 | 1 |
| task_type | string | Yes | `extraction`, `reasoning`, `summarization`, `reranking`, `answering` | None |
| system_prompt | text | Yes | Non-empty | None |
| user_prompt_template | text | Yes | Non-empty | None |
| output_schema | json | Yes | JSON schema | Empty object |
| privacy_policy | json | Yes | PII and logging controls | Strict policy |
| review_status | string | Yes | `draft`, `in_review`, `approved`, `active`, `retired` | `draft` |
| approved_by | UUID | No | User ID | Null |
| approved_at | datetime | No | UTC | Null |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: PromptTemplate is used by ReasoningPattern and LLMUsageEvent.

Sample data:

| template_key | task_type | version | review_status |
|---|---|---:|---|
| `bns_section_mapper` | `reasoning` | 1 | `active` |
| `wiki_concept_extractor` | `extraction` | 1 | `approved` |

## 4.18 Entity: ReasoningPattern

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | No | FK KnowledgeBase | Null |
| pattern_key | string | Yes | Unique per domain and version | None |
| version | integer | Yes | Greater than 0 | 1 |
| name | string | Yes | 3 to 160 characters | None |
| context_config | json | Yes | Sources, top_k, budgets | Empty object |
| engine_chain | string array | Yes | Values from `rules`, `analytics`, `llm` | Empty array |
| output_config | json | Yes | Delivery and schema | Empty object |
| traffic_pct | integer | Yes | 0 to 100 | 0 |
| cost_budget_cents | integer | Yes | Non-negative | 0 |
| review_status | string | Yes | `draft`, `approved`, `active`, `retired` | `draft` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: ReasoningPattern has many ReasoningRuns.

Sample data:

| pattern_key | name | engine_chain | review_status |
|---|---|---|---|
| `fir_bns_mapping` | `FIR BNS Section Mapping` | `["rules","llm"]` | `active` |
| `advisor_next_best_action` | `Advisor Next Best Action` | `["rules","analytics","llm"]` | `active` |

## 4.19 Entity: RetrievalQuery

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| request_id | string | Yes | Unique request ID | Generated |
| principal_type | string | Yes | `user`, `service` | None |
| principal_id | string | Yes | Caller identifier | None |
| query_text_hash | string | Yes | SHA-256 of query text | None |
| query_text_redacted | text | Yes | PII-masked query | None |
| retrieval_mode | string | Yes | `vector`, `hybrid`, `graph`, `wiki`, `facts` | `hybrid` |
| filters | json | Yes | Domain filters | Empty object |
| result_count | integer | Yes | Non-negative | 0 |
| latency_ms | integer | Yes | Non-negative | 0 |
| status | string | Yes | `succeeded`, `failed`, `blocked` | None |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | No | User ID | Null |
| updated_by | UUID | No | User ID | Null |
| is_deleted | boolean | Yes | True or false | false |

Relationships: RetrievalQuery has many RetrievalResults.

Sample data:

| retrieval_mode | result_count | status | latency_ms |
|---|---:|---|---:|
| `hybrid` | 10 | `succeeded` | 842 |
| `vector` | 6 | `succeeded` | 214 |

## 4.20 Entity: RetrievalResult

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| retrieval_query_id | UUID | Yes | FK RetrievalQuery | None |
| source_kind | string | Yes | `vector`, `graph`, `fact`, `wiki`, `feature` | None |
| source_id | UUID/string | Yes | Source record ID | None |
| content_snippet | text | Yes | PII-masked if logged | None |
| relevance_score | float | Yes | 0.0 to 1.0 | 0.0 |
| rank | integer | Yes | 1-based | None |
| citation | json | Yes | Source citation payload | Empty object |
| metadata | json | Yes | Source metadata | Empty object |
| created_at | datetime | Yes | UTC | Now |

Relationships: RetrievalResult belongs to RetrievalQuery and references one source record.

Sample data:

| source_kind | rank | relevance_score | citation |
|---|---:|---:|---|
| `wiki` | 1 | 0.94 | `{"title":"BNS 303 Theft","slug":"bns_303_theft"}` |
| `graph` | 2 | 0.89 | `{"edge_type":"maps_to_offence"}` |

## 4.21 Entity: IngestionJob

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| source_document_id | UUID | No | FK SourceDocument | Null |
| source_connector_id | UUID | No | FK SourceConnector | Null |
| job_type | string | Yes | `parse`, `chunk`, `embed`, `extract_facts`, `build_graph`, `compile_wiki`, `reindex` | None |
| status | string | Yes | `queued`, `running`, `review_required`, `completed`, `failed`, `cancelled` | `queued` |
| progress_pct | integer | Yes | 0 to 100 | 0 |
| counts | json | Yes | Processed counts | Empty object |
| error_code | string | No | Stable error code | Null |
| error_message | text | No | Max 4000 characters | Null |
| started_at | datetime | No | UTC | Null |
| completed_at | datetime | No | UTC | Null |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User or service ID | Caller |
| updated_by | UUID | Yes | User or service ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: IngestionJob belongs to KnowledgeBase and optionally a SourceDocument.

Sample data:

| job_type | status | progress_pct | counts |
|---|---|---:|---|
| `embed` | `completed` | 100 | `{"chunks":128}` |
| `compile_wiki` | `review_required` | 100 | `{"draft_articles":9}` |

## 4.22 Entity: ReasoningRun

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | No | FK KnowledgeBase | Null |
| reasoning_pattern_id | UUID | Yes | FK ReasoningPattern | None |
| request_id | string | Yes | Unique request ID | Generated |
| entity_type | string | No | Domain entity type | Null |
| entity_id | string | No | Domain entity ID | Null |
| trigger_type | string | Yes | `api`, `schedule`, `event`, `manual` | `api` |
| context_snapshot | json | Yes | PII-redacted context only | Empty object |
| result | json | Yes | Final response | Empty object |
| confidence | float | No | 0.0 to 1.0 | Null |
| severity | string | No | Domain severity | Null |
| pii_fields_redacted | json | Yes | Types and token counts only | Empty object |
| llm_usage | json | Yes | Tokens, cost, model | Empty object |
| status | string | Yes | `queued`, `context_assembly`, `reasoning`, `completed`, `failed`, `blocked`, `cost_exceeded` | `queued` |
| duration_ms | integer | Yes | Non-negative | 0 |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | No | User or service ID | Null |
| updated_by | UUID | No | User or service ID | Null |
| is_deleted | boolean | Yes | True or false | false |

Relationships: ReasoningRun belongs to ReasoningPattern and may reference RetrievalQueries.

Sample data:

| trigger_type | status | confidence | duration_ms |
|---|---|---:|---:|
| `api` | `completed` | 0.91 | 1760 |
| `schedule` | `cost_exceeded` | Null | 320 |

## 4.23 Entity: PolicyRule

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| rule_name | string | Yes | 3 to 160 characters | None |
| rule_type | string | Yes | `privacy`, `provider`, `retrieval`, `retention`, `approval`, `cost` | None |
| condition | json | Yes | Machine-evaluable condition | Empty object |
| action | string | Yes | `allow`, `block`, `redact`, `review`, `notify` | None |
| severity | string | Yes | `low`, `medium`, `high`, `critical` | `medium` |
| effective_from | datetime | Yes | UTC | Now |
| effective_until | datetime | No | UTC | Null |
| review_status | string | Yes | `draft`, `approved`, `active`, `retired` | `draft` |
| status | string | Yes | `active`, `inactive` | `inactive` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: PolicyRule belongs to Domain and produces PolicyViolation events.

Sample data:

| rule_type | rule_name | action | severity |
|---|---|---|---|
| `privacy` | `Block high risk PII to LLM` | `block` | `critical` |
| `cost` | `Monthly OpenAI Budget` | `review` | `medium` |

## 4.24 Entity: AuditEvent

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | No | FK Domain | Null for platform event |
| actor_type | string | Yes | `user`, `service`, `system` | None |
| actor_id | string | Yes | Actor identifier | None |
| action | string | Yes | Stable action code | None |
| target_type | string | Yes | Entity name | None |
| target_id | string | No | Entity ID | Null |
| request_id | string | No | Request correlation ID | Null |
| ip_address | string | No | IP address | Null |
| user_agent | string | No | User agent | Null |
| metadata | json | Yes | Redacted metadata | Empty object |
| created_at | datetime | Yes | UTC | Now |

Relationships: AuditEvent references any auditable target.

Sample data:

| actor_type | action | target_type | metadata |
|---|---|---|---|
| `user` | `wiki.article.approved` | `WikiArticle` | `{"slug":"bns_303_theft"}` |
| `service` | `llm.prompt.blocked_pii` | `ReasoningRun` | `{"pii_types":["AADHAAR","PHONE"]}` |

## 4.25 Entity: DomainTemplate

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| template_key | string | Yes | Unique platform key | None |
| name | string | Yes | 3 to 160 characters | None |
| description | text | No | Max 3000 characters | Empty |
| default_domain_policy | json | Yes | Privacy, retention, provider, audit defaults | Strict defaults |
| ontology_seed | json | Yes | Node, edge, and fact definitions | Empty object |
| prompt_seed | json | Yes | Prompt template definitions | Empty object |
| retrieval_profile_seed | json | Yes | Default retrieval weights | Hybrid defaults |
| evaluation_seed | json | Yes | Smoke-test queries | Empty array |
| status | string | Yes | `draft`, `active`, `retired` | `draft` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: DomainTemplate can create Domains, KnowledgeBases, OntologyTypes, PromptTemplates, PolicyRules, and EvaluationSets.

Sample data:

| template_key | name | status | retrieval_profile_seed |
|---|---|---|---|
| `police_iqw_bns` | `Police IQW BNS Knowledge` | `active` | `{"vector":0.45,"graph":0.2,"facts":0.2,"wiki":0.15}` |
| `ps_wms_advisory` | `PS-WMS Advisory Intelligence` | `active` | `{"vector":0.4,"graph":0.25,"facts":0.2,"wiki":0.15}` |

## 4.26 Entity: KnowledgeSnapshot

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| snapshot_version | integer | Yes | Monotonic per knowledge base | Next version |
| label | string | Yes | 3 to 160 characters | None |
| source_document_versions | json | Yes | Source IDs and versions | Empty object |
| vector_namespace_version | string | Yes | Index version or build ID | None |
| ontology_versions | json | Yes | Ontology type versions | Empty object |
| graph_version | string | Yes | Graph build ID | None |
| wiki_versions | json | Yes | Article slugs and versions | Empty object |
| prompt_versions | json | Yes | Prompt keys and versions | Empty object |
| retrieval_profile | json | Yes | Effective retrieval config | Empty object |
| quality_gate_result | json | Yes | Evaluation and gate summary | Empty object |
| status | string | Yes | `draft`, `published`, `rolled_back`, `retired` | `draft` |
| published_at | datetime | No | UTC | Null |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: KnowledgeSnapshot belongs to KnowledgeBase and is referenced by RetrievalQuery and ReasoningRun.

Sample data:

| snapshot_version | label | status | quality_gate_result |
|---:|---|---|---|
| 3 | `BNS legal baseline May 2026` | `published` | `{"recall":0.91,"citation_coverage":1.0}` |
| 7 | `WMS advisory policy refresh` | `published` | `{"recall":0.88,"broken_links":0}` |

## 4.27 Entity: EvaluationSet

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| name | string | Yes | 3 to 160 characters | None |
| purpose | string | Yes | `smoke`, `release_gate`, `regression`, `benchmark` | `smoke` |
| cases | json | Yes | Query, expected sources, expected traits | Empty array |
| min_recall | float | Yes | 0.0 to 1.0 | 0.8 |
| min_citation_coverage | float | Yes | 0.0 to 1.0 | 0.95 |
| status | string | Yes | `draft`, `active`, `retired` | `draft` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: EvaluationSet has many EvaluationRuns.

Sample data:

| name | purpose | min_recall | status |
|---|---|---:|---|
| `BNS smoke queries` | `release_gate` | 0.85 | `active` |
| `WMS NBA golden set` | `regression` | 0.8 | `active` |

## 4.28 Entity: EvaluationRun

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| evaluation_set_id | UUID | Yes | FK EvaluationSet | None |
| knowledge_snapshot_id | UUID | No | FK KnowledgeSnapshot | Null |
| retrieval_mode | string | Yes | `vector`, `hybrid`, `graph`, `wiki`, `facts` | `hybrid` |
| metrics | json | Yes | Recall, precision, MRR, latency, citations | Empty object |
| failed_cases | json | Yes | Case IDs and reasons | Empty array |
| status | string | Yes | `running`, `passed`, `failed`, `cancelled` | `running` |
| started_at | datetime | Yes | UTC | Now |
| completed_at | datetime | No | UTC | Null |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User or service ID | Caller |
| updated_by | UUID | Yes | User or service ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: EvaluationRun belongs to EvaluationSet and may gate KnowledgeSnapshot publication.

Sample data:

| retrieval_mode | status | metrics | failed_cases |
|---|---|---|---|
| `hybrid` | `passed` | `{"recall":0.91,"mrr":0.84}` | `[]` |
| `vector` | `failed` | `{"recall":0.67,"mrr":0.58}` | `["case_004"]` |

## 4.29 Entity: FeedbackItem

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | Yes | FK KnowledgeBase | None |
| retrieval_query_id | UUID | No | FK RetrievalQuery | Null |
| reasoning_run_id | UUID | No | FK ReasoningRun | Null |
| source_kind | string | No | `chunk`, `fact`, `graph`, `wiki`, `prompt`, `answer` | Null |
| source_id | string | No | Source record ID | Null |
| rating | integer | Yes | -1, 0, or 1 | 0 |
| issue_category | string | Yes | `wrong`, `missing`, `stale`, `uncited`, `unsafe`, `other` | `other` |
| comment_redacted | text | No | PII-masked text | Null |
| review_status | string | Yes | `new`, `triaged`, `resolved`, `dismissed` | `new` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User or service ID | Caller |
| updated_by | UUID | Yes | User or service ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: FeedbackItem can create ReviewTasks and quality reports.

Sample data:

| rating | issue_category | source_kind | review_status |
|---:|---|---|---|
| -1 | `uncited` | `answer` | `new` |
| -1 | `stale` | `wiki` | `triaged` |

## 4.30 Entity: LLMUsageEvent

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | No | FK KnowledgeBase | Null |
| provider_config_id | UUID | Yes | FK LLMProviderConfig | None |
| prompt_template_id | UUID | No | FK PromptTemplate | Null |
| reasoning_run_id | UUID | No | FK ReasoningRun | Null |
| request_id | string | Yes | Request correlation ID | None |
| call_type | string | Yes | `prompt`, `embedding`, `rerank`, `summary` | None |
| provider | string | Yes | Provider name | None |
| model | string | Yes | Model ID | None |
| prompt_tokens | integer | Yes | Non-negative | 0 |
| completion_tokens | integer | Yes | Non-negative | 0 |
| estimated_cost_cents | integer | Yes | Non-negative | 0 |
| privacy_summary | json | Yes | Redaction counts and policy | Empty object |
| status | string | Yes | `succeeded`, `failed`, `blocked` | None |
| created_at | datetime | Yes | UTC | Now |

Relationships: LLMUsageEvent belongs to provider, prompt, and optionally ReasoningRun.

Sample data:

| call_type | provider | model | status |
|---|---|---|---|
| `embedding` | `openai` | `text-embedding-3-small` | `succeeded` |
| `prompt` | `gemini` | `gemini-1.5-pro` | `blocked` |

## 4.31 Entity: ReviewTask

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | No | FK KnowledgeBase | Null |
| task_type | string | Yes | `source`, `fact`, `graph`, `wiki`, `prompt`, `provider`, `feedback`, `quality_gate` | None |
| target_type | string | Yes | Entity name | None |
| target_id | string | Yes | Entity ID | None |
| priority | string | Yes | `low`, `medium`, `high`, `critical` | `medium` |
| owner_role | string | Yes | Domain role responsible | `reviewer` |
| due_at | datetime | No | UTC | Null |
| status | string | Yes | `open`, `in_progress`, `approved`, `rejected`, `resolved`, `expired` | `open` |
| resolution | json | Yes | Resolution details | Empty object |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User or service ID | Caller |
| updated_by | UUID | Yes | User or service ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: ReviewTask references the entity awaiting review and may be created by ingestion, feedback, or quality gates.

Sample data:

| task_type | target_type | priority | status |
|---|---|---|---|
| `fact` | `ExtractedFact` | `medium` | `open` |
| `quality_gate` | `KnowledgeSnapshot` | `high` | `in_progress` |

## 4.32 Entity: LegalHold

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | No | FK KnowledgeBase | Null |
| target_type | string | Yes | `domain`, `knowledge_base`, `source_document`, `wiki_article`, `graph_node`, `graph_edge`, `fact` | None |
| target_id | string | Yes | Target record ID | None |
| reason | text | Yes | Non-empty | None |
| effective_from | datetime | Yes | UTC | Now |
| effective_until | datetime | No | UTC | Null |
| status | string | Yes | `active`, `released`, `expired` | `active` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: LegalHold blocks deletion and archival purge of matching records.

Sample data:

| target_type | target_id | status | reason |
|---|---|---|---|
| `source_document` | `d7ce08a6` | `active` | `Court proceeding reference` |
| `knowledge_base` | `bns-legal` | `released` | `Review completed` |

## 4.33 Entity: IdempotencyRecord

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| principal_id | string | Yes | Caller identifier | None |
| idempotency_key | string | Yes | Unique by domain and principal | None |
| request_hash | string | Yes | SHA-256 request body hash | None |
| target_operation | string | Yes | Operation name | None |
| response_snapshot | json | No | Success response to replay | Null |
| status | string | Yes | `in_progress`, `succeeded`, `failed` | `in_progress` |
| expires_at | datetime | Yes | UTC | Now plus retention window |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | No | User or service ID | Null |
| updated_by | UUID | No | User or service ID | Null |
| is_deleted | boolean | Yes | True or false | false |

Relationships: IdempotencyRecord protects mutating API operations from duplicate side effects.

Sample data:

| idempotency_key | target_operation | status | expires_at |
|---|---|---|---|
| `upload-bns-v1-20260505` | `source.ingest` | `succeeded` | `2026-05-06T00:00:00Z` |
| `reasoning-fir-0001` | `reasoning.execute` | `succeeded` | `2026-05-06T00:00:00Z` |

## 4.34 Entity: DeletionRequest

| Field | Type | Required | Validation | Default |
|---|---|---:|---|---|
| id | UUID | Yes | Generated UUID | Generated |
| domain_id | UUID | Yes | FK Domain | None |
| knowledge_base_id | UUID | No | FK KnowledgeBase | Null |
| target_type | string | Yes | `source_document`, `wiki_article`, `graph_node`, `graph_edge`, `fact`, `knowledge_base` | None |
| target_id | string | Yes | Target record ID | None |
| deletion_mode | string | Yes | `soft_delete`, `purge_if_allowed` | `soft_delete` |
| reason | text | Yes | Non-empty | None |
| legal_hold_check | json | Yes | Hold status and IDs | Empty object |
| reindex_status | string | Yes | `not_required`, `pending`, `running`, `completed`, `failed` | `pending` |
| status | string | Yes | `requested`, `blocked`, `approved`, `completed`, `failed`, `cancelled` | `requested` |
| created_at | datetime | Yes | UTC | Now |
| updated_at | datetime | Yes | UTC | Now |
| created_by | UUID | Yes | User ID | Caller |
| updated_by | UUID | Yes | User ID | Caller |
| is_deleted | boolean | Yes | True or false | false |

Relationships: DeletionRequest references the target record and creates reindex jobs when deletion affects derived knowledge.

Sample data:

| target_type | deletion_mode | status | reindex_status |
|---|---|---|---|
| `source_document` | `soft_delete` | `completed` | `completed` |
| `knowledge_base` | `purge_if_allowed` | `blocked` | `not_required` |

# 5. Functional Requirements

## 5.1 Domain and Access Administration

### FR-001: Domain Management

Description: The service must allow platform administrators to create, activate, suspend, and archive domains. Each domain defines data residency, privacy policy, allowed providers, and ownership boundaries.

User story: As a Platform Administrator, I want to create isolated domains so that each business context can manage its own knowledge and governance.

Acceptance criteria:

- A new domain can be created with unique `code`, `name`, `data_residency`, and default `pii_policy`.
- Suspended domains reject ingestion, retrieval, and reasoning requests with `DOMAIN_SUSPENDED`.
- Archived domains remain readable only to platform admins and auditors.
- Domain deletion requires a soft delete and creates an audit event.

Business rules:

- Domain code cannot be changed after activation.
- At least one domain admin must be assigned before activation.
- The default privacy policy must block high-risk PII to LLM providers.

UI behavior notes:

- The Create Domain form disables submit until code, name, residency, and admin owner are valid.
- Suspending a domain requires a confirmation modal with affected knowledge base count.
- Errors show field-level messages and a top-level error summary.

Edge cases and error handling:

- Duplicate code returns `409 CONFLICT`.
- Missing admin owner returns `422 VALIDATION_ERROR`.
- Attempts to activate a domain without provider policy return `422 DOMAIN_POLICY_INCOMPLETE`.

### FR-002: Domain Membership and RBAC

Description: The service must manage domain-scoped memberships, roles, and scopes. Permissions must be enforced by API and database query filters.

User story: As a Domain Administrator, I want to assign curators, reviewers, developers, and auditors so that responsibilities are controlled inside my domain.

Acceptance criteria:

- Domain admin can add active users to their domain with a supported domain role.
- Users cannot access records from domains where they have no active membership.
- API keys inherit only the scopes explicitly assigned to their service principal.
- Membership changes are audit logged.

Business rules:

- Platform admins can manage all domains.
- Domain admins cannot grant platform roles.
- A user cannot approve their own membership escalation.

UI behavior notes:

- Role selector displays the exact scopes implied by each role.
- Removing the last domain admin is blocked with an inline explanation.

Edge cases and error handling:

- Unknown user returns `404 USER_NOT_FOUND`.
- Scope outside caller permission returns `403 SCOPE_NOT_ALLOWED`.

## 5.2 Knowledge Base and Ingestion

### FR-003: Knowledge Base Management

Description: Domain admins must create one or more knowledge bases inside a domain. Each knowledge base controls language support, retrieval profile, vector namespace, ontology, and publishing lifecycle.

User story: As a Domain Administrator, I want to create knowledge bases so that different knowledge collections can have separate retrieval and governance policies.

Acceptance criteria:

- Knowledge base code is unique within a domain.
- Retrieval profile includes weights for vector, graph, fact, wiki, and structured feature sources.
- Knowledge bases can be suspended independently of the domain.
- Retrieval requests for inactive knowledge bases return `KB_INACTIVE`.

Business rules:

- A knowledge base cannot be activated until at least one vector namespace and one privacy policy are configured.
- Default hybrid retrieval weights are vector 0.45, graph 0.20, facts 0.20, wiki 0.15.

UI behavior notes:

- Retrieval profile uses sliders with total-weight validation.
- Activation checklist shows missing configuration.

Edge cases and error handling:

- Invalid weight total returns `422 RETRIEVAL_PROFILE_INVALID`.
- Duplicate knowledge base code returns `409 CONFLICT`.

### FR-004: Source Connector Management

Description: Domain admins and developers must configure sources such as upload, cloud storage, database, Git repository, or API connector. Connector secrets must be references or encrypted credential IDs, never plaintext in configuration.

User story: As an Application Developer, I want to configure a source connector so that my application can synchronize domain content into KIS.

Acceptance criteria:

- Connector creation validates required configuration fields for each connector type.
- Secret-looking values in connector config are rejected unless stored as credential references.
- Connector sync can be paused and resumed.
- Manual sync creates an IngestionJob.

Business rules:

- Connector credentials require security review before activation.
- Connector sync cannot write outside its assigned domain and knowledge base.

UI behavior notes:

- Connector setup uses type-specific forms.
- The test connection button returns success, failure reason, and latency.

Edge cases and error handling:

- Invalid cron expression returns `422 INVALID_SCHEDULE`.
- Failed connection test returns `424 CONNECTOR_TEST_FAILED`.

### FR-005: Source Document Ingestion

Description: The service must ingest text, files, or file references into a knowledge base, capture metadata, detect duplicates by content hash, and start processing jobs.

User story: As a Knowledge Curator, I want to upload source documents so that they become searchable, reviewable, and citeable knowledge.

Acceptance criteria:

- Ingestion accepts raw text, multipart file upload, or object storage URI.
- Duplicate content hash in the same knowledge base creates a new version instead of duplicate active content.
- Document status moves from `pending` to `processing` to `review_required` or `published`.
- Failed ingestion preserves error code and error message.

Business rules:

- Restricted documents require reviewer approval before publication.
- Document metadata must include source type, title, language, and classification.
- OCR is invoked by consuming apps or connector-specific preprocessing, not directly mandated for KIS v1.

UI behavior notes:

- Upload screen shows progress per processing stage.
- Duplicate detection displays existing document and version details.

Edge cases and error handling:

- Unsupported file type returns `415 UNSUPPORTED_MEDIA_TYPE`.
- Empty text returns `422 EMPTY_DOCUMENT`.
- Hash collision suspicion returns `409 HASH_COLLISION_REVIEW_REQUIRED`.

### FR-006: Chunking and Embedding

Description: KIS must chunk document text by token budget, preserve overlap, generate embeddings, and store chunk-level metadata for retrieval and citation.

User story: As a Consuming Application, I want documents chunked and embedded automatically so that retrieval can find relevant passages.

Acceptance criteria:

- Chunk size and overlap are configurable per knowledge base.
- Every chunk stores chunk index, token count, citation reference, topics, entities, and confidence.
- Embedding failures mark only affected jobs failed and leave source document traceable.
- Reindexing can rebuild embeddings after model changes.

Business rules:

- Chunk overlap must be less than chunk size.
- Embedding model dimensions must match VectorNamespace dimensions.

UI behavior notes:

- Chunk preview shows chunk text, token count, embedding status, and citation reference.

Edge cases and error handling:

- Embedding provider unavailable returns `503 EMBEDDING_PROVIDER_UNAVAILABLE`.
- Dimension mismatch returns `422 EMBEDDING_DIMENSION_MISMATCH`.

## 5.3 Graph, Facts, and Wiki

### FR-007: Ontology Management

Description: Domain admins must define allowed node, edge, and fact types. Ontologies constrain graph construction and fact extraction.

User story: As a Domain Administrator, I want to define my domain ontology so that graph and fact extraction use approved semantics.

Acceptance criteria:

- Ontology types support draft, active, deprecated, and versioned states.
- Graph writes reject node, edge, and fact types that are not active.
- Ontology changes require reviewer approval before activation.
- Deprecated ontology types remain readable but cannot be used for new records.

Business rules:

- Edge ontology must define allowed source and target node types.
- JSON schema validation is applied to properties and structured claims.

UI behavior notes:

- Ontology editor provides separate tabs for nodes, edges, and facts.
- Schema validation errors highlight the invalid field path.

Edge cases and error handling:

- Breaking ontology change with active data returns `409 ONTOLOGY_IN_USE`.
- Invalid schema returns `422 INVALID_JSON_SCHEMA`.

### FR-008: Fact Extraction and Review

Description: KIS must extract candidate facts from documents using deterministic rules, NLP, or approved LLM prompts. Curators and reviewers must verify, reject, or correct candidate facts.

User story: As a Knowledge Curator, I want to review extracted facts so that the graph and retrieval results are grounded in verified claims.

Acceptance criteria:

- Candidate facts include claim, structured claim, confidence, source document, and source chunk.
- Facts below confidence threshold require review before graph promotion.
- Review actions update status to `verified` or `rejected`.
- Verified facts are available to hybrid retrieval.

Business rules:

- A fact cannot be verified without a source citation.
- Contradictory facts must link through `contradicted_by` or be resolved by reviewer action.

UI behavior notes:

- Fact review screen shows source snippet side by side with structured claim.
- Reviewer can edit structured fields before approval.

Edge cases and error handling:

- Missing source citation returns `422 FACT_SOURCE_REQUIRED`.
- Attempt to verify own generated fact can require second reviewer if policy says maker-checker.

### FR-009: Knowledge Graph Construction

Description: KIS must build and update graph nodes and edges from verified facts and approved ontology mappings. It must support traversal, graph stats, search, and source provenance.

User story: As a Domain Reviewer, I want verified facts promoted into a graph so that downstream reasoning can use relationships, not only text similarity.

Acceptance criteria:

- Graph builder deduplicates nodes by domain, knowledge base, node type, and external ID.
- Edge upsert keeps highest confidence and merges approved properties.
- Graph traversal supports configurable max depth and relationship filters.
- Graph stats show nodes and edges by type.

Business rules:

- Graph edges must cite a source fact or source document unless manually created by reviewer.
- Superseded edges remain auditable and inactive.

UI behavior notes:

- Graph explorer displays node search, neighborhood traversal, edge confidence, and citations.

Edge cases and error handling:

- Invalid relationship by ontology returns `422 EDGE_TYPE_NOT_ALLOWED`.
- Traversal exceeding max depth returns `422 GRAPH_DEPTH_TOO_HIGH`.

### FR-010: Wiki Compilation and Review

Description: KIS must compile approved source content into wiki articles using concept extraction, article generation, link resolution, and reviewer approval.

User story: As a Knowledge Curator, I want generated wiki drafts so that domain experts can maintain curated knowledge without manually rewriting every source.

Acceptance criteria:

- Wiki compilation supports changed-only and full rebuild modes.
- Draft articles include title, slug, domain area, content, source documents, concepts, tags, and wikilink report.
- Broken wikilinks are visible before publication.
- Published wiki articles are queryable and cite source documents.

Business rules:

- Generated wiki articles must remain drafts until reviewer approval.
- Every factual claim generated from source material must preserve citation metadata.

UI behavior notes:

- Wiki review screen shows article markdown, citations, link health, and source preview.

Edge cases and error handling:

- Duplicate slug creates a new article version, not a second active slug.
- LLM article generation failure creates an article failure entry and continues with remaining concepts.

## 5.4 Hybrid Retrieval and Reasoning

### FR-011: Vector Search

Description: KIS must support vector similarity search over document chunks with filters by domain, knowledge base, source type, classification, language, and metadata.

User story: As a Consuming Application, I want vector search so that semantically relevant text passages can be retrieved for a user query.

Acceptance criteria:

- Query text is embedded with the configured domain embedding model.
- Results include chunk, score, document metadata, and citation.
- Searches cannot return chunks outside caller domain and allowed knowledge base.
- Similarity threshold and top_k are enforced.

Business rules:

- Default max top_k is 50 for API calls.
- Query logs store redacted query text and hash, not raw PII.

UI behavior notes:

- Search diagnostics show score, source, chunk, and filters applied.

Edge cases and error handling:

- Missing embedding provider returns `503 EMBEDDING_PROVIDER_UNAVAILABLE`.
- top_k beyond limit returns `422 TOP_K_TOO_HIGH`.

### FR-012: Hybrid Retrieval

Description: KIS must combine vector results, graph traversals, extracted facts, wiki articles, and optional structured feature providers into a unified ranked context.

User story: As an Application Developer, I want one hybrid retrieval endpoint so that my app can get better context than vector-only search.

Acceptance criteria:

- Hybrid retrieval accepts include flags for vector, graph, facts, wiki, and structured features.
- Results include source type counts, elapsed time, final rank, relevance score, and citation.
- Retrieval degrades gracefully if a non-required source fails.
- Required source failure marks response as degraded or failed based on request policy.

Business rules:

- Final ranking must deduplicate near-identical content.
- Retrieval profile weights are domain configurable.
- Source failures must be logged with error code, not raw secret or PII.

UI behavior notes:

- Retrieval trace screen shows source fan-out, per-source status, and final reranking.

Edge cases and error handling:

- All sources fail returns `503 RETRIEVAL_UNAVAILABLE`.
- Partial source failure returns `200` with `degraded=true` if policy allows degradation.

### FR-013: Context Assembly

Description: KIS must assemble context for reasoning from configured sources, enforce token budgets, trim lower-priority context, and record which sources were used.

User story: As a Domain Administrator, I want context assembly to follow a configured profile so that LLM reasoning receives enough evidence without exceeding cost and privacy constraints.

Acceptance criteria:

- Context config names sources, required fields, graph traversals, wiki domains, vector query, top_k, and max tokens.
- Context assembly fans out to sources concurrently with timeout.
- Token trimming preserves required structured features before wiki and vector excerpts.
- Context snapshot stored for audit is PII-redacted.

Business rules:

- Raw high-risk PII cannot enter context sent to the LLM.
- Required source missing marks reasoning run degraded or failed based on pattern policy.

UI behavior notes:

- Pattern editor previews estimated token count and trimming order.

Edge cases and error handling:

- Context timeout returns `504 CONTEXT_TIMEOUT`.
- Missing required feature returns `422 REQUIRED_CONTEXT_MISSING` if pattern requires all sources.

### FR-014: Reasoning Pattern Execution

Description: KIS must execute reasoning patterns composed of rules, analytics, and LLM steps, similar to the PS-WMS reasoning engine.

User story: As a Domain Administrator, I want reusable reasoning patterns so that applications can run governed domain logic consistently.

Acceptance criteria:

- Pattern execution creates a ReasoningRun with queued, context_assembly, reasoning, and final status.
- Engine chain supports `rules`, `analytics`, and `llm`.
- LLM step uses approved provider, approved prompt, privacy controls, and cost budget.
- Output validates against configured schema before completion.

Business rules:

- LLM step cannot run if provider is inactive, unapproved, or over budget.
- Pattern traffic split resolves deterministic version by entity ID when configured.

UI behavior notes:

- Run detail shows chain steps, duration, model, cost, redaction summary, confidence, and citations.

Edge cases and error handling:

- Budget exceeded returns `402 COST_BUDGET_EXCEEDED`.
- Output schema violation returns `502 LLM_OUTPUT_SCHEMA_INVALID`.

### FR-015: Citation and Provenance

Description: Every retrieval answer and reasoning output must provide traceable source references where source-backed claims are used.

User story: As an Auditor, I want citations on generated outputs so that I can verify where each claim came from.

Acceptance criteria:

- Retrieval results always include citation payloads.
- Reasoning output includes citations for source-backed recommendations or mappings.
- Citation payload identifies source kind, source ID, document title or article slug, chunk index when applicable, and confidence.
- Missing citations lower confidence or block output when policy requires citations.

Business rules:

- Regulated domains must require citations for final LLM answers.
- Generated wiki citations must point back to original source documents.

UI behavior notes:

- Citation clicks open source preview in a side panel.

Edge cases and error handling:

- Citation target deleted returns source preview `410 SOURCE_RETIRED` while preserving audit metadata.

## 5.5 LLM Governance and Privacy

### FR-016: LLM Provider Configuration

Description: Domain admins must define which LLM providers and models may be used for each domain. Security administrators must review provider configurations before activation.

User story: As a Domain Administrator, I want to configure allowed LLMs so that my domain can use approved models with known limits and fallbacks.

Acceptance criteria:

- Provider config includes provider type, base URL if applicable, allowed models, default model, embedding models, token limit, budget, and fallback provider.
- Provider cannot be active until a credential and security review are complete.
- Requests for disallowed models are blocked.
- Provider status changes are audit logged.

Business rules:

- Domain provider allowlist overrides platform default.
- Self-hosted provider requires HTTPS base URL or explicitly approved private network URL.

UI behavior notes:

- Provider setup form shows security review status and activation checklist.

Edge cases and error handling:

- Unknown model returns `403 MODEL_NOT_ALLOWED`.
- Inactive provider returns `403 PROVIDER_INACTIVE`.

### FR-017: Encrypted Credential Maintenance

Description: Domain admins must store LLM API keys and connector credentials using encrypted database storage or secret manager references. Plaintext credentials must never be returned by API or stored in logs.

User story: As a Security Administrator, I want credentials encrypted and non-readable so that domain teams can maintain keys without exposing secrets.

Acceptance criteria:

- Credential create accepts plaintext only over HTTPS request body and immediately encrypts or stores in secret manager.
- Read APIs return credential metadata and masked fingerprint only.
- Rotation creates an audit event and invalidates old credential when requested.
- Credential expiry can block provider use.

Business rules:

- `encrypted_secret` and `secret_manager_ref` cannot both be null.
- Plaintext secret cannot be written to AuditEvent metadata.
- Production requires KMS or approved secret manager.

UI behavior notes:

- Credential detail screen never displays the secret value.
- Rotation form confirms provider impact before save.

Edge cases and error handling:

- Expired credential returns `403 CREDENTIAL_EXPIRED`.
- KMS failure returns `503 SECRET_ENCRYPTION_UNAVAILABLE`.

### FR-018: PII Protection for LLM Calls

Description: KIS must mask or tokenize high-risk PII before sending any prompt, context, or retrieved content to an LLM, encrypt the token map locally, restore values after response when needed, and scan for leakage.

User story: As a Security Administrator, I want PII protected before LLM calls so that external models never receive raw personal data.

Acceptance criteria:

- PII categories include name, address, email, phone, government ID, bank account, vehicle ID, and domain-defined fields.
- LLM-bound payload uses tokens such as `[[PII_EMAIL_0001]]`, not raw PII.
- Token map is encrypted in memory or temporary secure storage and never persisted in logs.
- Response restoration happens after model response and before final application response only when caller is authorized to see original values.
- Strict mode blocks request if high-risk PII remains after masking.

Business rules:

- Privacy policy can choose tokenization, generalization, irreversible redaction, or block for each PII type.
- Prompt logs store redacted prompts only.
- High-risk PII leakage violation creates critical audit event.

UI behavior notes:

- Reasoning run detail shows redaction count and PII types, never original values.

Edge cases and error handling:

- PII detection error returns `503 PRIVACY_ENGINE_UNAVAILABLE`.
- Unmasked high-risk PII detection returns `422 PII_LEAKAGE_BLOCKED`.

### FR-019: Prompt Template Governance

Description: KIS must provide versioned prompt templates with draft, review, approval, activation, and rollback lifecycle.

User story: As a Domain Reviewer, I want prompt changes reviewed before use so that LLM behavior remains controlled and auditable.

Acceptance criteria:

- Prompt template stores system prompt, user template, output schema, task type, privacy policy, and review status.
- Only approved templates can be activated.
- Activation and rollback create audit events.
- Prompt render endpoint previews rendered prompt with PII protection indicators.

Business rules:

- Prompt author cannot be sole approver if maker-checker policy is enabled.
- Active prompt version cannot be hard-deleted.

UI behavior notes:

- Prompt editor supports diff between versions.
- Output schema validation runs before submit.

Edge cases and error handling:

- Invalid template placeholder returns `422 PROMPT_RENDER_ERROR`.
- Unapproved prompt execution returns `403 PROMPT_NOT_APPROVED`.

### FR-020: Cost, Token, and Usage Governance

Description: KIS must meter LLM and embedding usage, enforce budgets, expose usage reports, and support provider fallback.

User story: As a Platform Administrator, I want cost controls so that model usage remains predictable and accountable by domain.

Acceptance criteria:

- Each LLM call records provider, model, prompt tokens, completion tokens, estimated cost, domain, pattern, and request ID.
- Domain monthly budgets block or review further calls when exceeded based on policy.
- Per-request token limit blocks oversized prompt construction before provider call.
- Fallback provider is used only if allowed by domain policy.

Business rules:

- Cost estimates must use configured provider price table.
- Budget override requires platform admin or security admin.

UI behavior notes:

- Usage dashboard groups cost by domain, provider, model, task, and knowledge base.

Edge cases and error handling:

- Monthly budget exceeded returns `402 DOMAIN_BUDGET_EXCEEDED`.
- Missing price table returns `422 PROVIDER_PRICING_REQUIRED`.

## 5.6 Quality, Learning, and Operations

### FR-021: Retrieval Evaluation Sets

Description: KIS must maintain golden query sets per domain to compare vector-only, graph-only, wiki-only, and hybrid retrieval quality.

User story: As a Domain Administrator, I want retrieval evaluation sets so that changes to chunking, embeddings, ontology, and ranking can be measured before production.

Acceptance criteria:

- Evaluation set stores query, expected source IDs, expected answer traits, and minimum score thresholds.
- Evaluation run reports recall, precision, MRR, citation coverage, and degraded-source count.
- Hybrid retrieval can be compared to vector-only baseline.
- Failing evaluation blocks promotion if quality gate is required.

Business rules:

- Every production knowledge base must have at least one smoke-test evaluation set.
- Model or ranker changes require evaluation run before activation.

UI behavior notes:

- Evaluation dashboard shows trend by run and source mode.

Edge cases and error handling:

- Empty evaluation set returns `422 EVALUATION_SET_EMPTY`.
- Missing expected sources returns warning and computes answer-only metrics.

### FR-022: Feedback and Learning Loop

Description: KIS must collect user and application feedback on retrieval results, wiki articles, graph facts, and reasoning outputs.

User story: As a Knowledge Curator, I want feedback on answers and sources so that low-quality knowledge can be corrected.

Acceptance criteria:

- Feedback captures rating, issue category, free text, source ID, retrieval query ID, and reasoning run ID.
- Feedback can create curator review tasks.
- Repeated negative feedback on the same source flags it for review.
- Feedback reports are domain-scoped.

Business rules:

- Feedback free text passes through PII masking before any LLM analysis.
- User feedback cannot directly modify published knowledge without review.

UI behavior notes:

- Result detail includes thumbs up/down, issue type, and comment field.

Edge cases and error handling:

- Feedback on unavailable source returns `410 SOURCE_RETIRED`.
- Anonymous feedback is rejected for internal domains.

### FR-023: Shadow Mode and A/B Testing

Description: KIS must support shadow retrieval and reasoning runs for testing new prompts, models, and rankers without affecting production responses.

User story: As a Domain Administrator, I want to test new retrieval and reasoning configurations in shadow mode so that I can measure impact before activation.

Acceptance criteria:

- Shadow runs execute using a candidate pattern, provider, or retrieval profile without returning candidate output to the caller.
- A/B traffic splits route a controlled percentage of eligible requests to approved candidate versions.
- Metrics compare baseline and candidate latency, cost, quality, and feedback.
- Rollback can set candidate traffic to zero immediately.

Business rules:

- Shadow runs still enforce privacy, provider, and cost controls.
- Candidate configs require approval before receiving live traffic.

UI behavior notes:

- Experiment dashboard shows baseline versus candidate metrics and rollback button.

Edge cases and error handling:

- Candidate provider failure does not fail the production request if baseline succeeds.
- Invalid traffic percentage returns `422 TRAFFIC_SPLIT_INVALID`.

### FR-024: Audit and Compliance Review

Description: KIS must audit administrative changes, data access, provider usage, policy violations, and security-sensitive operations.

User story: As an Auditor, I want complete audit trails so that I can verify who changed knowledge, prompts, providers, and policies.

Acceptance criteria:

- Audit events are written for create, update, delete, approve, activate, execute, query, and block actions.
- Audit metadata is PII-redacted and secret-redacted.
- Audit search supports domain, actor, action, target, request ID, and date range.
- Audit export is available to auditors and platform admins.

Business rules:

- Audit events are append-only.
- Audit retention defaults to 7 years for regulated domains unless configured otherwise.

UI behavior notes:

- Audit screen provides filters, CSV export, and event detail drawer.

Edge cases and error handling:

- Audit write failure for security-sensitive actions blocks the primary action with `503 AUDIT_UNAVAILABLE`.

### FR-025: Health, Metrics, and Operations

Description: KIS must expose health checks, Prometheus metrics, readiness checks, and operational dashboards.

User story: As a Platform Administrator, I want operational visibility so that I can detect degraded knowledge services before users are affected.

Acceptance criteria:

- Health endpoint reports database, vector store, queue, provider configuration, and secret store status.
- Metrics include request count, latency, ingestion jobs, LLM tokens, cost, retrieval source failures, and privacy blocks.
- Readiness fails if database is unavailable or mandatory migrations are missing.
- Liveness does not depend on external LLM providers.

Business rules:

- Health responses must not expose secrets.
- Provider health checks use lightweight non-sensitive calls or configuration checks.

UI behavior notes:

- Operations dashboard uses status indicators and trend charts.

Edge cases and error handling:

- Missing database migration returns `503 MIGRATION_REQUIRED`.

### FR-026: Application Integration Adapter

Description: KIS must provide stable service APIs and a lightweight integration pattern for compliant-parser and other applications.

User story: As an Application Developer, I want a documented integration adapter so that my application can query knowledge and reasoning without importing KIS internals.

Acceptance criteria:

- API supports domain-scoped query, hybrid retrieval, reasoning execution, and source citation fetch.
- Service credentials map to domain, application, scopes, and rate limits.
- Response schema is stable and versioned.
- Integration errors use standardized error shape.

Business rules:

- Browser clients must not call KIS directly unless explicit public-client policy exists.
- Every integration request must include request ID or receive a generated request ID.

UI behavior notes:

- Developer screen shows API keys, scopes, usage, and sample curl for assigned domain.

Edge cases and error handling:

- Missing service credential returns `401 MISSING_API_KEY`.
- Unauthorized domain returns `403 DOMAIN_ACCESS_DENIED`.

## 5.7 Release Governance and Platform Hardening

### FR-027: Domain Templates and Guided Setup

Description: KIS must provide domain templates that seed domain policy, knowledge base settings, ontology, prompts, retrieval profile, and evaluation smoke tests.

User story: As a Domain Administrator, I want to start from a domain template so that I can create a usable knowledge base without configuring every platform primitive manually.

Acceptance criteria:

- Platform admins can create and activate DomainTemplates.
- Domain admins can choose an active template during knowledge base setup.
- Template application creates reviewable seed records and records source template version.
- Police IQW BNS and PS-WMS advisory templates exist for MVP validation.

Business rules:

- Template application must not overwrite existing active records without explicit confirmation.
- Template-created prompts and ontology types must still follow approval policy before production use.

UI behavior notes:

- Setup wizard shows template preview, included ontology, prompts, policies, and evaluation cases.

Edge cases and error handling:

- Template version retired during setup returns `409 TEMPLATE_RETIRED`.
- Invalid template seed returns `422 TEMPLATE_INVALID`.

### FR-028: Published Knowledge Snapshots

Description: KIS must publish immutable knowledge snapshots so consuming applications can bind to stable knowledge versions and roll back safely.

User story: As an Application Developer, I want to bind my app to a published knowledge snapshot so that retrieval behavior does not change unexpectedly during curator edits.

Acceptance criteria:

- Snapshot includes source versions, chunk/index version, ontology versions, graph version, wiki versions, prompt versions, retrieval profile, and policy versions.
- Snapshot publication requires passing mandatory quality gates.
- Retrieval and reasoning requests can target latest published snapshot or a specific snapshot version.
- Rollback marks the current snapshot retired and reactivates a previous published snapshot.

Business rules:

- Draft knowledge is not visible to production service principals unless explicitly allowed.
- Published snapshots are immutable; changes create a new snapshot.

UI behavior notes:

- Snapshot screen shows diff from previous snapshot, quality gate status, and rollback action.

Edge cases and error handling:

- Publishing with failed quality gate returns `409 QUALITY_GATE_FAILED`.
- Requesting a retired snapshot returns `410 SNAPSHOT_RETIRED`.

### FR-029: Embedding Privacy Controls

Description: KIS must apply privacy policy to embedding generation because external embedding providers receive document chunks and query text.

User story: As a Security Administrator, I want embedding calls governed like LLM calls so that sensitive data is not leaked through vectorization.

Acceptance criteria:

- Domain policy defines whether each PII type is tokenized, generalized, blocked, or explicitly allowed before embedding.
- External embedding calls record privacy summary in LLMUsageEvent with `call_type=embedding`.
- Query embedding masks PII before external provider calls unless the provider is approved as private/trusted.
- Raw and masked embedding modes are visible in provider configuration.

Business rules:

- Regulated domains default to masked embeddings.
- Trusted private embedding providers require security approval and audit logging.

UI behavior notes:

- Provider configuration shows whether provider is approved for raw embeddings.

Edge cases and error handling:

- High-risk PII remaining before external embedding returns `422 EMBEDDING_PII_BLOCKED`.
- Embedding policy missing returns `422 EMBEDDING_PRIVACY_POLICY_REQUIRED`.

### FR-030: Idempotent Mutating APIs

Description: KIS must prevent duplicate side effects when clients retry mutating operations.

User story: As an Application Developer, I want idempotency keys on mutating APIs so that retries do not create duplicate knowledge records or duplicate provider charges.

Acceptance criteria:

- Mutating APIs accept an `Idempotency-Key` header.
- Repeating the same key and same request returns the original response.
- Repeating the same key with a different request body returns `409 IDEMPOTENCY_CONFLICT`.
- Idempotency records expire after a configurable retention window.

Business rules:

- Idempotency is mandatory for source ingestion, graph build, wiki compile, snapshot publish, reasoning execution, and provider credential rotation.
- External provider calls must not start until the idempotency record is acquired.

UI behavior notes:

- Admin UI generates idempotency keys automatically for retryable operations.

Edge cases and error handling:

- In-progress duplicate request returns `409 OPERATION_IN_PROGRESS`.
- Expired key is treated as a new request.

### FR-031: Legal Hold, Retention, and Reindex After Delete

Description: KIS must support domain retention policies, legal holds, soft delete, hard purge where allowed, and reindexing after deletion.

User story: As a Security Administrator, I want deletion and legal hold controls so that KIS satisfies privacy obligations without destroying records under hold.

Acceptance criteria:

- LegalHold can block deletion or purge of target records.
- Deletion request soft-deletes source documents and removes them from future snapshots.
- Vector indexes, graph edges, facts, and wiki articles derived from deleted sources are reindexed or marked inactive.
- Audit events preserve deletion metadata without storing raw deleted content.

Business rules:

- Records under active legal hold cannot be purged.
- Retention windows are domain configurable and default to 7 years for regulated domains.

UI behavior notes:

- Retention screen shows records under hold, pending deletes, and reindex status.

Edge cases and error handling:

- Delete under active legal hold returns `409 LEGAL_HOLD_ACTIVE`.
- Reindex failure after delete creates critical ReviewTask.

### FR-032: PS-WMS Compatibility and Migration

Description: KIS must provide a migration path from PS-WMS intelligence-service without breaking existing PS-WMS integrations.

User story: As a Platform Administrator, I want PS-WMS migration adapters so that existing intelligence workflows continue while reusable KIS is introduced.

Acceptance criteria:

- PS-WMS `app_id` maps to a KIS Domain and service principal.
- Existing PS-WMS retrieval and reasoning calls can be routed through an adapter or versioned endpoint.
- Migration tests compare PS-WMS baseline retrieval output to KIS output on golden sets.
- Deprecated PS-WMS endpoints emit deprecation warnings before removal.

Business rules:

- PS-WMS migration must preserve source provenance, facts, graph nodes, wiki articles, and prompt versions.
- No production PS-WMS traffic moves to KIS until golden-set regression passes.

UI behavior notes:

- Migration dashboard shows migrated document count, graph count, wiki count, prompt count, and regression status.

Edge cases and error handling:

- Missing source mapping returns `422 MIGRATION_MAPPING_MISSING`.
- Golden-set regression failure blocks cutover with `409 MIGRATION_QUALITY_GATE_FAILED`.

### FR-033: Graph, Wiki, and Citation Quality Gates

Description: KIS must gate publication on quality checks for graph, wiki, facts, vector retrieval, and citations.

User story: As a Domain Reviewer, I want quality gates before publication so that broken links, contradictory facts, and uncited answers do not enter production snapshots.

Acceptance criteria:

- Quality gate checks broken wiki links, orphan wiki articles, low-confidence graph edges, contradictory active facts, citation coverage, and retrieval evaluation results.
- Gate severity can be `blocker`, `warning`, or `info`.
- Blocker failures prevent snapshot publication.
- Quality gate failures create ReviewTasks with owners and due dates.

Business rules:

- Regulated domains must block on citation coverage below configured threshold.
- Contradictory facts cannot both be active unless marked as unresolved and excluded from production retrieval.

UI behavior notes:

- Quality gate screen groups failures by source artifact and provides direct links to remediation screens.

Edge cases and error handling:

- Quality gate engine failure returns `503 QUALITY_GATE_UNAVAILABLE`.
- Missing evaluation set returns `422 RELEASE_GATE_EVALUATION_REQUIRED`.

# 6. User Interface Requirements

## 6.1 Design System

The admin UI should use React with Tailwind CSS and shadcn/ui/Radix primitives unless the host platform provides an established design system. Components must use accessible labels, keyboard navigation, responsive tables, modals for confirmation, tabs for grouped settings, toasts for asynchronous actions, and compact operational layouts rather than marketing-style pages.

## 6.2 Major Screens

| Screen | Purpose | Layout and Components | Navigation | Responsive Behavior |
|---|---|---|---|---|
| Domain Dashboard | Overview of assigned domains and platform health. | Domain table, status chips, usage cards, critical alerts, recent audit events. | Opens domain detail, create domain, audit. | Tables collapse to searchable cards on mobile. |
| Domain Template Wizard | Create a domain or knowledge base from a curated template. | Template cards, included controls preview, policy summary, seed confirmation, expert settings link. | From domain dashboard and KB create flow. | Template cards stack and preview opens as drawer. |
| Domain Settings | Manage domain policy, residency, privacy, and owners. | Form sections, policy JSON editor, membership table, activation checklist. | From dashboard and admin nav. | Form sections stack vertically. |
| Knowledge Base List | Manage knowledge bases in a domain. | Filter bar, table with status, source count, chunks, graph nodes, wiki articles. | Opens KB detail or create flow. | List becomes cards with primary actions. |
| Knowledge Base Detail | Operational view of one knowledge base. | Tabs for sources, chunks, graph, wiki, retrieval profile, evaluations, jobs. | From KB list. | Tabs convert to menu on narrow screens. |
| Snapshot Release Manager | Publish, compare, and roll back knowledge snapshots. | Snapshot table, diff viewer, quality gate panel, publish and rollback controls. | From KB detail. | Diff viewer stacks before action panel. |
| Source Upload and Connectors | Upload files and configure external sources. | Upload dropzone, connector cards, sync job table, test connection panel. | From KB detail. | Dropzone and forms stack. |
| Ingestion Job Detail | Inspect processing progress and failures. | Timeline, stage logs, counts, errors, retry button, source metadata. | From jobs table or notification. | Timeline becomes vertical compact list. |
| Ontology Editor | Maintain node, edge, and fact types. | Tabs, schema editor, relationship matrix, review status controls. | From KB detail. | Matrix scrolls horizontally with sticky first column. |
| Fact Review Queue | Review candidate facts. | Split view with source snippet, structured claim form, confidence, approve/reject buttons. | From KB detail or notification. | Source and form stack with sticky action bar. |
| Graph Explorer | Traverse and search graph. | Search box, graph canvas or table fallback, node detail drawer, edge citations. | From KB detail and result citations. | Canvas switches to list-first exploration. |
| Wiki Review | Review generated wiki drafts and published articles. | Article list, markdown preview, source citations, link health, approval actions. | From KB detail. | Preview and metadata stack. |
| Retrieval Playground | Test vector and hybrid retrieval. | Query input, source toggles, filter panel, ranked results, retrieval trace. | From KB detail and developer nav. | Results remain single-column. |
| Reasoning Pattern Editor | Configure context sources, engine chain, prompts, budgets, and outputs. | Stepper or tabs, prompt selection, token estimate, cost estimate, schema validator. | From KB detail. | Stepper becomes vertical. |
| LLM Provider Maintenance | Configure providers, models, credentials, budgets, and fallback. | Provider table, credential modal, model allowlist, security review status. | From domain settings. | Provider rows become summary cards. |
| Evaluation Dashboard | Run and inspect retrieval evaluation sets. | Gold-set table, run charts, metrics, failures, source-level drilldown. | From KB detail. | Charts stack above result table. |
| Quality Gate Review | Review release blockers across retrieval, graph, facts, wiki, and citations. | Gate status grid, grouped findings, owner assignment, remediation links. | From Snapshot Release Manager and Evaluation Dashboard. | Findings become accordion list. |
| Retention and Legal Hold | Manage holds, delete requests, and reindex-after-delete status. | Hold table, delete request queue, target detail drawer, reindex progress. | From domain settings and audit. | Tables collapse to searchable cards. |
| Audit Log | Search and export audit events. | Filters, event table, JSON detail drawer, export action. | From platform nav. | Filters collapse into drawer. |
| Operations Dashboard | Service health and metrics. | Status grid, latency charts, provider health, queue depth, privacy blocks. | Platform nav. | Cards stack by severity. |

# 7. API and Integration Requirements

## 7.1 Authentication

- Internal applications authenticate using `X-API-Key` or OAuth2 client credentials.
- Admin UI users authenticate using OIDC or SAML through the host identity provider.
- Each request resolves a principal, domain access, scopes, and rate limit profile.
- Mutating API requests must include `Idempotency-Key` unless explicitly documented as non-idempotent internal maintenance.

## 7.2 Standard Error Format

All API errors must use this JSON shape:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human readable message",
    "field": "optional.field.path",
    "request_id": "req_20260505_0001",
    "details": {}
  }
}
```

## 7.3 Core API Endpoints

| Method | Path | Purpose | Required Scope |
|---|---|---|---|
| GET | `/api/v1/domain-templates` | List active domain templates | `domain:read` |
| POST | `/api/v1/domain-templates` | Create domain template | `platform:admin` |
| POST | `/api/v1/domains` | Create domain | `platform:admin` |
| GET | `/api/v1/domains` | List visible domains | `domain:read` |
| POST | `/api/v1/domains/{domain_id}/memberships` | Add membership | `domain:admin` |
| POST | `/api/v1/domains/{domain_id}/apply-template` | Apply template seed to domain | `domain:admin` |
| POST | `/api/v1/domains/{domain_id}/knowledge-bases` | Create knowledge base | `kb:write` |
| GET | `/api/v1/domains/{domain_id}/knowledge-bases` | List knowledge bases | `kb:read` |
| POST | `/api/v1/kb/{kb_id}/sources` | Ingest source document | `source:write` |
| GET | `/api/v1/kb/{kb_id}/sources/{source_id}` | Get source detail | `source:read` |
| POST | `/api/v1/kb/{kb_id}/sources/{source_id}/publish` | Publish reviewed source | `source:approve` |
| GET | `/api/v1/kb/{kb_id}/chunks` | List chunks | `chunk:read` |
| POST | `/api/v1/kb/{kb_id}/search/vector` | Vector search | `query:read` |
| POST | `/api/v1/kb/{kb_id}/search/hybrid` | Hybrid retrieval | `query:read` |
| POST | `/api/v1/kb/{kb_id}/graph/build` | Build graph | `graph:write` |
| GET | `/api/v1/kb/{kb_id}/graph/search` | Search graph nodes | `graph:read` |
| GET | `/api/v1/kb/{kb_id}/graph/nodes/{node_id}` | Get graph node | `graph:read` |
| POST | `/api/v1/kb/{kb_id}/wiki/compile` | Compile wiki drafts | `wiki:write` |
| GET | `/api/v1/kb/{kb_id}/wiki/articles` | List wiki articles | `wiki:read` |
| POST | `/api/v1/kb/{kb_id}/snapshots` | Create draft snapshot | `snapshot:write` |
| POST | `/api/v1/kb/{kb_id}/snapshots/{snapshot_id}/publish` | Publish snapshot | `snapshot:approve` |
| POST | `/api/v1/kb/{kb_id}/snapshots/{snapshot_id}/rollback` | Roll back to snapshot | `snapshot:approve` |
| POST | `/api/v1/kb/{kb_id}/quality-gates/run` | Run release quality gates | `quality:run` |
| POST | `/api/v1/kb/{kb_id}/evaluations` | Create evaluation set | `evaluation:write` |
| POST | `/api/v1/kb/{kb_id}/evaluations/{evaluation_id}/runs` | Run evaluation | `evaluation:run` |
| POST | `/api/v1/kb/{kb_id}/feedback` | Submit feedback | `feedback:write` |
| POST | `/api/v1/kb/{kb_id}/reasoning/patterns` | Create reasoning pattern | `reasoning:write` |
| POST | `/api/v1/kb/{kb_id}/reasoning/execute` | Execute reasoning | `reasoning:execute` |
| POST | `/api/v1/domains/{domain_id}/llm/providers` | Configure LLM provider | `llm:admin` |
| POST | `/api/v1/domains/{domain_id}/llm/credentials` | Create encrypted credential | `credential:write` |
| POST | `/api/v1/domains/{domain_id}/legal-holds` | Create legal hold | `retention:admin` |
| POST | `/api/v1/domains/{domain_id}/delete-requests` | Request deletion and reindex | `retention:admin` |
| GET | `/api/v1/audit/events` | Search audit logs | `audit:read` |
| GET | `/api/v1/health` | Health check | Public or authenticated by deployment policy |
| GET | `/api/v1/metrics` | Prometheus metrics | `platform:metrics` |

## 7.4 Request and Response Examples

### Create Knowledge Base

Request:

```json
{
  "code": "bns-legal",
  "name": "BNS Legal Knowledge",
  "description": "Legal sections and mapping rules for FIR drafting",
  "default_language": "en",
  "supported_languages": ["en", "hi", "te"],
  "retrieval_profile": {
    "vector_weight": 0.45,
    "graph_weight": 0.2,
    "fact_weight": 0.2,
    "wiki_weight": 0.15,
    "default_top_k": 10
  }
}
```

Response:

```json
{
  "id": "8f7c0a1c-8a1d-4fa1-b0e1-a3c7e6030001",
  "domain_id": "5cb1a281-2bb2-4b01-87b1-6ac8d1e90001",
  "code": "bns-legal",
  "name": "BNS Legal Knowledge",
  "status": "draft",
  "created_at": "2026-05-05T10:00:00Z"
}
```

### Ingest Source Document

Request:

```json
{
  "source_type": "legal_reference",
  "title": "BNS Section Reference v1",
  "raw_text": "Section text and legal descriptions...",
  "language": "en",
  "classification": "internal",
  "metadata": {
    "jurisdiction": "India",
    "source_version": "v1"
  },
  "processing_options": {
    "chunk": true,
    "embed": true,
    "extract_facts": true,
    "build_graph": false,
    "compile_wiki": false
  }
}
```

Response:

```json
{
  "document": {
    "id": "d7ce08a6-8f65-48fd-99f0-e7b8a9190001",
    "title": "BNS Section Reference v1",
    "processing_status": "processing",
    "content_hash": "9f2c8a95d7e5b6c9"
  },
  "jobs": [
    {
      "id": "job_9e8b0001",
      "job_type": "chunk",
      "status": "queued"
    }
  ],
  "request_id": "req_20260505_100001"
}
```

### Hybrid Search

Request:

```json
{
  "query": "Which BNS sections apply to a theft complaint involving a stolen motorcycle?",
  "top_k": 10,
  "similarity_threshold": 0.65,
  "include_vector": true,
  "include_graph": true,
  "include_facts": true,
  "include_wiki": true,
  "filters": {
    "language": "en",
    "classification_max": "internal"
  }
}
```

Response:

```json
{
  "query_id": "a4dfba49-2a01-4551-a743-8a44d6300001",
  "query": "Which BNS sections apply to a theft complaint involving a stolen motorcycle?",
  "degraded": false,
  "elapsed_ms": 812,
  "source_counts": {
    "vector": 5,
    "graph": 3,
    "fact": 2,
    "wiki": 2
  },
  "results": [
    {
      "rank": 1,
      "source_kind": "wiki",
      "content": "BNS 303 applies to theft of movable property...",
      "relevance_score": 0.94,
      "citation": {
        "source_id": "wiki_bns_303",
        "title": "BNS 303 Theft",
        "source_document_id": "d7ce08a6-8f65-48fd-99f0-e7b8a9190001"
      }
    }
  ],
  "privacy": {
    "pii_redacted_before_llm": false,
    "raw_pii_sent_to_llm": false
  }
}
```

### Execute Reasoning Pattern

Request:

```json
{
  "pattern_key": "fir_bns_mapping",
  "entity_type": "complaint",
  "entity_id": "complaint_2026_0001",
  "input": {
    "incident_type": "vehicle theft",
    "facts": "The complainant reports that a motorcycle was stolen from the station parking area."
  },
  "options": {
    "require_citations": true,
    "max_tokens": 4000
  }
}
```

Response:

```json
{
  "run_id": "2e6c7b2b-a4b0-47e2-a219-b98f61ad0001",
  "pattern_key": "fir_bns_mapping",
  "status": "completed",
  "confidence": 0.91,
  "result": {
    "recommended_sections": [
      {
        "code": "BNS 303",
        "label": "Theft",
        "rationale": "The facts describe theft of movable property.",
        "confidence": 0.91,
        "citations": ["wiki_bns_303", "fact_legal_mapping_001"]
      }
    ]
  },
  "privacy": {
    "pii_redacted_before_llm": true,
    "redaction_count": 2,
    "redaction_types": ["NAME", "VEHICLE_ID"],
    "raw_pii_sent_to_llm": false
  },
  "llm_usage": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "prompt_tokens": 1240,
    "completion_tokens": 310,
    "cost_cents": 1
  }
}
```

### Publish Knowledge Snapshot

Request:

```json
{
  "label": "BNS legal baseline May 2026",
  "require_quality_gate": true,
  "quality_gate_policy": {
    "min_recall": 0.85,
    "min_citation_coverage": 0.95,
    "block_on_broken_wikilinks": true,
    "block_on_active_contradictions": true
  },
  "notes": "Initial production snapshot for compliant-parser BNS mapping."
}
```

Response:

```json
{
  "snapshot_id": "a4c5f639-8840-4c8e-9c84-95f424090001",
  "snapshot_version": 3,
  "status": "published",
  "published_at": "2026-05-05T11:10:00Z",
  "quality_gate_result": {
    "status": "passed",
    "recall": 0.91,
    "citation_coverage": 1.0,
    "broken_wikilinks": 0,
    "active_contradictions": 0
  }
}
```

### Create Encrypted LLM Credential

Request:

```json
{
  "secret_name": "openai-police-prod",
  "provider": "openai",
  "secret_value": "sk-REDACTED-FOR-EXAMPLE",
  "expires_at": "2026-08-01T00:00:00Z"
}
```

Response:

```json
{
  "id": "c8a77f96-77a2-4ee9-b962-15f85f500001",
  "secret_name": "openai-police-prod",
  "fingerprint": "sha256:9f2c8a95",
  "status": "active",
  "last_rotated_at": "2026-05-05T10:15:00Z",
  "expires_at": "2026-08-01T00:00:00Z"
}
```

## 7.5 External Integrations

| Integration | Purpose | Direction | Security Requirement |
|---|---|---|---|
| PostgreSQL with pgvector | Metadata, graph, chunks, vectors | KIS to DB | TLS, least privilege DB role |
| Redis or queue service | Async jobs, events, fatigue, rate counters | KIS to queue | Authenticated connection |
| Secret manager or KMS | Credential encryption and retrieval | KIS to secret store | Service identity, audit enabled |
| OpenAI | LLM and embeddings | KIS to provider | Domain allowlist, PII masking |
| Google Gemini | LLM and optional embeddings | KIS to provider | Domain allowlist, PII masking |
| Anthropic | LLM fallback | KIS to provider | Domain allowlist, PII masking |
| Self-hosted LLM endpoint | Private model execution | KIS to provider | TLS/private network, allowlist |
| Compliant-parser | Query and reasoning consumer | App to KIS | Service API key, domain scope |
| PS-WMS feature service | Optional structured features | KIS to service | Internal service credential |

## 7.6 Rate Limiting

- Admin APIs: 120 requests per minute per user by default.
- Query APIs: 600 requests per minute per service principal by default.
- Reasoning APIs: 60 requests per minute per service principal by default.
- Credential APIs: 20 requests per hour per user.
- Limits are domain-configurable and can be tightened by policy.

# 8. Non-Functional Requirements

## 8.1 Performance

| Area | Target |
|---|---|
| Vector search P95 | Under 500 ms for top 10 within 1 million chunks on indexed PostgreSQL/pgvector deployment. |
| Hybrid retrieval P95 | Under 2.5 seconds for top 10 when all sources respond. |
| Reasoning request P95 | Under 15 seconds excluding external LLM provider outage or configured long-running pattern. |
| Ingestion throughput | At least 100 documents per hour for 10-page average documents on baseline deployment. |
| Admin UI initial load | Under 2 seconds on broadband desktop. |

## 8.2 Security

- Enforce authentication on all non-health endpoints.
- Enforce domain isolation in query filters and service scopes.
- Include `domain_id` and, where applicable, `knowledge_base_id` on every persisted business row.
- Support PostgreSQL row-level security for production deployments that require defense-in-depth isolation.
- Include automated cross-domain negative tests in every release gate.
- Store secrets using KMS envelope encryption or external secret manager references.
- Log only redacted prompts, redacted query text, and secret fingerprints.
- Use OWASP ASVS aligned controls for API input validation, output encoding, CSRF where browser sessions exist, and secure headers.
- Maintain complete audit trails for security-sensitive operations.

## 8.3 Privacy

- High-risk PII must be tokenized before LLM prompt calls, LLM completion calls, and external embedding calls.
- Medium-risk PII can be generalized by policy.
- Raw PII must not be written to prompt logs, usage events, or retrieval query logs.
- Embedding logs must record only privacy summary, model, token count, and source IDs, not raw chunk text when policy marks the domain as regulated.
- Deletion and retention policies must be domain configurable.
- Restored PII can only be returned to authorized callers.

## 8.4 Scalability

- Stateless API layer scales horizontally.
- Asynchronous ingestion workers scale independently.
- Vector indexes can be partitioned by domain and knowledge base.
- Graph traversal must enforce depth and result limits.
- Large domains can use separate vector provider namespaces.

## 8.5 Availability

- Target uptime: 99.9 percent for query APIs in production.
- Health checks must distinguish liveness, readiness, and provider degradation.
- Non-required retrieval source failures should degrade, not fail, hybrid retrieval.
- LLM provider outages should use configured fallback when allowed.

## 8.6 Backup and Recovery

| Requirement | Target |
|---|---|
| Metadata DB backup | Daily full backup and point-in-time recovery. |
| RPO | 15 minutes for production metadata. |
| RTO | 4 hours for production service restore. |
| Source object backup | Based on domain retention policy. |
| Reindex recovery | Ability to rebuild vector index from SourceDocument and DocumentChunk records. |

## 8.7 Accessibility

- Admin UI must meet WCAG 2.1 AA.
- All forms must have labels, validation messages, and keyboard navigation.
- Color cannot be the only indicator of status or severity.

## 8.8 Browser and Device Support

- Latest two major versions of Chrome, Edge, Safari, and Firefox.
- Tablet support for review workflows.
- Mobile support for status checks and approvals, not large graph authoring.

# 9. Workflow and State Diagrams

## 9.1 Source Document Lifecycle

| Current State | Action | Actor | Next State | Side Effects |
|---|---|---|---|---|
| `pending` | Start processing | System | `processing` | Creates chunking job. |
| `processing` | Processing succeeds with high confidence | System | `review_required` | Creates chunks, facts, and review tasks. |
| `processing` | Processing fails | System | `failed` | Stores error code and sends notification. |
| `review_required` | Reviewer approves | Reviewer | `published` | Makes chunks, facts, wiki, and graph eligible for retrieval. |
| `review_required` | Reviewer rejects | Reviewer | `archived` | Excludes document from retrieval. |
| `published` | New version uploaded | Curator | `review_required` | Creates new version and marks previous as superseded after approval. |
| `published` | Archive | Domain Admin | `archived` | Removes from default retrieval and emits audit event. |

## 9.2 Ingestion Job Lifecycle

| Current State | Action | Actor | Next State | Side Effects |
|---|---|---|---|---|
| `queued` | Worker claims job | System | `running` | Sets started_at. |
| `running` | Stage progress update | System | `running` | Updates progress_pct and counts. |
| `running` | Stage needs human review | System | `review_required` | Creates review task. |
| `running` | All stages complete | System | `completed` | Publishes event and metrics. |
| `running` | Recoverable failure | System | `failed` | Stores error and retry eligibility. |
| `failed` | Retry | Curator or System | `queued` | Increments retry count. |
| `queued` | Cancel | Curator | `cancelled` | Stops future processing. |

## 9.3 Wiki Article Lifecycle

| Current State | Action | Actor | Next State | Side Effects |
|---|---|---|---|---|
| `draft` | Submit for review | Curator | `in_review` | Notifies reviewers. |
| `in_review` | Approve | Reviewer | `approved` | Records approval. |
| `approved` | Publish | Domain Admin or Reviewer | `published` | Article becomes retrievable. |
| `in_review` | Reject | Reviewer | `rejected` | Captures rejection reason. |
| `published` | Edit | Curator | `draft` | Creates new version. |
| `published` | Archive | Domain Admin | `archived` | Removes from retrieval. |

## 9.4 LLM Provider Lifecycle

| Current State | Action | Actor | Next State | Side Effects |
|---|---|---|---|---|
| `draft` | Submit provider config | Domain Admin | `pending_security_review` | Notifies security admin. |
| `pending_security_review` | Approve | Security Admin | `active` | Provider can be used by patterns. |
| `pending_security_review` | Reject | Security Admin | `draft` | Stores reason. |
| `active` | Suspend | Security Admin | `suspended` | Blocks new calls. |
| `active` | Credential expires | System | `suspended` | Sends rotation notification. |
| `suspended` | Rotate credential and approve | Domain Admin and Security Admin | `active` | Restores provider use. |
| Any | Revoke | Security Admin | `revoked` | Blocks provider permanently unless recreated. |

## 9.5 Reasoning Run Lifecycle

| Current State | Action | Actor | Next State | Side Effects |
|---|---|---|---|---|
| `queued` | Start context assembly | System | `context_assembly` | Creates run audit entry. |
| `context_assembly` | Context complete | System | `reasoning` | Stores redacted context snapshot. |
| `context_assembly` | Required source missing | System | `failed` | Stores source failure details. |
| `reasoning` | Privacy guard blocks | System | `blocked` | Emits critical privacy audit event. |
| `reasoning` | Budget exceeded | System | `cost_exceeded` | Emits budget event. |
| `reasoning` | Chain completes | System | `completed` | Stores result, citations, cost, confidence. |
| `reasoning` | Engine fails | System | `failed` | Stores step failure. |

## 9.6 Knowledge Snapshot Lifecycle

| Current State | Action | Actor | Next State | Side Effects |
|---|---|---|---|---|
| `draft` | Create snapshot | Domain Admin | `draft` | Captures current source, graph, wiki, prompt, policy, and retrieval versions. |
| `draft` | Run quality gates | System | `draft` | Stores quality gate results and creates ReviewTasks for failures. |
| `draft` | Publish with passing gates | Reviewer | `published` | Makes snapshot available to production queries. |
| `draft` | Publish with blocker failures | Reviewer | `draft` | Blocks publication and emits quality event. |
| `published` | Roll back to previous snapshot | Domain Admin | `retired` | Previous snapshot becomes active and audit event is written. |
| `published` | Retire | Domain Admin | `retired` | Snapshot can no longer be selected for new production traffic. |

## 9.7 Legal Hold and Delete Lifecycle

| Current State | Action | Actor | Next State | Side Effects |
|---|---|---|---|---|
| No hold | Create legal hold | Security Admin | `active` | Blocks purge of target records. |
| `active` | Release hold | Security Admin | `released` | Deletion may proceed if policy allows. |
| Source active | Request delete | Domain Admin | Delete pending | Creates audit event and legal hold check. |
| Delete pending | Legal hold exists | System | Delete blocked | Returns `LEGAL_HOLD_ACTIVE`. |
| Delete pending | Delete allowed | System | Soft deleted | Source removed from new snapshots. |
| Soft deleted | Reindex | System | Reindexed | Derived chunks, vectors, graph, facts, and wiki are removed or marked inactive. |

# 10. Notification and Communication Requirements

| Event | Channel | Recipient | Trigger | Template |
|---|---|---|---|---|
| Domain activation blocked | In-app, email | Platform admin, domain admin | Activation checklist incomplete | `Domain {name} cannot be activated: {missing_items}.` |
| Source processing failed | In-app | Curator, domain admin | IngestionJob failed | `Source {title} failed at {stage}: {error_code}.` |
| Source ready for review | In-app | Reviewers | Document enters review_required | `Source {title} is ready for review.` |
| Wiki draft ready | In-app | Reviewers | Wiki compile produces drafts | `{count} wiki drafts are ready in {knowledge_base}.` |
| Provider pending review | In-app, email | Security admin | Provider submitted | `LLM provider {name} requires security review.` |
| Credential rotation due | In-app, email | Domain admin, security admin | Credential expiry within 14 days | `Credential {secret_name} expires on {date}.` |
| PII leakage blocked | In-app, email | Security admin, platform admin | Privacy guard blocks LLM call | `Critical privacy block in {domain}: {pii_types}.` |
| Budget threshold reached | In-app | Domain admin, platform admin | 80 percent monthly budget used | `{domain} has used {percent}% of LLM budget.` |
| Evaluation quality gate failed | In-app | Domain admin, reviewers | Evaluation run below threshold | `Evaluation {name} failed: recall={recall}.` |
| Snapshot publication blocked | In-app | Domain admin, reviewers | Quality gate blocker found | `Snapshot {version} is blocked by {count} quality findings.` |
| Review task overdue | In-app, email | Task owner role | ReviewTask due date passed | `{task_type} review for {target_type} is overdue.` |
| Legal hold blocks delete | In-app, email | Security admin, domain admin | Delete request targets held record | `Delete request for {target_type} is blocked by legal hold.` |

Notification preferences:

- Security-critical notifications cannot be disabled.
- Informational ingestion notifications can be muted per user.
- Email delivery requires verified user email.

# 11. Reporting and Analytics

| Report | Audience | Data Sources | Filters | Refresh |
|---|---|---|---|---|
| Domain Health Dashboard | Platform admin, domain admin | KnowledgeBase, IngestionJob, VectorNamespace, GraphNode, WikiArticle | Domain, status, date | 1 minute |
| Retrieval Quality Dashboard | Domain admin, curator | EvaluationSet, EvaluationRun, RetrievalQuery, FeedbackItem | KB, mode, model, date | On run and hourly |
| LLM Usage and Cost | Platform admin, domain admin, security admin | LLMUsageEvent, ReasoningRun | Domain, provider, model, task, date | 15 minutes |
| Privacy Events | Security admin, auditor | AuditEvent, PolicyRule, ReasoningRun | Domain, PII type, severity | Near real-time |
| Ingestion Operations | Curator, platform admin | IngestionJob, SourceDocument | KB, connector, status | 1 minute |
| Graph Health | Domain admin, curator | GraphNode, GraphEdge, ExtractedFact | Node type, edge type, confidence | 5 minutes |
| Wiki Health | Curator, reviewer | WikiArticle, link reports | Domain area, review status, broken links | 5 minutes |
| Snapshot Release Report | Domain admin, reviewer, developer | KnowledgeSnapshot, EvaluationRun, ReviewTask | KB, version, status | On publish and rollback |
| Retention and Legal Hold Report | Security admin, auditor | LegalHold, AuditEvent, SourceDocument | Domain, target type, status | Daily and query-time |
| Audit Search | Auditor | AuditEvent | Actor, action, target, domain, date | Query-time |

Metric calculations:

- Citation coverage = cited final outputs / total final outputs.
- Hybrid recall lift = hybrid recall minus vector-only recall on the same evaluation set.
- Privacy block rate = blocked LLM calls / attempted LLM calls.
- Ingestion success rate = completed ingestion jobs / all terminal ingestion jobs.
- Average retrieval latency = sum retrieval latency / retrieval request count.

# 12. Migration and Launch Plan

## 12.1 Migration Needs

- Inventory PS-WMS intelligence-service features and classify as platform-level or PS-WMS-specific.
- Migrate reusable tables from `intelligence` and `reasoning_service` concepts into KIS schema with `domain_id` and `knowledge_base_id`.
- Replace PS-WMS `app_id` isolation with explicit Domain and service principal model.
- Create adapters for PS-WMS and compliant-parser that call KIS APIs instead of importing local logic.
- Migrate prompt, graph, wiki, and retrieval tests into domain-neutral KIS tests.
- Preserve PS-WMS endpoint compatibility through adapters until consuming services move to versioned KIS APIs.
- Validate migration with PS-WMS golden sets before production cutover.

## 12.2 Phased Rollout

| Phase | Scope | Exit Criteria |
|---|---|---|
| Phase 0: BRD and Architecture | Finalize requirements, control-plane/data-plane boundary, data model, security model, and MVP scope. | BRD approved and architecture decision record signed off. |
| Phase 1: Secure Core | Domains, memberships, domain templates, KBs, source ingestion, chunking, masked embeddings, vector search, audit, idempotency. | Compliant-parser can query vector search with citations and cross-domain tests pass. |
| Phase 2: Snapshots, Graph, and Wiki | Published snapshots, ontology, facts, graph builder, graph API, wiki compile and review. | Hybrid retrieval uses vector, graph, facts, and wiki from a published snapshot. |
| Phase 3: LLM Governance | Provider config, encrypted credentials, prompt templates, PII boundary for prompts and embeddings, cost controls. | Reasoning pattern executes with no raw high-risk PII sent to external providers. |
| Phase 4: Quality and Admin UI | Admin console, template wizard, snapshot manager, retrieval playground, evaluation sets, quality gates, dashboards. | Domain admin can self-serve a KB, publish a snapshot, and run quality gates. |
| Phase 5: Migration and Production Hardening | HA, backups, rate limits, observability, retention/legal hold, PS-WMS migration adapters. | Production readiness review and PS-WMS golden-set migration gate passed. |

## 12.3 Go-Live Checklist

- Production database migrations applied.
- KMS or secret manager configured.
- At least one platform admin and one security admin provisioned.
- Default privacy policy active.
- External embedding privacy policy active.
- Domain isolation tests passing.
- Optional row-level security enabled or explicitly waived by architecture review.
- Provider governance tests passing.
- Retrieval smoke tests passing for each production knowledge base.
- Snapshot quality gate passing for each production knowledge base.
- Audit log write path verified.
- Idempotency tests passing for mutating APIs.
- Retention, legal hold, and reindex-after-delete workflow verified.
- Backup and restore drill completed.
- Compliant-parser adapter tested against KIS.
- PS-WMS migration plan and backward-compatible adapter approved.

# 13. Glossary

| Term | Definition |
|---|---|
| Domain | A governed business boundary such as police complaints or PS-WMS advisory. |
| Knowledge Base | A domain-scoped collection of sources, chunks, vectors, graph, wiki, prompts, and retrieval policy. |
| Vector Namespace | Isolated vector index configuration for a knowledge base. |
| Ontology | Approved node, edge, and fact type definitions for a domain graph. |
| Extracted Fact | A structured claim derived from a source and available for review, graph construction, and retrieval. |
| Wiki Article | Curated domain knowledge article with citations and review lifecycle. |
| Hybrid Retrieval | Retrieval that combines vector, graph, facts, wiki, and optional structured features. |
| Reasoning Pattern | Versioned configuration that defines context assembly, engine chain, prompt, output schema, and delivery policy. |
| PII | Personally identifiable information including names, contact details, government IDs, financial identifiers, and domain-defined sensitive data. |
| Tokenization | Replacing PII with reversible tokens before LLM prompt calls, LLM completion handling, or external embedding calls. |
| Provider Governance | Controls that define which LLM providers, models, keys, budgets, and fallback rules a domain may use. |
| Citation | Metadata linking a retrieved or generated claim to source document, chunk, graph fact, or wiki article. |
| Shadow Mode | Running a candidate retrieval or reasoning configuration without affecting production output. |
| Control Plane | The KIS layer that manages domains, permissions, templates, policies, credentials, prompts, ontology, snapshots, and audit. |
| Data Plane | The KIS layer that executes ingestion, indexing, graph updates, wiki compilation, retrieval, embedding, and reasoning. |
| Domain Template | A reusable setup package that seeds a domain or knowledge base with policies, ontology, prompts, retrieval profile, and evaluation cases. |
| Knowledge Snapshot | An immutable published version of sources, chunks, indexes, graph, wiki, prompts, policies, and retrieval profile. |
| Quality Gate | Automated checks that must pass before publication, covering retrieval metrics, citations, graph health, facts, and wiki links. |
| Idempotency Key | Client-provided key that prevents duplicate side effects when a mutating request is retried. |
| Legal Hold | A compliance control that prevents deletion or purge of records while an investigation, proceeding, or retention requirement is active. |
| Deletion Request | A governed request to soft-delete or purge a target record and reindex derived knowledge if allowed. |

# 14. Appendices

## 14.1 PS-WMS Reference Features To Preserve

The following reusable patterns from PS-WMS intelligence-service must be preserved and generalized:

- FastAPI service boundary with health, metrics, auth middleware, and API prefix.
- Document ingestion with status lifecycle and background processing.
- Semantic chunking with token budget and overlap.
- OpenAI-compatible embeddings with pgvector storage.
- Hybrid retrieval across vector, graph, facts, and wiki.
- Context assembler with source fan-out, degraded-source tracking, token estimation, and trimming.
- Knowledge graph node and edge upsert with confidence and provenance.
- Extracted facts with structured claims, contradictions, and active status.
- Wiki compilation with concept extraction, article generation, wikilinks, and incremental change detection.
- LLM router with provider fallback and cost tracking.
- Reasoning engine with rules, analytics, LLM chain, prompt registry, pattern registry, traffic split, and approval.
- PII redaction and rehydration around LLM-bound reasoning context.
- Output pipeline with deduplication, fatigue limits, grouping, delivery channels, and audit status.
- Golden-set evaluation tests.

## 14.2 Domain-Specific PS-WMS Concepts To Generalize

| PS-WMS Concept | KIS Generalization |
|---|---|
| `client_id` | Domain entity ID |
| `app_id` | Domain ID and service principal scope |
| WMS node types | Domain ontology node types |
| WMS fact types | Domain ontology fact types |
| Feature service | Optional structured feature provider |
| Advisor NBA | Domain reasoning pattern |
| SEBI hallucination guard | Domain policy rule and output validator |

## 14.3 Quality Checklist

- Database schema can be derived from Section 4 entities and relationships.
- Every functional requirement has a user story, acceptance criteria, business rules, UI behavior, and edge cases.
- Every major screen references entities defined in Section 4.
- API error format and complex endpoint bodies are defined.
- Notifications and reporting requirements are explicit.
- Privacy, provider governance, and domain isolation are first-class requirements.
- DomainTemplate, KnowledgeSnapshot, EvaluationSet, EvaluationRun, FeedbackItem, LLMUsageEvent, ReviewTask, LegalHold, IdempotencyRecord, and DeletionRequest are defined for the new recommendations.
- MVP v1 scope is explicitly separated from target-state platform scope.

## 14.4 Adversarial Evaluation Recommendations Incorporated

| Recommendation | BRD Update |
|---|---|
| Split control plane and data plane. | Added to Executive Summary and Phase 0 architecture scope. |
| Narrow MVP v1. | Added Section 2.5 MVP v1 Service Boundary and updated phased rollout. |
| Protect embeddings, not only prompts. | Added FR-029, NFR privacy updates, and provider requirements. |
| Strengthen domain isolation. | Added row-level security option, `domain_id` requirements, and release-gate tests. |
| Add published snapshots and rollback. | Added KnowledgeSnapshot entity, FR-028, Snapshot UI, workflow, APIs, and launch gates. |
| Add domain templates and guided setup. | Added DomainTemplate entity, FR-027, and Domain Template Wizard. |
| Add idempotency for retry safety. | Added IdempotencyRecord entity, FR-030, API authentication requirement, and go-live checklist item. |
| Add legal hold, retention, and deletion behavior. | Added LegalHold entity, FR-031, workflow, UI, notifications, reports, and go-live checklist item. |
| Add graph/wiki/fact quality gates. | Added FR-033, Quality Gate Review screen, APIs, workflow, and snapshot gate. |
| Add PS-WMS migration compatibility. | Added FR-032, migration needs, phased rollout, and go-live checklist updates. |
