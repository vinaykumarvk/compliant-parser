# UI Review Remediation - compliant-parser - 2026-05-05

## Verdict

All six findings from `docs/reviews/ui-review-compliant-parser-2026-05-05.md` have been remediated and smoke tested.

## Finding Closure

| # | Finding | Remediation | Evidence |
|---:|---|---|---|
| 1 | Modal focus management incomplete | Added shared modal controller with focus trap, focus restore, Escape handling, `aria-hidden`, and background inerting across profile, compare history, case form, status transition, and create-user dialogs. | `index.html:6335`, `index.html:6351` |
| 2 | i18n absent across SPA | Added English, Hindi, and Telugu dictionaries, locale persistence, language selector, and migrated login, navigation, cases, senior dashboard, admin/KIS, settings, modal, not-found, validation, and toast strings through `t(key)`. | `index.html:5518`, `index.html:7015` |
| 3 | Design-system drift from inline styles | Removed static and generated `style="..."`/`style='...'` strings from `index.html`; moved layout, status, summary, and generated UI styling into tokenized CSS classes with controlled post-render CSS variables for dynamic metrics. | `index.html:972`, `index.html:8655` |
| 4 | Tables rely on horizontal scroll | Added mobile card-row rendering for senior dashboard and audit tables using `data-label` values while preserving desktop tables. | `index.html:12987`, `index.html:13313` |
| 5 | No invalid-view fallback | Added an explicit not-found view and `navigateTo()` fallback for unknown SPA views with recovery actions to Documents, Cases, and Dashboard. | `index.html:5389`, `index.html:9663` |
| 6 | Login reset/access requests client-only | Added auditable backend support-request endpoints with rate limiting and wired login reset/access actions to create tickets. | `app.py:580`, `app.py:872`, `index.html:7015`, `tests/test_app.py:221` |

## Verification

| Check | Result |
|---|---:|
| `python3 -m unittest discover -s tests -v` | Passed, 344 tests |
| `python3 -m py_compile app.py` | Passed |
| `node -e "... new Function(scripts) ..."` | Passed |
| `rg -n "style=['\\\"]|100vh" index.html` | No matches |
| `curl http://127.0.0.1:8080/health` | Passed |
| `curl -X POST /api/auth/support-request` | Passed, created `SUP-...` ticket |
| `curl -X POST /api/auth/login` with `admin/password123` | Passed |
| Headless Chrome smoke: login, operational locale switch, not-found fallback, profile modal accessibility | Passed |

## Artifact

- `docs/reviews/artifacts/ui-remediation-smoke-1280x800.png`
