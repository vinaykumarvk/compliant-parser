# Case Lifecycle — Business Requirements Document

## 1. Overview

The IQW Case Lifecycle models the real Indian police investigation workflow from initial complaint through final disposal. It replaces the simplified Open/Closed model with a proper state machine reflecting statutory requirements under CrPC/BNSS.

## 2. Case Lifecycle Flow

```
                            ┌─────────────────┐
                            │   Complaint      │
                            │   Received       │
                            └────────┬─────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                                  ▼
           ┌───────────────┐                 ┌────────────────┐
           │ FIR Registered │                 │ Closed (No FIR)│  ← Terminal
           └───────┬───────┘                 └────────────────┘
                   │
                   ▼
           ┌───────────────────┐
           │Under Investigation │
           └───────┬───────────┘
                   │
       ┌───────────┼───────────────┐
       ▼           ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌────────────┐
│Charge Sheet  │ │Closure Report│ │Transferred │ ← Terminal
│Filed         │ │Filed         │ └────────────┘
└──────┬───────┘ └──────┬───────┘
       │                 │
       ▼                 ▼
┌──────────────┐  ┌──────────┐
│Court         │  │ Disposed │ ← Terminal
│Proceedings   │  └──────────┘
└──────┬───────┘
       │
       ▼
┌──────────┐
│ Disposed │ ← Terminal
└──────────┘
```

## 3. Status Definitions

| Status | Description | Terminal? |
|--------|-------------|-----------|
| Complaint_Received | Complaint/petition received and recorded | No |
| FIR_Registered | FIR registered with crime number and offence sections | No |
| Under_Investigation | Active investigation by IO | No |
| Charge_Sheet_Filed | Charge sheet filed before court | No |
| Closure_Report_Filed | Closure report (FR/Untraced/MoF) submitted to court | No |
| Court_Proceedings | Case before court, trial in progress | No |
| Transferred | Case transferred to another PS/agency | Yes |
| Disposed | Case concluded (judgment/closure accepted) | Yes |
| Closed_No_FIR | No cognizable offence, FIR not registered | Yes |

## 4. Allowed Transitions

| From | Allowed Transitions To |
|------|----------------------|
| Complaint_Received | FIR_Registered, Closed_No_FIR |
| FIR_Registered | Under_Investigation |
| Under_Investigation | Charge_Sheet_Filed, Closure_Report_Filed, Transferred |
| Charge_Sheet_Filed | Court_Proceedings |
| Closure_Report_Filed | Disposed |
| Court_Proceedings | Disposed |
| Transferred | (none — terminal) |
| Disposed | (none — terminal) |
| Closed_No_FIR | (none — terminal) |

### Transition Validation Rules

- **FIR_Registered**: Crime Number (NNNN/YYYY) must be set on the case before this transition.
- **Charge_Sheet_Filed**: Should be filed within 60 days (summons cases) or 90 days (sessions cases) of FIR.
- Terminal states have no outgoing transitions.

## 5. Stage-Specific Document Requirements

| Stage | Expected Documents |
|-------|-------------------|
| Complaint_Received | Petition, Complaint copy |
| FIR_Registered | FIR |
| Under_Investigation | Witness_Statement, Seizure_Memo, Arrest_Memo, Medical_Report, FSL_Report, CDR |
| Charge_Sheet_Filed | Charge_Sheet, Witness_Statement, FSL_Report |
| Closure_Report_Filed | Closure report (Other type) |
| Court_Proceedings | — |

## 6. Stage-Specific Action Checklists

### Complaint_Received
- Record complainant details
- Assess cognizability
- Make GD entry

### FIR_Registered
- Assign IO
- Identify offence sections (BNS/IPC)
- Sync with CCTNS

### Under_Investigation
- Visit scene of crime & prepare panchnama
- Record witness statements (Sec 161 CrPC / 180 BNSS)
- Collect & seize evidence
- Arrest accused (if needed) — prepare arrest memo
- Send exhibits to FSL
- Obtain CDR/technical evidence
- Get medical examination reports
- Submit progress reports

### Charge_Sheet_Filed
- Prepare list of witnesses
- Prepare list of documents/exhibits
- Generate evidence certificates (Sec 65B)

### Closure_Report_Filed
- Prepare closure report (FR/Untraced/Mistake of Fact)
- Submit to Magistrate

### Court_Proceedings
- Attend hearings
- Present evidence
- Produce witnesses

## 7. Statutory Deadlines

| Deadline | Duration | Triggered At |
|----------|----------|-------------|
| Charge sheet filing (summons) | 60 days from FIR | FIR_Registered |
| Charge sheet filing (sessions) | 90 days from FIR | FIR_Registered |
| Progress report submission | 30 days recurring | Under_Investigation |
| Witness examination | 60 days from FIR | Under_Investigation |
| FSL report follow-up | 45 days from exhibit submission | Under_Investigation |

## 8. Role-Based Permissions

| Action | IO | Clerk | AI_Admin | System_Admin |
|--------|-----|-------|----------|--------------|
| Create Case | Yes | Yes | No | Yes |
| Transition Status | Yes (own cases) | No | No | Yes |
| Upload Documents | Yes (own cases) | Yes (own PS) | No | Yes |
| View Case | Own cases | Own PS | All (read-only) | All |
| Seed Demo Case | Yes | Yes | Yes | Yes |

## 9. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/cases/lifecycle | Returns transitions + stage guidance |
| POST | /api/v1/cases/seed-demo | Creates a demo case |
| PATCH | /api/v1/cases/{id}/status | Transition case status |

## 10. Frontend Components

- **Lifecycle Stepper**: Horizontal visual indicator showing progression through main path stages
- **Stage Guidance Panel**: Shows expected documents, actions, and next step hint for current stage
- **Status Filter**: Dropdown with all 9 status values
- **Empty State**: Shows "Create Demo Case" button when no cases exist
