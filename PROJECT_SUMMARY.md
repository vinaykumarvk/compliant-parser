# ADS Complaint Analyser — Project Summary

> **Intelligent Police Complaint Parsing & FIR Drafting Platform**

---

## Table of Contents

1. [Overview](#overview)
2. [Main Features](#main-features)
   - [Document Ingestion & OCR](#document-ingestion--ocr)
   - [Multilingual Processing](#multilingual-processing)
   - [Complaint Analysis & Extraction](#complaint-analysis--extraction)
   - [FIR Draft Generation](#fir-draft-generation)
   - [Case History & Records Management](#case-history--records-management)
   - [User Interface & Experience](#user-interface--experience)
   - [User Management & Security](#user-management--security)
   - [System Health & Monitoring](#system-health--monitoring)
3. [Technical Architecture](#technical-architecture)
4. [Benefits for the Police Department](#benefits-for-the-police-department)

---

## Overview

**ADS Complaint Analyser** is a web-based platform purpose-built for Indian police departments to digitize, analyse, and structure citizen complaint documents. The system ingests complaint files — including scanned handwritten documents in Hindi and Telugu — and automatically extracts the critical **5W+1H** facts (Who, What, When, Where, Why, How) needed to initiate a First Information Report (FIR).

Built on a modern, cloud-native stack and deployed as a fully managed service on Google Cloud, the application combines Google Document AI for optical character recognition, multi-provider language translation, and optional AI-guided extraction powered by large language models. The result is a significant reduction in the manual effort required to process, translate, and classify incoming complaints — enabling front-desk officers and investigation teams to focus on action rather than paperwork.

The platform is designed for police station operators, desk officers, investigating officers, and departmental leadership who need fast, reliable, and auditable conversion of raw complaint documents into structured, actionable intelligence.

---

## Main Features

### Document Ingestion & OCR

| Feature | Description |
|---------|-------------|
| Multi-format upload | Accepts PDF, DOCX, TIFF, PNG, JPEG, WEBP, BMP, and GIF complaint documents in a single unified workflow. |
| Intelligent OCR | Leverages Google Document AI to extract text from both printed and handwritten documents with high accuracy. |
| OCR noise cleanup | Automatically normalizes Unicode artefacts, removes control characters, collapses garbled punctuation, and filters stray Latin fragments from Indic scripts. |
| File size governance | Configurable upload size limits (default 15 MB) with MIME-type validation to reject unsupported or malicious files. |

### Multilingual Processing

| Feature | Description |
|---------|-------------|
| Automatic language detection | Identifies English, Hindi, and Telugu documents using character-range heuristics with confidence scoring. |
| Multi-provider translation | Translates non-English complaints to English via Google Cloud Translation, OpenAI GPT, or Google Gemini — with automatic fallback across providers. |
| Dual-language analysis | Processes both the original-language text and its English translation in parallel, cross-referencing names, dates, and locations to prevent translation distortion. |
| Original text preservation | Retains and displays the original OCR text alongside the English translation for officer verification. |

### Complaint Analysis & Extraction

| Feature | Description |
|---------|-------------|
| 5W+1H structured extraction | Parses every complaint into Who (complainant, victim, accused, witnesses), What (incident type), When (date and time), Where (location), Why (motive), and How (method). |
| Heuristic pattern matching | Rule-based extraction engine that identifies people, dates, locations, and incident types using keyword scoring and regex patterns tuned for Indian police complaints. |
| AI-guided extraction | Optional large-language-model layer (OpenAI GPT) that applies few-shot, question-guided prompts with confidence scoring and mandatory evidence snippets. |
| Incident classification | Automatically categorises complaints by offence type (theft, assault, fraud, cyber crime, arson, traffic accident, and more) using weighted keyword analysis. |
| Gap analysis | Calculates a completeness score for every parsed complaint, flags missing or uncertain fields, and generates a plain-language summary of information gaps. |
| Confidence scoring | Each extracted field carries a confidence level (high, medium, low) with supporting evidence quoted directly from the source document. |

### FIR Draft Generation

| Feature | Description |
|---------|-------------|
| Automated FIR narrative | Generates a structured First Information Report draft from the extracted 5W+1H fields, ready for officer review and filing. |
| BNS section proposal | Suggests applicable Bharatiya Nyaya Sanhita (BNS) sections based on the detected nature of offence. |
| Jurisdiction mapping | Proposes the relevant police station and district based on extracted location data. |
| Evidence compilation | Collects and lists supporting evidence items referenced in the complaint for inclusion in the FIR. |

### Case History & Records Management

| Feature | Description |
|---------|-------------|
| Persistent parse history | Every parsed complaint is stored in a PostgreSQL database with full metadata, the original file bytes, and the complete structured output. |
| History browsing | Browse all previously parsed complaints with sortable metadata — file name, size, detected language, completeness score, and parse date. |
| Record retrieval | Load any historical record to review its full parsed output, re-examine extracted fields, or download the original uploaded file. |
| Compare mode | Side-by-side comparison of two complaints (a fresh upload against a saved record) to identify patterns or corroborate information across cases. |
| Record management | Delete individual records or clear the entire history with confirmation safeguards. |

### User Interface & Experience

| Feature | Description |
|---------|-------------|
| Single-page web application | A responsive, self-contained interface served directly from the backend — no separate frontend build or deployment required. |
| Multiple result views | Switch between a JSON editor (full raw output), a narrative summary view (with gap highlights), and a structured table view (5W+1H grid). |
| Real-time progress streaming | Server-Sent Events deliver live progress updates during document parsing — OCR status, translation progress, and extraction steps are shown in real time. |
| Mobile-responsive layout | Hybrid design optimised for both desktop and mobile devices, ensuring field officers can use the system from tablets or phones. |
| Theme support | Light and dark display themes (including Tokyo Night and Dracula palettes) for comfortable use across different working environments. |
| Document filter chips | Multi-select filter controls on the history list allow quick narrowing by language, completeness, or document type. |

### User Management & Security

| Feature | Description |
|---------|-------------|
| Authenticated access | Operator login with username and password, enforced on all sensitive endpoints. |
| Secure sessions | Server-side session management with signed cookies, configurable HTTPS-only mode, strict same-site policy, and 12-hour expiry. |
| Timing-attack protection | Password verification uses constant-time comparison to prevent credential inference. |
| Rate limiting | Per-IP request throttling on write and authentication endpoints to mitigate brute-force and abuse. |
| CORS policy | Configurable cross-origin resource sharing with no open-by-default posture. |

### System Health & Monitoring

| Feature | Description |
|---------|-------------|
| Health check endpoint | Reports the operational status of all dependent services — Document AI, database connectivity, and translation providers — in a single call. |
| Timing metadata | Every parse operation records detailed timing breakdowns (OCR, translation, heuristic extraction, LLM extraction, FIR drafting) for performance monitoring. |
| Structured logging | Consistent, machine-readable log output suitable for aggregation in cloud logging platforms. |

---

## Technical Architecture

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend framework** | Python 3.12 · FastAPI 0.135.1 · Uvicorn (ASGI) |
| **Frontend** | Vanilla JavaScript · Single-page HTML application · CSS custom properties design system |
| **Database** | PostgreSQL (async) via SQLAlchemy 2.0 + asyncpg |
| **OCR engine** | Google Document AI |
| **Translation** | Google Cloud Translation · OpenAI GPT · Google Gemini (multi-provider with fallback) |
| **AI extraction** | OpenAI GPT (few-shot, question-guided prompts with confidence validation) |
| **Cloud platform** | Google Cloud (Cloud Run, Cloud SQL, Artifact Registry, Cloud Build) |
| **Containerisation** | Docker (Python 3.12-slim base, non-root execution) |

### High-Level System Architecture

The application follows a **server-rendered monolith** pattern optimised for operational simplicity:

- A single FastAPI process serves both the REST API and the embedded web interface.
- The frontend is a self-contained single-page application embedded in a single HTML file — no build toolchain, no CDN dependencies, no separate deployment.
- The backend orchestrates all external service calls (Document AI, translation APIs, LLM providers) and persists results to the database.
- All communication between client and server occurs over HTTPS via JSON REST endpoints and Server-Sent Events for streaming.

### Authentication & Authorisation

- **Mechanism:** Username/password login with server-side session cookies (Starlette SessionMiddleware).
- **Scope:** Single operator role — authenticated users have full access to parse, history, and management functions.
- **Session security:** Signed cookies with configurable HTTPS-only flag, strict same-site policy, and 12-hour maximum age.
- **Credential safety:** Constant-time password comparison; secrets injected via environment variables, never committed to source control.

### Data Flow Summary

1. **Upload** — The operator uploads a complaint document through the web interface.
2. **OCR** — The file is sent to Google Document AI, which returns extracted text.
3. **Language detection** — Character-range heuristics identify the document language and assign a confidence score.
4. **Translation** — Non-English text is translated to English via the configured provider (Google, OpenAI, or Gemini), with automatic fallback.
5. **Heuristic extraction** — Rule-based pattern matching identifies the 5W+1H fields from the English text.
6. **AI-guided extraction** *(optional)* — An LLM validates and enriches the heuristic results using few-shot prompts, returning confidence scores and evidence snippets.
7. **FIR drafting** — A structured FIR draft is generated from the extracted fields, including proposed BNS sections and jurisdiction.
8. **Gap analysis** — Missing or uncertain fields are identified, and a completeness score is calculated.
9. **Persistence** — The original file, raw OCR text, structured output, and completeness score are stored in PostgreSQL.
10. **Response** — The complete structured result is returned to the client for display in the operator's chosen view.

### Deployment Model

- **Runtime:** Google Cloud Run (fully managed, serverless containers) in the `asia-southeast1` region.
- **Database:** Google Cloud SQL for PostgreSQL with IAM-based authentication from Cloud Run.
- **Container registry:** Google Artifact Registry.
- **CI/CD:** Google Cloud Build triggers on push to the `main` branch, automatically building and deploying new container revisions.
- **Scaling:** Cloud Run auto-scales from zero to meet demand, with instant rollback to any previous revision.
- **Security posture:** The Cloud Run service is publicly accessible (the application's own login gate handles operator authentication), with all traffic encrypted via managed TLS.

### Notable Libraries & Design Patterns

- **Async-first I/O** — The entire backend uses Python's `asyncio` with async database drivers and non-blocking HTTP handlers for high concurrency on minimal infrastructure.
- **Multi-provider resilience** — Translation and extraction services are configured with automatic fallback chains, ensuring the system degrades gracefully when any single provider is unavailable.
- **Schema-versioned output** — The parsed complaint JSON follows a versioned schema (currently v3.0), enabling forward-compatible evolution of the data model.
- **Dual-layer extraction** — Heuristic rules provide a fast, deterministic baseline; the optional LLM layer adds depth with confidence-gated acceptance, ensuring AI results are only used when they meet quality thresholds.

---

## Benefits for the Police Department

### Faster Complaint Processing & Improved Response Times

Manual processing of complaint documents — especially handwritten, non-English submissions — is one of the most time-consuming front-desk tasks in any police station. The ADS Complaint Analyser reduces the time required to read, translate, and structure a complaint from **minutes to seconds**. Officers no longer need to manually transcribe handwritten Hindi or Telugu documents; the system handles OCR, translation, and field extraction automatically. This directly translates to shorter queues at the complaint desk and faster initiation of investigations.

### Accurate, Structured Intelligence from Day One

Every complaint is broken down into the 5W+1H framework that underpins sound investigative practice. Instead of working from unstructured narrative text, investigating officers receive a clean, categorised summary of the complainant, accused, incident details, location, motive, and method — with confidence scores that highlight which facts are well-established and which require follow-up. The automated gap analysis ensures no critical detail is overlooked before an FIR is filed.

### Multilingual Accessibility

India's linguistic diversity means police stations routinely receive complaints in multiple languages and scripts, including handwritten submissions. The platform's ability to process Hindi, Telugu, and English documents — and to cross-reference original text against translations — removes the language barrier from complaint intake. This ensures equitable service for all citizens, regardless of the language in which they file their complaint.

### Streamlined FIR Drafting & Legal Compliance

The automated FIR draft generation — complete with proposed BNS sections, jurisdiction mapping, and evidence listing — gives officers a structured starting point that aligns with legal filing requirements. This reduces drafting errors, ensures relevant sections of law are considered, and creates a consistent, auditable record from the moment a complaint is received.

### Comprehensive Case History & Audit Trail

Every parsed complaint is permanently stored with its original document, full extraction results, and completeness score. This persistent record provides a clear audit trail for internal reviews, judicial proceedings, and oversight inquiries. The compare mode allows officers to cross-reference complaints and identify patterns across cases — supporting intelligence-led policing.

### Data-Driven Decision Making

The structured, machine-readable output from every complaint enables departmental leadership to aggregate and analyse complaint data at scale. Trends in crime type, geographic hotspots, repeat offenders, and seasonal patterns become visible when complaints are captured as structured data rather than paper files. This intelligence supports resource allocation, beat planning, and strategic policing initiatives.

### Enhanced Inter-Departmental Coordination

Because every complaint is stored in a standardised digital format with consistent field definitions, sharing case information between stations, districts, or specialised units becomes straightforward. The structured JSON output can be integrated with downstream case management, crime mapping, or analytics systems without manual re-entry.

### Reduced Administrative Burden & Cost Savings

By automating the most labour-intensive steps of complaint intake — transcription, translation, classification, and FIR drafting — the platform frees up officer time for core policing duties. The serverless cloud deployment eliminates the need for on-premise hardware, dedicated IT staff, or complex infrastructure management. The system scales automatically with demand and incurs costs only when actively processing complaints.

### Officer Accountability & Transparency

The timestamped, immutable parse history creates a verifiable record of when each complaint was received and processed. This supports internal accountability mechanisms and demonstrates to the public that every complaint is systematically recorded and acted upon — strengthening community trust in the department's responsiveness and fairness.

### Operational Resilience

The cloud-native architecture ensures the system is available around the clock without manual intervention. Automatic scaling handles peak loads (such as festival seasons or major incidents), and instant rollback capability means any issue can be resolved in seconds. Multi-provider fallback for translation and AI services ensures the platform remains functional even if an individual cloud service experiences disruption.

---

<p align="center"><em>ADS Complaint Analyser — Transforming complaint intake from paperwork into police work.</em></p>
