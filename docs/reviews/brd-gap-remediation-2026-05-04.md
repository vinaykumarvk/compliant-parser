# BRD Gap Remediation Log

Date: 2026-05-04
Source audit: `docs/reviews/brd-coverage-hcp-iqw-brd-v1-2026-05-04.md`

## Remediated Areas

- FR-001: Case intake now enforces exact crime/petition formats, duplicate crime-number checks per police station/year, CCTNS sync status, retry endpoint, retry UI, and 3-attempt adapter policy.
- FR-002: Case payload/UI now supports secondary offence IDs and displays offence status in the case header.
- FR-003/FR-012: Upload now supports PDF/JPEG/PNG/DOCX/TXT, 50 MB limit, 20-file bulk upload, document-type validation, SHA-256 storage, IndexedDB offline queue, auto-sync, failed reason, and manual retry.
- FR-004/FR-005: Timeline has sort toggle and click navigation; documents have version history/diff; tasks show source, overdue state, reminders, completion, and snooze.
- FR-006: Quality checks now include citation objects for every finding, persist analysis/citations for uploaded documents, use KB checklists when available, show the generic checklist note, and report latency.
- FR-007/FR-009: Section recommendation and investigation-plan APIs now return confidence, reasoning, ingredients, missing facts, alternatives, disclaimer, editable plan steps, evidence, documents, and deadline countdowns.
- FR-008: Congruence detection auto-runs after upload for supported pairs, creates typed alerts, sends notifications, and supports dismissal with feedback to refinement.
- FR-010/FR-018: Document generation now autofills from case data, includes Google/Meta platform notices, exposes missing-field prompts, supports DOCX/PDF export, DSC signing endpoint/UI, certificate details, and read-only signed docs.
- FR-011: OCR review endpoint returns original/extracted/translation panes, language detection, segment confidence, mandatory review flag, acknowledgement status, and 5-second target metadata.
- FR-013/FR-014: AI Admin queue, correction-to-KB draft workflow, KB draft/staging/production promotion, validation, version metadata, and rollback endpoints are implemented.
- FR-015/FR-016: Judgment upload/analysis, proposed checklist updates, analytics summary, scoped IO/Admin metrics, filters, and monthly PDF export are implemented.
- FR-017/FR-019/FR-020: HRMS adapter/profile sync, exact login/lockout messages, session-aware audit entries, 7-year retention evidence, and real hash recomputation with admin alert are implemented.

## Remaining External Validation

- Production HRMS, CCTNS, DSC, self-hosted OCR/LLM, HSM/KMS, backup, DR, TLS, and load-test evidence still require environment-specific validation and credentials.
- Local automated tests verify application behavior, but they do not prove government-system connectivity or infrastructure SLOs.
