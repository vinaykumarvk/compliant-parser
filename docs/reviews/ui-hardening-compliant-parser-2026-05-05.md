# UI Hardening Closure - compliant-parser - 2026-05-05

## Verdict

The post-review hardening items have been taken up.

## Closure

| Item | Status | Evidence |
|---|---:|---|
| Durable login support/access requests | Done | `auth_support_requests` table in `database.py`, idempotent migration in `migrations.py`, database-first endpoint in `app.py` |
| Admin support queue | Done | Admin Support Requests tab in `index.html`; admins can view and move requests to review/resolved |
| Broader operational i18n | Done | Added cases, senior dashboard, admin/KIS/support labels to English/Hindi/Telugu dictionaries |
| Repeatable accessibility/responsive check | Done | `scripts/ui_accessibility_smoke.py` validates login labels, locale switching, not-found fallback, modal focus/ARIA, admin support queue, and 360/768/1280 overflow |

## Verification

| Check | Result |
|---|---:|
| Focused support endpoint tests | Passed |
| `python3 -m py_compile app.py database.py migrations.py scripts/ui_accessibility_smoke.py` | Passed |
| `node -e "... new Function(scripts) ..."` | Passed |
| `rg -n "style=['\\\"]|100vh" index.html` | No matches |
| `python3 scripts/ui_accessibility_smoke.py --url http://127.0.0.1:8080 --username admin --password password123` | Passed |
