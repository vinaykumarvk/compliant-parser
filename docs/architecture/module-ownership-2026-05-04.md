# Module Ownership and Refactor Boundaries - 2026-05-04

This document records the temporary size exceptions called out by the full-review pass and defines the refactor path for each one.

| Module | Current role | Owner boundary | Refactor target |
| --- | --- | --- | --- |
| `complaint_parsing.py` | Legacy OCR-to-5W1H parser, translation fallback, FIR draft generation | Parser correctness and regression samples | Split into OCR normalization, language/translation, extraction, FIR drafting, and LLM extraction modules. |
| `index.html` | Standalone operator UI served by FastAPI | Operator workflow and BRD UI coverage | Split CSS, API client, state management, and feature views while preserving the no-build static deployment option. |
| `api_v1.py` | IQW v1 route aggregation and request/response models | Versioned API contract | Move auth, cases, analysis, admin, documents, analytics, and reference data into separate routers. |
| `models.py` | ORM schema for IQW entities | Data contract | Split enums, mixins, core case models, analysis models, document models, and admin/audit models. |
| `cases.py` | Case orchestration service | Case lifecycle, documents, tasks, notifications | Split case CRUD, document storage/versioning, CCTNS sync, tasks, and notifications. |

Release rule: future feature work should not grow these files further unless it is paired with extraction into the target module boundary. Regression tests should stay attached to the behavior being moved before each extraction lands.
