# Petition Missing Information Assistance Validation - 2026-05-06

## Scope

Validated the phased implementation for petitioner missing-information assistance:

- deterministic English assistance packets from refined English parse output
- packet persistence, review lifecycle, approval, and export
- documents-page assistance packet UI
- petitioner return values, verification, and final acceptance
- original-language translation records with placeholder preservation and semantic QA gates
- checklist, LLM contract validation, and pilot quality reporting primitives

## Automated Checks

| Check | Result |
| --- | --- |
| `python3 -m py_compile app.py database.py migrations.py petition_assistance.py tests/test_app.py tests/test_petition_assistance.py` | Passed |
| Inline `index.html` JavaScript parse via Node `new Function(...)` | Passed |
| `python3 -m pytest tests/test_petition_assistance.py tests/test_app.py tests/test_complaint_parsing.py tests/test_document_generator.py -q` | Passed: 120 tests, 5 subtests |

Warnings observed:

- Google Python client warns Python 3.10 support ends on 2026-10-04.
- Local `requests` dependency warns about urllib3/charset package version mismatch.
- Existing test fake DB helpers emit SQLAlchemy `Select.froms` deprecation warnings.

## Local Smoke

Started the app locally:

```bash
uvicorn app:app --host 127.0.0.1 --port 8010
```

Smoke results:

| Endpoint / Flow | Result |
| --- | --- |
| `GET /` | 200 HTML |
| `GET /health` | 200 JSON |
| `POST /api/auth/login` with configured local admin credentials | 200 |
| Unauthenticated `POST /api/parse` | 401 |
| Authenticated unsupported upload | 400 |
| Authenticated `GET /api/history` | 200 |
| Authenticated `GET /api/rewrite-checklist/questions` | 200 |
| Create assistance packet from existing history record | 201 |
| Create original-language translation record | 201 |
| Save semantic QA override | 200 |
| Approve assistance packet | 200 |
| Export assistance packet | 200 Markdown |

Runtime fix made during smoke:

- Fixed SQLAlchemy row serialization in `app.py` so real `Result.mappings()` rows work in the local runtime, not only in the unit-test fake.

## Residual Risks

- Original-language packet generation currently records an explicit English-only issue when no petition-packet translation provider is configured. Semantic approval is blocked until bilingual review passes or an override is recorded.
- Live OCR/translation parsing was not run in this phase because it depends on external Document AI and translation credentials.
- The local runtime emits a passlib bcrypt version warning, but startup completed and auth worked.

## Verdict

`CONDITIONAL READY` for manual workflow testing on `http://127.0.0.1:8010`.

Full live OCR and real original-language translation still require configured provider credentials.
