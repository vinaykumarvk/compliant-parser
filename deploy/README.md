# IQW Deployment Artifacts

These artifacts cover the private-cloud/on-prem deployment target called out by the BRD/RFQ.

## Local On-Prem Stack

Use `docker-compose.onprem.yml` to validate the runtime boundary with pgvector Postgres, MinIO, OpenSearch, Redis, self-hosted OCR, and self-hosted LLM endpoints:

```bash
APP_ADMIN_PASSWORD=change-me \
APP_SESSION_SECRET=replace-with-a-long-random-secret \
JWT_SECRET_KEY=replace-with-a-separate-long-random-secret \
docker compose -f deploy/docker-compose.onprem.yml up --build
```

The compose file intentionally keeps OCR and LLM as externally supplied gateway URLs so model deployments can be backed by vLLM/TGI or an agency-approved inference endpoint.

## Kubernetes

`k8s/iqw-onprem.yaml` provides the application layer for a high-availability deployment:

- 3 replicas, HPA, PDB, readiness/liveness probes.
- non-root container, dropped Linux capabilities, read-only root filesystem.
- private service dependencies through ConfigMap/Secret.
- egress restricted to database, Redis, MinIO, OpenSearch, OCR/LLM, and HTTPS integration paths.

Replace image tags and Secret values before applying:

```bash
kubectl apply -f deploy/k8s/iqw-onprem.yaml
```

## NFR Evidence

Run a repeatable p95/error-rate smoke:

```bash
python scripts/nfr_smoke.py --base-url http://127.0.0.1:8080 --path /health --requests 100 --concurrency 10 --p95-ms 500
```

For go-live, run the same script against authenticated non-AI endpoints, plus OCR and LLM gateway-specific tests sized to the RFQ concurrency target.
