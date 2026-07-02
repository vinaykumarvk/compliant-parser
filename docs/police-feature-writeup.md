# Investigation Quality Workbench — Police Feature Write-Up

*A platform for police complaint intake, FIR drafting, and investigation management*

---

## 1. What the Application Is

The **Investigation Quality Workbench (IQW)** — built on the Complaint Parser engine — is a
web platform purpose-built for **Indian police departments**. It takes a raw citizen complaint
(scanned, handwritten, or typed, in English, Hindi, Telugu, or Urdu) and turns it into a
structured, FIR-ready case file. Beyond intake, it manages the full investigation lifecycle from
complaint received through charge sheet, court proceedings, and disposal, while giving senior
command real-time operational visibility.

The application is designed for the police organizational hierarchy: desk operators and **Clerks**,
**Investigating Officers (IO)**, **Station House Officers (SHO)**, **Zone Officers (DCP/ACP)**,
and **Senior Command (Commissioner/JCP)**, plus AI and System administrators.

**Tech stack:** Python 3 / FastAPI backend, async SQLAlchemy 2.0 over PostgreSQL, a single-page
HTML/JavaScript front end, Google Document AI for OCR, multi-provider translation and AI
extraction (Google, OpenAI, Gemini) with fallback, deployed on Google Cloud Run + Cloud SQL.

---

## 2. Police-Related Features

### A. Complaint Intake & OCR
- **Multi-format upload and intelligent OCR.** Accepts PDF, DOCX, TIFF, and common image
  formats, extracting text via Google Document AI including handwriting recognition. Each parse
  carries an OCR confidence rating (High/Medium/Low) and a processing status.
- **OCR cleanup and normalization** strips Unicode artifacts and garbled characters so scanned
  and handwritten complaints become machine-readable.

### B. Multilingual Processing
- **Automatic language detection** across English, Hindi, Telugu, and Urdu using character-range
  heuristics with confidence scoring.
- **Multi-provider translation with fallback** renders non-English complaints into English, with
  an optional refinement pass and **dual-language analysis** that cross-references names, dates,
  and locations against the original to prevent translation distortion. Both original and
  translated text are preserved for audit.

### C. Complaint Analysis (5W+1H)
- **Structured 5W+1H extraction** parses every complaint into *Who* (complainant, victim,
  accused, witnesses), *What* (incident type), *When*, *Where*, *Why*, and *How*.
- **Offence classification** categorizes complaints by crime type (theft, assault, fraud, cyber,
  etc.) using weighted keyword scoring tuned for Indian police complaints, mapping to **BNS, IPC,
  CrPC, BNSS, NDPS, POCSO, and SC/ST Act** frameworks.
- **Gap analysis and completeness scoring** assign each complaint a 0–1 completeness score and
  flag missing or weak fields with severity levels.
- **Confidence scoring with evidence lineage** attaches a confidence level and a quoted source
  snippet to every extracted field, so every output is traceable back to the document.

### D. FIR Draft Generation
- **Automated FIR draft** produces a *Telangana Police — Draft First Information Report* (NCRB
  IIF-I style) from the extracted fields: complaint header, parties, gist of complaint, witnesses,
  evidence schedule, proposed sections, and an officer signature block. Drafts are explicitly
  marked pre-filing pending crime-number registration and judicial approval.
- **BNS/IPC section recommendation** suggests applicable legal sections from the detected offence,
  each with a confidence score and supporting evidence snippet.
- **Jurisdiction mapping** proposes the relevant police station and district from extracted
  location data, against a seeded police-station registry (code, district, zone, city, state).
- **Evidence compilation** assembles referenced evidence items into the FIR evidence schedule.

### E. Case Management & Investigation Lifecycle
- **Case creation** for FIR, Petition, and Suo Motu cases, with **automatic crime-number
  generation** in the Indian `NNNN/YYYY` per-station-per-year format (CCTNS-compliant) and
  enforced uniqueness.
- **A 9-state lifecycle state machine** — Complaint Received → FIR Registered → Under
  Investigation → Charge Sheet Filed → Closure Report Filed → Court Proceedings, with terminal
  states Transferred, Disposed, and Closed (No FIR). Transitions are validated against allowed
  state changes.
- **Stage guidance** lists expected documents and next actions for each stage (e.g. witness
  statements, seizure/arrest memos, medical and FSL reports, CDRs during investigation).
- **Investigating Officer ownership** assigns IOs to cases and restricts access and edits to the
  assigned officer.
- **Statutory deadline tracking** auto-populates CrPC/BNSS deadlines — 60/90-day charge-sheet
  filing, 45-day FSL follow-up, recurring progress reports — and surfaces overdue cases as alerts.

### F. Document Management & Legal Drafting
- **Case document upload with version control** for petitions, FIRs, witness statements, medical
  and FSL reports, seizure/arrest memos, remand notes, and CDRs — with SHA-256 integrity hashes,
  OCR metadata, version history, and version diffing.
- **Legal document generation** from a library of standard templates (FSL forwarding letters,
  Section 63 BSA certificates, arrest memos, remand notes, FIR drafts) with autofill from case
  data, IO editing, **digital signature**, and **DOCX/PDF export**.

### G. Intelligent Investigation Support
- **Automated investigation plan** generates step-by-step guidance from case facts and offence
  type — scene panchnama, witness interviews (Sec 161 CrPC / 180 BNSS), seizure procedures,
  FSL/forensic checklists, CDR requisition, and reporting timelines.
- **Congruence detection** flags contradictions, timeline inconsistencies, role mismatches, and
  medical-vs-narrative discrepancies *between* documents (e.g. FIR vs. witness statement), which
  officers can dismiss with audited reason codes.
- **Quality gate / investigation-readiness assessment** scores a case against a checklist
  (cognizability, parties, incident detail, evidence, witnesses) and classifies trial-risk before
  FIR registration.
- **Judgment analysis** mines court judgments for trial-risk patterns, procedural gaps, and
  lessons that feed the **Knowledge Intelligence Service (KIS)** — a searchable legal knowledge
  base of BNS/IPC sections, procedure SOPs, and investigation pitfalls.

### H. Petition Assistance
- **Missing-information assistance** converts a complaint's gap analysis into a petitioner-facing
  packet with clear placeholders, renders it in the petitioner's language, and captures consent,
  verification, and witness sign-off — with full lineage from every sentence back to its source.

### I. Senior Officer Dashboard & Analytics
- **Command-level operational dashboard** with role-scoped visibility (station / zone / city)
  showing complaint-to-FIR conversion, processing times (median/p75/p95), investigation
  completion, and adoption.
- **Lifecycle funnel and backlog tracking**, **bottleneck detection with configurable alerts**
  (delays, low adoption, stuck cases), and a **non-punitive training-recommendations engine**.

### J. Security, Audit & Privacy
- **Role-based access control** across the police hierarchy, with operator authentication,
  server-side sessions, timing-attack protection, and rate limiting.
- **Comprehensive append-only audit logging** of every action (logins, case/document/AI/export
  events, status transitions) with before/after state — supporting CrPC/BNSS, RTI, and judicial
  audits.
- **PII protection** masks names, addresses, and phone numbers before any external LLM call,
  restores them afterward, and keeps dashboard aggregates name-free. External AI providers are
  **blocked by default** unless written approval metadata is supplied.

---

## 3. Why It Matters for Policing

IQW collapses the manual, paper-heavy path from a citizen's complaint to a registered FIR and a
well-run investigation. It standardizes complaint intake across languages, drafts statutorily
aligned FIRs with the right BNS/IPC sections, enforces the investigation lifecycle and its
statutory deadlines, surfaces contradictions before they reach court, and gives command real-time
oversight — all under strict audit, RBAC, and PII safeguards appropriate for sensitive police data.
