# UI Review - compliant-parser - 2026-05-05

## Verdict

Login-specific verdict: **GO for manual testing**.

App-wide UI release verdict: **NO-GO** until the remaining modal focus-trap and i18n/design-system issues are addressed. The login screen requested in this pass has been upgraded and verified across phone, tablet, desktop, and light/dark themes.

## Scope And Assumptions

- Target: `/Users/n15318/compliant-parser`.
- UI shape: single static SPA in `index.html`, served by FastAPI from `app.py`.
- No `apps/*/src` React app, Tailwind config, shadcn config, or package script surface was found in this repo, so the review was adapted to the existing HTML/CSS/vanilla JS UI.
- PS-WMS reference reviewed: `/Users/n15318/PS-WMS/apps/ops/src/pages/login.tsx`. Relevant patterns adopted: split screen, branded lockup, remember username only, password visibility, loading state, forgot-password panel swap, and theme access on login.

## Implemented In This Pass

| Area | Status | Evidence |
|---|---:|---|
| Full-viewport production login layout | Done | `index.html:390`, `index.html:4078` |
| PS-WMS-inspired split desktop login and stacked responsive layout | Done | `index.html:400`, `index.html:863`, `index.html:884` |
| Branded logo, app name, operational value panel | Done | `index.html:4078`, `index.html:4130` |
| Form autocomplete, labels, inline errors, `aria-invalid`, `aria-describedby` | Done | `index.html:4163`, `index.html:4171`, `index.html:5877` |
| Remember username only | Done | `index.html:5892`, `index.html:5932` |
| Forgot-password in-page panel | Done | `index.html:4190`, `index.html:6057` |
| Password visibility toggle | Done | `index.html:6046` |
| Loading and double-submit prevention | Done | `index.html:5904`, `index.html:6232` |
| Login theme selector | Done | `index.html:4207`, `index.html:9208`, `index.html:9240` |
| Legacy `100vh` removed from case workspace | Done | `index.html:4013` now uses `100dvh` |

## Evidence Artifacts

| Artifact | Result |
|---|---|
| `docs/reviews/artifacts/login-360x800.png` | Phone login form visible first, no horizontal overflow observed |
| `docs/reviews/artifacts/login-768x1024.png` | Tablet login form visible first, overview below |
| `docs/reviews/artifacts/login-1280x800.png` | Desktop split layout, dark theme |
| `docs/reviews/artifacts/login-1280x800-light.png` | Desktop split layout, light theme |

## Command Log

| Command | Result |
|---|---|
| `rg` scans for login, modal, responsive, i18n, route, and inline-style evidence | Executed |
| `node -e "... new Function(scripts) ..."` | Passed, inline script parses |
| `curl http://127.0.0.1:8080/health` | Passed |
| `curl -X POST /api/auth/login` with `admin/password123` | Passed |
| DevTools Protocol screenshot matrix at `360x800`, `768x1024`, `1280x800` | Passed |
| `python3 -m unittest discover -s tests -v` | Passed, 342 tests |
| Automated axe/Playwright accessibility scan | Not executed, packages are not installed in this repo |

## UI Inventory

| App | Route/View | Screen Source | CSS Source | Design System | i18n Status | Theme Status |
|---|---|---|---|---|---|---|
| compliant-parser | Login | `index.html` | `index.html` | Custom CSS tokens | Missing | Good |
| compliant-parser | Documents list/detail | `index.html` | `index.html` | Custom CSS tokens plus inline styles | Missing | Partial |
| compliant-parser | Compare | `index.html` | `index.html` | Custom CSS tokens plus inline styles | Missing | Partial |
| compliant-parser | Cases/new/detail | `index.html` | `index.html` | Custom CSS tokens plus inline styles | Missing | Partial |
| compliant-parser | Quality Check | `index.html` | `index.html` | Custom CSS tokens plus inline styles | Missing | Partial |
| compliant-parser | Doc Gen | `index.html` | `index.html` | Custom CSS tokens plus inline styles | Missing | Partial |
| compliant-parser | Senior Dashboard | `index.html` | `index.html` | Custom CSS tokens plus inline styles | Missing | Partial |
| compliant-parser | Admin/KIS | `index.html` | `index.html` | Custom CSS tokens plus inline styles | Missing | Partial |

## Navigation And State Inventory

| Check | Status | Evidence |
|---|---:|---|
| Mobile sidebar exists | Present | `index.html:1105`, `index.html:4219`, `index.html:4336` |
| Hamburger toggle exists | Present | `index.html:4219`, `index.html:9452` |
| Menu icons on main nav | Present | `index.html:4341` through `index.html:4366` |
| Sidebar overlay closes on click and Escape | Present | `index.html:9456`, `index.html:9516` |
| Toast live region | Present | `index.html:4077` |
| Empty states | Partial | Some lists use empty text, but this is not consistent across all generated table/list paths |
| Loading states | Partial | Login and several flows have loading states; not every data-fetching view has skeleton/loading affordances |
| Client-side 404 view | Missing | SPA has view switching in `navigateTo()` but no not-found view for unknown UI states |

## Login Completeness

| Feature | Status | Notes |
|---|---:|---|
| Branded logo + app name | Present | Desktop hero plus compact stacked-layout brand |
| Password visibility toggle | Present | Text toggle with `aria-label`; icon can be added later if an icon library is introduced |
| Remember me | Present | Stores username only in `localStorage` |
| Forgot password flow | Present | In-page panel swap, client-side support notice |
| Loading state on submit | Present | Button spinner, busy state, disabled state |
| Error display with aria-live | Present | Alert banner and field-level messages |
| Theme selector on login | Present | Optgroup select uses all defined theme options |
| Dark mode support | Present | Dark screenshot verified |
| Light mode support | Present | Light screenshot verified |
| `100dvh` viewport | Present | Login uses `100dvh`; legacy `100vh` removed |
| Touch targets >= 44px | Present for login | Inputs and buttons are at least 2.75rem |
| Responsive 360/768/1280 | Present | Screenshot matrix captured |
| Autocomplete attributes | Present | Username/password fields use browser/password-manager attributes |
| Redirect to intended page | Partial | Login returns to default workspace, not a stored intended deep link |
| i18n | Missing | Static English strings only |

## Findings

### 1. Modal focus management is incomplete

- Severity: P1
- Confidence: High
- Status: Confirmed
- Risk Score: 12
- Evidence: compare/profile overlays at `index.html:5066` and `index.html:5076` lack `role="dialog"`/`aria-modal`; IQW modals have dialog semantics at `index.html:5113`, `index.html:5123`, and `index.html:5144`, but no reusable focus trap was found. Escape handlers exist at `index.html:9087`, `index.html:9343`, and `index.html:12298`.
- What: Add a shared modal controller that traps focus, restores focus on close, applies `inert`/`aria-hidden` to the background, and handles Escape consistently.
- Where: compare history modal, profile modal, case form modal, status transition modal, create user modal.
- How: Create one `openModal(modal, initialFocus)` and `closeModal(modal, returnFocus)` helper and route all modal open/close paths through it.
- Verify: Keyboard-only tab should never leave the active modal; Escape closes; focus returns to the opener.

### 2. i18n is absent across the SPA

- Severity: P1
- Confidence: High
- Status: Confirmed
- Risk Score: 12
- Evidence: `index.html:2` is hardcoded `lang="en"` and user-visible strings are embedded throughout the single HTML file, including login and core workflows.
- What: Introduce a small translation layer before adding more operational UI.
- Where: login, navigation, cases, senior dashboard, admin/KIS, validation and toast text.
- How: Define message keys and locale dictionaries for at least English, Hindi, and Telugu for policing workflows; route every visible string through `t(key)`.
- Verify: Toggle locale and confirm login, nav, form validation, empty states, and dashboard text update.

### 3. Design-system drift remains outside the login screen

- Severity: P2
- Confidence: High
- Status: Confirmed
- Risk Score: 8
- Evidence: CSS tokens exist at the top of `index.html`, but many inline styles remain in markup and generated HTML, for example `index.html:4223`, `index.html:4477`, `index.html:4619`, `index.html:4701`, `index.html:10751`, and `index.html:12276`.
- What: Reduce inline styles and generated style strings.
- Where: case details, document viewer, quality findings, senior dashboard, audit table.
- How: Move repeated inline styles into tokenized utility classes and component-level CSS selectors.
- Verify: `rg -n 'style="' index.html` count should materially drop and dark/light screenshots should remain stable.

### 4. Table/list responsiveness is still mostly horizontal-scroll based

- Severity: P2
- Confidence: Medium
- Status: Partially Confirmed
- Risk Score: 6
- Evidence: table wrappers rely on `overflow-x: auto` at `index.html:3896` and `index.html:3912`; audit/senior tables are defined at `index.html:4880`, `index.html:4893`, `index.html:4906`, and `index.html:5057`.
- What: Improve dense operational tables for phone and tablet.
- Where: senior dashboard, audit table, admin lists.
- How: Keep desktop tables, but add mobile card rows or priority columns with expandable detail.
- Verify: At 360px, no row action or key value should require awkward horizontal panning.

### 5. SPA has no explicit not-found or invalid-view state

- Severity: P2
- Confidence: Medium
- Status: Confirmed
- Risk Score: 6
- Evidence: UI navigation is centralized in `navigateTo()` at `index.html:8590`, but no dedicated not-found/unknown-view page was found.
- What: Add an intentional unknown-view fallback.
- Where: `navigateTo()` and app shell view registry.
- How: Define a `not-found` view with recovery actions to Documents, Cases, and Dashboard.
- Verify: Calling `navigateTo('unknown')` should show the fallback and not leave the screen blank.

### 6. Login reset and access-request flows are client-side only

- Severity: P3
- Confidence: High
- Status: Confirmed
- Risk Score: 3
- Evidence: forgot/access handlers show status messages at `index.html:6077` and `index.html:6095`; no backend reset request was verified.
- What: Wire reset/access requests to auditable backend tickets.
- Where: login forgot-password and request-access actions.
- How: Add endpoints that create admin-visible requests with rate limiting and audit logs.
- Verify: Submit request, confirm ticket appears for admin without exposing sensitive data.

## QA Gate Scorecard

| Gate | Result | Notes |
|---|---:|---|
| Login production readiness | PASS | Implemented and screenshot verified |
| Mobile login | PASS | 360px and 768px form-first layout verified |
| Dark/light theme login | PASS | Both snapshots captured |
| Keyboard login basics | PASS | Native form, autofocus, labels, visible focus styles |
| Modal accessibility | FAIL | Focus trap and background inerting missing |
| i18n readiness | FAIL | Static English strings |
| App-wide design-system consistency | PARTIAL | Token base exists; inline/generator styles remain |
| Loading/error/empty states | PARTIAL | Good in some flows, uneven app-wide |
| App-wide release readiness | FAIL | Blocking items above |

## BRD/UI Traceability

| Requirement | Status | Evidence |
|---|---:|---|
| Production-grade secure login | Covered | `index.html:4078`, `index.html:4130`, screenshots |
| AI-policing app identity visible at login | Covered | `index.html:4078`, `index.html:4130` |
| Editable, officer-reviewed AI positioning | Covered | Hero/trust copy at `index.html:4098`, `index.html:4120` |
| Role/station-aware operational app shell | Existing | Sidebar/admin/dashboard nav at `index.html:4336` |
| Senior officer dashboard visibility | Existing, not fully re-reviewed here | `index.html:4806` and related senior dashboard code |
| Multilingual policing UX | Gap | No translation layer in UI |
| Accessibility-complete dialogs | Gap | Findings 1 |

## Prioritized Backlog

1. Add shared modal focus trap and background inerting.
2. Add i18n infrastructure and migrate login/navigation first.
3. Convert repeated inline styles into tokenized classes.
4. Add mobile card/table presentation for senior dashboard and audit views.
5. Add explicit not-found/invalid-view fallback.
6. Wire forgot-password/access request to backend audit/ticket flows.

## Quick Wins

- Add `role="dialog"` and `aria-modal="true"` to compare/profile modal cards while implementing the full focus trap.
- Convert the highest-repeat generated inline button styles into `.btn.btn-compact`.
- Add a `navigateTo()` default fallback branch.
- Capture one keyboard-only smoke script/checklist for login after each UI change.
