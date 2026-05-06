# Petition Missing Information Assistance - Adversarial Council Transcript

**Generated:** 2026-05-06 08:25:57
**BRD reviewed:** `docs/petition-rewrite-assistance-brd.md`
**Verdict:** GO WITH MODIFICATIONS

## Chairman Synthesis
Recommendation: GO WITH MODIFICATIONS

The concept is worth pursuing, but the BRD should not frame v1 as "rewriting a petition" end to end. It should be narrowed to a controlled Missing Information Assistance Packet that helps the petitioner supply gaps while preserving authorship, evidence integrity, and officer accountability.

Top incorporated observations:
1. The feature name and story create trust risk: police should not appear to rewrite a citizen's complaint.
2. Authorship and evidentiary legitimacy are the core risks, not just LLM quality.
3. V1 should be narrowed to an English packet generated from existing refined English text, 5W+1H gaps, and checklist gaps.
4. Every generated sentence, placeholder, and prompt must have lineage to source text or a named missing-information gap.
5. Translation back to Telugu/Hindi/Urdu needs explicit semantic validation and petitioner approval before it is operationally trusted.

Strongest argument: the system is acceptable only if it preserves factual truth and petitioner authorship. The AI may structure missing-information prompts, but it must not become the author of the complaint, resolve contradictions, infer facts, choose legal sections, or silently alter meaning across languages.

Biggest blind spot: the original BRD under-specified operational accountability: who owns each word at each stage, how corrections/refusals are captured, how misuse is monitored, and what state transition proves the final text was petitioner-supplied, officer-reviewed, and petitioner-verified.

Required BRD changes: rename/reframe the feature, add petitioner consent and verification, require source lineage, add semantic translation QA, define the JSON prompt contract, add refusal/correction rights, narrow Phase 1, and introduce pilot quality thresholds.

First implementation step: build the Phase 1 deterministic packet MVP from existing parse_records by consuming refined English plus detected gaps, generating an English officer-reviewable packet with protected placeholders and source/gap lineage, then supporting export and review status capture.

## Advisor Responses
### Advisor A - Outsider

This BRD is technically thorough, but the product story is hard to trust on first read. "Petition Rewrite Assistance" sounds like the police are rewriting a citizen's complaint, which is sensitive. The document says it preserves facts and avoids FIR/legal decisions, but the user-facing language needs sharper framing: this is a "missing information assistance packet," not a rewritten complaint unless the petitioner explicitly verifies and signs the final version.

The petitioner/officer boundary is the biggest ambiguity. The petitioner has no system access, handwrites or dictates values, and officers capture those values. That creates a trust gap: who owns the final wording, the petitioner or the officer? If an officer edits the generated draft before printing, then later captures returned values, the system needs a very visible chain of "AI suggested / officer edited / petitioner supplied / officer accepted." Hashes and audit tables help internally, but the petitioner also needs a readable change/verification page.

There is heavy internal jargon: `5W+1H`, "gap findings," "placeholder integrity," "accepted_unknown," "refined English translation," "bilingual-approved." These may be fine in APIs, but front-desk workflows need simpler terms like "missing details," "needs confirmation," and "petitioner-added answer."

A hidden assumption is that translating from original language to refined English, rewriting in English, then translating back will preserve legal nuance. That is risky, especially for Telugu, Hindi, and Urdu complaints. The BRD requires placeholder preservation but says much less about meaning preservation.

The workflow is also ambitious for v1: generation, officer review, multilingual translation, PDF/DOCX export, return capture, acceptance, dashboards, checklist administration, audit, and analytics. A narrower launch around English draft plus printed missing-details checklist may be easier to explain, train, and defend.

### Advisor B - Proponent

As Proponent: yes, the BRD is strong enough to guide implementation. Its strongest quality is that it turns an existing ADS Complaint Analyser pipeline into a closed-loop petitioner remediation workflow: OCR/refined English -> 5W+1H/checklist gaps -> inline placeholders -> officer-reviewed bilingual packet -> returned values -> accepted final petition. That is implementation-grade framing, not just product aspiration.

The advantage is clear operational leverage. It reduces repeated counter explanations, standardizes missing-fact guidance, preserves petitioner facts, and supports Telugu/Hindi/Urdu accessibility without pretending the system can make legal decisions. Its defensibility is also unusually strong: SHA hashes, prompt/checklist versioning, protected placeholder tokens, role-scoped approval, audit events, immutable history, and explicit anti-fabrication rules all make the feature safer for a police intake context.

Timing is favorable because the platform already has the hard primitives: parsing, refined English translation, 5W+1H gap analysis, multilingual handling, history, and document generation. This BRD correctly treats rewrite assistance as an extension of those capabilities rather than a new standalone system.

Concrete improvements would make it even stronger: add one full sample rewrite packet in English plus Telugu/Hindi/Urdu to remove ambiguity; define the exact JSON schema for LLM rewrite output; specify deterministic placeholder anchoring and deduplication thresholds; add a translation QA rubric for named entities, dates, legal terms, and Urdu RTL rendering; clarify PII redaction rules before model calls; and resolve the `accepted_unknown` / `needs_follow_up` status mentioned in FR-009 against the current placeholder enum. I would also add an end-to-end acceptance test matrix mapped to each rollout phase.

Bottom line: the BRD is implementable and well aligned with the product. It needs tightening at the prompt contract, QA, and state-enum edges, but its core architecture is sound.

### Advisor C - Executor

The BRD is not implementation-ready as one release. It is implementation-ready only if cut to Phase 1: English rewrite packet from an existing `parse_records` row using `text.refined_english_translation` plus current `gaps`. The repo already has the useful seams: `parse_records` JSONB history, refined English output, session/JWT auth, audit infrastructure, and document export code. Use those first.

Build first: create a deterministic rewrite MVP that converts existing 5W+1H missing fields into protected placeholders, generates an English petition draft, lets an officer edit/review, and exports/prints it. Do not start with checklist admin, multilingual round-trip translation, return capture, dashboards, or SLA tasks.

Immediate DB: add only `petition_rewrite_requests`, `petition_placeholders`, `generated_petition_drafts`, and `rewrite_audit_events`. Defer `ChecklistQuestion`, `ChecklistEvaluation`, translations, packets, review tasks, and analytics tables until the workflow proves useful.

Immediate API: `POST /api/rewrite-requests`, `GET /api/rewrite-requests/{id}`, `PATCH /api/rewrite-requests/{id}/drafts/{draft_id}`, `POST /api/rewrite-requests/{id}/approve`, and a basic export endpoint. Reuse existing auth patterns and standard API error shape.

Immediate UI: add "Rewrite Petition" from history/document detail, then a compact review screen with source refined English, gap list, editable English draft, validation summary, approve/export actions.

Main risks: LLM output can omit or mutate placeholders, translation preservation across Telugu/Hindi/Urdu is nontrivial, Urdu PDF rendering is risky, and the BRD's RBAC/workflow assumes more mature station-scoped permissions than the current browser-session path provides.

Monday morning, May 11, 2026: implement the Phase 1 schema and endpoint contracts, seed no checklist tables, write placeholder integrity tests first, then wire one UI path from a saved parse record to printable English draft.

### Advisor D - Contrarian

The BRD is implementation-rich, but the fatal flaw is authorship and evidentiary legitimacy. It treats the rewritten packet as "petitioner-facing guidance," then lets the accepted rewrite become downstream petition text. That creates a procedural risk: the state may effectively reframe a citizen's complaint, translate it through English, insert structure and omissions, then later rely on it as if it were petitioner-authored.

The highest-risk path is: original Telugu/Hindi/Urdu petition -> OCR -> refined English -> AI rewrite -> translated original-language draft -> officer captures returned values -> accepted final petition. Every step can drift meaning. Placeholder integrity only proves tokens survived, not that translated prose preserves legal/factual nuance. A petitioner may sign or complete a document they perceive as police-approved, not as their own verified statement.

To make this bulletproof, the BRD needs hard gates:

1. Add explicit petitioner consent and authorship controls before issue and before acceptance. The packet must say, in English and original language, that it is AI/officer-assisted guidance and is not the petitioner's complaint unless personally verified and signed.

2. Require a petitioner verification block for the final accepted petition, not just an officer confirmation modal. If digital signature is out of scope, mandate wet signature capture metadata: signed date, officer witness, language used, and scanned signed packet link.

3. Add semantic translation validation, not only placeholder validation. For Telugu/Hindi/Urdu, require bilingual officer approval or back-translation comparison before bilingual approval.

4. Preserve evidence lineage: final text must show which sentences came from original refined text, officer edits, AI rewrite, translation, and petitioner-returned values. Hashes alone are not enough for courtroom or complaint-dispute review.

5. Move contradiction detection earlier. Any rewrite that softens, strengthens, omits uncertainty, changes chronology, or converts "unknown" into a forced blank should block approval.

Verdict: strong enough as a technical design, not yet strong enough as a police intake BRD. It needs petitioner consent, authorship, semantic translation, and evidentiary lineage requirements before implementation.

### Advisor E - First Principles

The BRD is directionally strong, but it slightly overstates the product: the core problem is not "rewrite petitions." It is reducing intake ambiguity by converting parser-detected missing facts into petitioner-actionable prompts, in a language the petitioner can understand, while preserving the original complaint's factual truth. The rewrite is only valuable if it remains a controlled container for missing-information collection.

Minimum valuable intervention: generate an officer-reviewed packet from refined English plus existing 5W+1H gaps, with source-linked placeholders, petitioner instructions, and original-language rendering. Everything else, including dashboards, checklist admin versioning, return-value merge, SLA reporting, and DOCX/PDF fallbacks, can follow. Phase 1 should prove: "Does this packet help a petitioner supply missing facts without the system adding facts?"

What must remain human-controlled: approval before issuance, legal sufficiency, sensitive-category routing, final acceptance of returned values, contradiction handling, and any decision that a fact is "mandatory" for a specific offence type. The BRD says this in pieces, but should make human control the central safety model rather than a workflow step.

What should not be automated: FIR registration, offence/legal section selection, invented accused/witness/evidence details, resolving contradictions, silently translating legally sensitive text, or treating "unknown" as a completed answer without officer judgment. Also avoid auto-polishing away uncertainty. If the original says "around 8 PM," the draft must not become "8:00 PM."

Verdict: strong enough to guide a scoped pilot, not yet strong enough for full implementation. The biggest missing requirement is traceability: every generated sentence and placeholder should map back to refined English, OCR/original text, or a named gap. Without that, officer review becomes subjective proofreading instead of verification. The BRD should narrow v1 around placeholder integrity, source preservation, translation review, and auditability before building the larger lifecycle.

## Anonymous Peer Review
### Peer Reviewer 1

Strongest: Response D. It identifies authorship, consent, evidentiary legitimacy, and factual drift across OCR, translation, AI rewrite, officer edits, and petitioner verification. Biggest blind spot: Response B is technically useful but too trusting of hashes, audit logs, and placeholder protection. What all responses missed: operational misuse incentives; the BRD needs refusal rights, petitioner copy/appeal process, supervisory sampling, misuse monitoring, and metrics that do not reward faster acceptance over factual fidelity.

### Peer Reviewer 2

Strongest: D. It identifies the highest-stakes failure mode: authorship and evidentiary legitimacy. Biggest blind spot: B optimizes the machinery before proving the process is acceptable. What all responses missed: real-world validation with measurable failure thresholds for semantic drift, fabricated/unsupported facts, petitioner comprehension, withdrawal/correction, officer override patterns, language-specific QA, and legal acceptability.

### Peer Reviewer 3

Strongest response: D. It reframes the BRD around legitimacy, consent, verification, signature state, and lineage. Biggest blind spot: B is too accepting of the BRD's premise and treats safeguards as engineering controls when the core risk is institutional power and legal meaning. What all responses missed: operational accountability after launch, including who can use the tool, supervision, reviewable audit events, dispute/retraction, misuse detection, and proof of fairness.

### Peer Reviewer 4

Strongest: E. It reframes the feature around helping a human produce a defensible, source-grounded filing. Source-linked traceability for every generated sentence is the strongest implementable control. Biggest blind spot: B is too optimistic. What all responses missed: post-generation review and accountability, including reviewer qualifications, approval/rejection records, edit audit, and proof the petitioner knowingly accepted final text.

### Peer Reviewer 5

Strongest: E. It challenges the core product framing and keeps the feature bounded as missing-fact collection plus source-grounded drafting. Biggest blind spot: C assumes a narrow deterministic v1 is automatically safer. What all responses missed: explicit review workflow and accountability model with a state machine covering draft, source-check required, petitioner review, officer review, final approval, and export.

## Observations Incorporated Into BRD
- **Product framing:** Renamed/reframed the BRD to Petition Missing Information Assistance and clarified that generated text is assistance, not a police-authored complaint.
- **Consent and authorship:** Added petitioner consent, refusal/correction rights, verification language, signature/witness metadata, signed packet link, and copy-provided tracking.
- **Source lineage:** Added SourceLineageMap entity, lineage review screen, lineage API, unsupported fact gate, and final accepted text provenance.
- **Semantic translation QA:** Added bilingual/back-translation validation for Telugu/Hindi/Urdu, semantic drift checks, Urdu RTL rendering requirements, and translation QA rubric.
- **Contradiction controls:** Added checks for softening, strengthening, omitting uncertainty, chronology changes, unsupported facts, and forced blanks.
- **Pilot governance:** Added RewritePilotEvaluation, pilot quality report, misuse monitoring, and rollout thresholds.
- **Phase narrowing:** Reworked rollout so Phase 1 proves a controlled English packet with source lineage before multilingual return capture and dashboards.
- **Prompt contract:** Added exact LLM output JSON schema and deterministic placeholder validation requirements.
