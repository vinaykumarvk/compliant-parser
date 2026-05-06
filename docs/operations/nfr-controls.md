# IQW Non-Functional Controls

Date: 2026-05-04

## Deployment Boundary

- Sensitive case data must run in an on-premises or police-approved private cloud boundary.
- OCR and LLM providers are self-hosted-first. Configure `IQW_OCR_PROVIDER=self_hosted` with `IQW_SELF_HOSTED_OCR_URL` and `IQW_LLM_PROVIDER=self_hosted` with `IQW_SELF_HOSTED_LLM_URL` for RFQ-aligned deployments.
- Cloud AI providers are adapter-based fallbacks and must be enabled only after written approval. Production calls to Google Document AI, OpenAI, or Gemini require `EXTERNAL_AI_API_APPROVED=true`, `EXTERNAL_AI_APPROVAL_ID`, and `EXTERNAL_AI_APPROVED_BY`.
- CCTNS, HRMS, DSC, OCR, and legal-section engines are integration adapters with local-safe fallbacks for development.
- On-prem reference artifacts live under `deploy/`: `docker-compose.onprem.yml` covers pgvector Postgres, MinIO, OpenSearch, and Redis; `k8s/iqw-onprem.yaml` covers HA app deployment, HPA, PDB, probes, and network-policy boundaries.
- Document binaries support local development, Google Cloud Storage, and S3-compatible storage such as MinIO through `OBJECT_STORAGE_PROVIDER`.

## Recovery Objectives

- RTO target: 1 hour.
- RPO target: 15 minutes.
- Required controls: point-in-time database recovery, daily full backup, immutable backup copy, and quarterly restore drill.

## Security Controls

- Data at rest: AES-256 or managed equivalent for database, object storage, and backups.
- Data in transit: TLS 1.3 at ingress/load balancer, with TLS 1.2 minimum only for legacy government integrations that cannot support 1.3.
- Key management: HSM/KMS-backed keys with rotation and access audit.
- Audit logs: retained for at least 7 years; application responses expose `retention_years: 7`.

## Performance Targets

- 100 concurrent users: validate with load test before production go-live.
- Non-AI API p95: less than 500 ms.
- OCR p95: less than 5 seconds per page.
- LLM/AI p95: less than 10 seconds.
- AI failed inference rate: less than 1%.
- AI fallback rate: less than 5%.
- GPU utilization: less than 80% sustained for self-hosted models.
- Repeatable smoke evidence: `python scripts/nfr_smoke.py --base-url http://127.0.0.1:8080 --path /health --requests 100 --concurrency 10 --p95-ms 500`.
- Go-live evidence must include health, representative non-AI API, upload/OCR, LLM workflow, and database/object-storage restore drill outputs attached to the release checklist.

## Browser and Accessibility

- Supported browsers: Chrome, Edge, and Firefox 100+.
- Accessibility target: WCAG 2.1 AA.
- Required release checks: keyboard navigation, visible focus states, form labels, color contrast, mobile/tablet layout, and offline queue behavior.
