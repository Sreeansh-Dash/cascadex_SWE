# Software Requirements Specification
## CascadeX — Drug-to-Drug Interaction Warning System

**Course:** BCSE301L – Software Engineering
**Document version:** 1.0
**Status:** Draft for review

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements for **CascadeX**, a patient-facing application that warns users when the medications they are taking together may cause an adverse drug-to-drug interaction (DDI). It is intended for the course instructor/evaluator, and for the developer(s) as a build reference for the coding agents used during implementation.

### 1.2 Scope
CascadeX allows a user (typically elderly, or managing medication for an elderly relative) to:
- Register/maintain a personal medication list (drug name, dosage, schedule), entered manually or via a scanned image of the medicine strip/box.
- Receive a warning when two or more active medications in their list have a known adverse interaction, including severity and a plain-language explanation.
- Review a history of past warnings and dose intake.

CascadeX is **not** a diagnostic or prescribing tool, does not replace a pharmacist or physician, and does not identify loose/unlabeled pills by appearance (see 2.5 Constraints).

### 1.3 Definitions, Acronyms, Abbreviations
| Term | Meaning |
|---|---|
| DDI | Drug-to-Drug Interaction |
| OCR | Optical Character Recognition |
| SRS | Software Requirements Specification |
| PII | Personally Identifiable Information |
| RBAC | Role-Based Access Control |
| WCAG | Web Content Accessibility Guidelines |

### 1.4 References
- DDInter 2.0 open drug-interaction dataset
- RxNorm (US National Library of Medicine) drug nomenclature
- openFDA drug label / adverse event API
- IEEE 830 / ISO-IEC-IEEE 29148 SRS structure (used as the template for this document)

### 1.5 Overview
Section 2 describes the product at a high level. Section 3 lists functional requirements. Section 4 lists non-functional requirements. Section 5 lists external interface requirements. Section 6 lists data requirements. Section 7 covers compliance and disclaimers.

---

## 2. Overall Description

### 2.1 Product Perspective
CascadeX is a new, standalone mobile-first application (not a component of an existing hospital or pharmacy system). It consumes a third-party, pre-curated drug interaction dataset (DDInter) rather than sourcing interaction data itself, and normalizes drug names against RxNorm.

### 2.2 Product Functions (summary)
1. Account creation and secure login
2. Manual entry of a medication (drug, dosage, schedule)
3. Scan-to-add a medication from a photo of packaging/strip
4. Interaction check across the user's active medication list
5. Interaction alert with severity, explanation, and recommended action ("consult your pharmacist/doctor")
6. Dose reminder and intake logging
7. History/timeline of alerts and doses
8. Optional caregiver linkage for assisted management

### 2.3 User Characteristics
- **Primary user:** older adult, possibly with limited technical fluency, possibly with reduced vision/dexterity. Assume low tolerance for small text, dense screens, or multi-step flows.
- **Secondary user:** a caregiver/family member managing medications on the primary user's behalf.
- Neither user class is assumed to have clinical training — all language in the app must be plain, non-clinical English (with room for future localization).

### 2.4 Assumptions and Dependencies
- The DDI dataset (DDInter) is accurate as of its last update; CascadeX is only as correct as its source data and displays the data source/version to the user.
- Users have a smartphone with a camera for the scan feature.
- Internet connectivity is available at least periodically to sync the interaction database and sign in.

### 2.5 Constraints
- Visual pill identification (identifying a loose, unlabeled pill from a photo) is **out of scope** — this is a research-grade computer vision problem and is not attempted. Scanning is limited to OCR of printed text on packaging/strips/labels.
- CascadeX must never present itself as a substitute for professional medical advice; every interaction warning carries a "consult a pharmacist or doctor" notice.
- The system must degrade safely: if the interaction engine cannot reach a confident match (e.g., unrecognized drug name), it must say so explicitly rather than silently returning "no interaction found."

---

## 3. Functional Requirements

Each requirement is tagged `FR-<module>-<n>` for traceability into test cases and the WBS.

### 3.1 Authentication & Account (AUTH)
- **FR-AUTH-1**: The system shall allow a user to register with name, date of birth, and either email or phone number.
- **FR-AUTH-2**: The system shall authenticate returning users via password or OTP.
- **FR-AUTH-3**: The system shall allow a user to link one or more caregiver accounts with a chosen permission level (view-only or manage).

### 3.2 Medication Entry (MED)
- **FR-MED-1**: The system shall allow a user to manually add a medication by searching the drug catalog (generic or brand name), then entering dosage amount, unit, frequency, and time(s) of day.
- **FR-MED-2**: The system shall allow a user to capture a photo of a medicine strip/box; the system shall run OCR on the image and propose a best-match drug from the catalog for user confirmation before adding it.
- **FR-MED-3**: The system shall allow a user to mark a medication inactive/end it without deleting its history.
- **FR-MED-4**: The system shall allow a user to log an actual dose as taken, missed, or skipped.

### 3.3 Interaction Engine (INT)
- **FR-INT-1**: On every add/edit of an active medication, the system shall check all pairs of the user's currently active medications against the DDI dataset.
- **FR-INT-2**: If an interaction is found, the system shall generate an alert containing: the two drugs involved, severity level, a plain-language explanation of the mechanism, and recommended action.
- **FR-INT-3**: The system shall classify severity into at least: Minor, Moderate, Major/Contraindicated, using the source dataset's classification.
- **FR-INT-4**: If a drug entered cannot be confidently matched to the catalog, the system shall inform the user rather than silently skipping the interaction check.

### 3.4 Alerts & Notifications (ALERT)
- **FR-ALERT-1**: The system shall display a new interaction alert immediately and require the user to acknowledge it.
- **FR-ALERT-2**: The system shall send a dose reminder notification at each scheduled dose time.
- **FR-ALERT-3**: The system shall maintain a chronological history of all alerts, viewable by the user and any linked caregiver.

### 3.5 History & Reporting (HIST)
- **FR-HIST-1**: The system shall show a timeline of doses taken/missed per medication.
- **FR-HIST-2**: The system shall allow export of the current medication list and interaction history as a shareable summary (e.g., PDF) for a doctor visit.

---

## 4. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Usability | Core flows (add medication, view alert) must be completable in ≤3 taps/screens; minimum tappable target 44×44dp; default font size readable at arm's length without zooming. |
| NFR-2 | Accessibility | UI shall meet WCAG 2.1 AA contrast ratios; support system-level font scaling; support screen readers (TalkBack/VoiceOver) on all core flows. |
| NFR-3 | Performance | Interaction check across a user's medication list (typically <20 drugs) shall return in ≤500 ms server-side. |
| NFR-4 | Reliability | Interaction engine shall have no false negatives it can avoid — an unmatched drug must surface as "unknown," never as "safe." |
| NFR-5 | Security | All PII and health data encrypted at rest and in transit (see Section 7). |
| NFR-6 | Availability | Backend API target uptime 99% for the course-deployment environment. |
| NFR-7 | Portability | Mobile client shall run on current Android and iOS (if built with Flutter) from a single codebase. |
| NFR-8 | Maintainability | Interaction dataset shall be swappable/updatable without a code change (versioned data import job). |

---

## 5. External Interface Requirements

### 5.1 User Interfaces
Mobile app (and/or responsive web) with: onboarding, medication list, add-medication (manual + scan), alert detail, history, settings/accessibility.

### 5.2 Hardware Interfaces
Device camera (scan feature). No other special hardware.

### 5.3 Software Interfaces
- REST API between frontend and backend (JSON over HTTPS)
- Graph database (interaction lookups)
- Relational/document store (user, medication, log data) — or a single graph DB serving both, see Project Overview doc
- OCR engine (on-device or cloud)
- Optional LLM API for plain-language explanation generation and fuzzy drug-name matching

### 5.4 Communication Interfaces
HTTPS/TLS 1.2+ for all client-server traffic. Push notification service for reminders/alerts.

---

## 6. Data Requirements
- Drug catalog and DDI dataset imported from DDInter (versioned; import date/version stored and shown in-app).
- Drug name normalization against RxNorm to resolve brand → generic.
- Full entity list and relationships are defined in `CascadeX_ER_Diagram.mdj` (StarUML) and summarized in the Project Overview document.

---

## 7. Compliance, Safety & Disclaimers
- CascadeX is a **course/demonstration project**, not a certified medical device; it must display a persistent disclaimer that it does not replace professional medical advice.
- Health-related personal data (medication list) is sensitive; the system should apply the same handling care as personal health information even though formal regulatory certification (e.g., HIPAA/DPDP compliance audit) is out of scope for the course deliverable — see Cybersecurity section of the Project Overview document for the specific controls implemented.
- The system must never suppress or downgrade a known severe interaction for UX simplicity.

---

## 8. Appendix — Traceability Note
Functional requirement IDs (`FR-*`) in this document map 1:1 to backend endpoints and test cases described in the Project Overview and Work Breakdown Structure documents, to keep implementation, testing, and grading rubric alignment straightforward.
