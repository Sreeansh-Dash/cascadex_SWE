# CascadeX — Project Overview

A working reference doc for anyone (human or coding agent) picking up this project. Pair this with `SRS.md` (what it must do) and `CascadeX_ER_Diagram.mdj` (data model) before writing code.

---

## 1. What is it?

CascadeX is a patient-facing app that tracks a person's medications (drug, dosage, schedule) and warns them when two or more of those medications, taken together, are known to cause an adverse drug-to-drug interaction (DDI) — a real and under-caught risk for elderly patients managing multiple prescriptions. A user (or their caregiver) enters a drug either manually or by photographing the packaging; CascadeX checks it against a curated interaction dataset and raises a plain-language warning, not a clinical diagnosis.

It is explicitly **not**: a prescribing tool, a substitute for a pharmacist/doctor, or a pill-image identifier (see Constraints in the SRS).

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Flutter (Dart)** | One codebase for Android + iOS, strong accessibility APIs, easy camera integration for scanning, and full control over a custom (non-templated) design system. |
| Backend | **FastAPI (Python 3.11+)** | Async, auto-generated OpenAPI docs (useful for a course write-up), same language as the ML/normalization pieces. |
| Primary database | **Neo4j (graph)** | Drugs and their interactions are natively a graph — "does A interact with B" is a relationship lookup, not a join. Cypher queries stay readable as the dataset grows. |
| Interaction dataset | **DDInter 2.0** (free, open, ~2,300 drugs / 300K+ interaction records with severity + mechanism) | No commercial license needed, unlike DrugBank's full dataset. |
| Name normalization | **RxNorm** | Resolves brand names → generic names so "Crocin" and "paracetamol" match the same catalog entry. |
| OCR (scan feature) | **Google ML Kit Text Recognition** (on-device) | Fast, free, works offline, sufficient for printed strip/box text. |
| AI/LLM assist | **Claude / Gemini API call from the backend** | Two narrow uses only: (1) fuzzy-matching noisy OCR/typed input to a catalog drug, (2) rewriting a dataset's clinical mechanism text into a plain-language sentence. Never used to invent an interaction that isn't in the dataset. |
| Auth | **JWT (access + refresh tokens)**, Argon2 password hashing | Standard, well-understood, easy to reason about for a security write-up. |
| Testing | **pytest** (backend), **flutter_test / integration_test** (frontend) | Matches each ecosystem's default. |
| CI/CD | **GitHub Actions** | Free for student repos, same as your CodeCity project. |
| Containerization | **Docker Compose** (backend + Neo4j) | One command to stand up the whole backend for grading/demo. |

---

## 3. Architecture

Layered, single backend service (no premature microservices — keep it defensible for a course project):

```
┌─────────────────────────────┐
│   Flutter App (mobile)      │
│  screens → state → api_client│
└───────────────┬─────────────┘
                │ HTTPS / JSON (REST, /api/v1)
┌───────────────▼─────────────┐
│        FastAPI Backend      │
│ ┌───────────────────────┐  │
│ │  API layer (routers)   │  │  auth, medications, scans, alerts, history
│ ├───────────────────────┤  │
│ │  Service layer         │  │  interaction_engine, ocr_service,
│ │                        │  │  drug_normalizer, notification_service
│ ├───────────────────────┤  │
│ │  Data access layer     │  │  Neo4j driver (parameterized Cypher)
│ └───────────────────────┘  │
└───────────────┬─────────────┘
                │ Bolt protocol
        ┌───────▼────────┐
        │     Neo4j       │  Drug / DrugInteraction / User /
        │  (graph DB)     │  MedicationEntry / Alert / ScanRecord nodes
        └─────────────────┘
```

**Interaction-check flow** (the core feature): user adds/edits a medication → API validates + normalizes the drug name → service layer queries Neo4j for edges between the new drug node and every other *active* medication node for that user → any `INTERACTS_WITH` edge found is turned into an `InteractionAlert` → push notification + in-app alert.

---

## 4. Database Structure

Neo4j as a single graph, modeling both the drug knowledge base and per-user data as connected nodes — this is what makes "check all my active drugs against each other" a short Cypher query instead of a batch of joins.

**Core node labels:** `User`, `Caregiver`, `Drug`, `DrugBrandName`, `MedicationEntry`, `DoseSchedule`, `DoseIntakeLog`, `DrugInteraction` (or model interactions as a direct `INTERACTS_WITH` relationship between two `Drug` nodes with severity/mechanism as edge properties — either works; the ER diagram uses an explicit node so severity/mechanism/source are queryable as their own entity), `InteractionAlert`, `ScanRecord`, `Notification`.

**Key relationships:** `User -[:TAKES]-> MedicationEntry -[:OF_DRUG]-> Drug`, `Drug -[:INTERACTS_WITH {severity, mechanism}]-> Drug`, `MedicationEntry -[:HAS_SCHEDULE]-> DoseSchedule`, `User -[:MONITORED_BY]-> Caregiver`.

The full entity/attribute/relationship model (12 entities, 17 relationships) is defined in **`CascadeX_ER_Diagram.mdj`** — open it directly in StarUML. It includes primary/foreign keys and types for every entity so it doubles as your schema reference regardless of which physical DB you implement it in.

> If you'd rather keep transactional data (accounts, logs) out of the graph DB for simplicity, a valid alternative is **polyglot persistence**: Neo4j for the `Drug`/`DrugInteraction` knowledge graph only, PostgreSQL for everything else. This is more "textbook enterprise," but adds a second database to manage — only worth it if you want to demonstrate that pattern for grading.

---

## 5. Directory Structure

```
cascadex/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI routers: auth.py, medications.py, scans.py, alerts.py, history.py
│   │   ├── core/                # config.py, security.py, dependencies.py
│   │   ├── db/                  # neo4j_session.py, seed_ddinter.py (dataset import)
│   │   ├── models/              # Pydantic request/response schemas
│   │   ├── services/            # interaction_engine.py, ocr_service.py, drug_normalizer.py, notification_service.py
│   │   ├── ml/                  # llm_client.py (fuzzy match + plain-language rewrite prompts)
│   │   └── main.py
│   ├── tests/                   # pytest, mirrors app/ structure
│   ├── data/                    # DDInter/RxNorm raw + versioned snapshots, import scripts
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── lib/
│   │   ├── screens/              # onboarding, medication_list, add_medication, scan, alert_detail, history, settings
│   │   ├── widgets/               # reusable accessible components (big_button, severity_badge, ...)
│   │   ├── services/               # api_client.dart, secure_storage.dart, notification_service.dart
│   │   ├── state/                   # riverpod or bloc providers
│   │   ├── theme/                    # colors.dart, typography.dart (accessibility-first design tokens)
│   │   └── main.dart
│   ├── test/
│   └── pubspec.yaml
├── docs/
│   ├── SRS.md
│   ├── PROJECT_OVERVIEW.md        (this file)
│   ├── CascadeX_ER_Diagram.mdj
│   └── WBS.xlsx
├── docker-compose.yml              # backend + neo4j
├── .github/workflows/ci.yml
└── README.md
```

---

## 6. Backend

- **API style:** REST, versioned under `/api/v1/`, JSON in/out, OpenAPI docs auto-served at `/docs` for free (useful evidence for your report).
- **Key endpoints:** `POST /auth/register`, `POST /auth/login`, `POST /medications`, `POST /medications/scan`, `GET /medications`, `GET /alerts`, `POST /alerts/{id}/acknowledge`, `GET /history`.
- **Interaction engine** is a pure service function — given a user's active drug list, return all pairwise interactions — so it can be unit-tested against known DDInter pairs independently of the API/DB.
- **Background jobs:** dose-reminder scheduler (APScheduler or a simple cron), DDInter dataset re-import job (versioned, doesn't silently overwrite without a version bump logged).
- **Error handling:** every response follows one error shape (`{code, message}`); an unmatched/unrecognized drug returns an explicit "unrecognized" status — the API must never imply "no interaction" when it actually means "couldn't check."

## 7. Frontend

- **Flutter**, Material 3 as a base but themed deliberately (custom type scale, warm/legible palette, generous spacing) so it doesn't read as a default-template AI app — this matters for both usability and your "doesn't look AI-generated" goal.
- **Accessibility-first defaults, not an afterthought:** large default font size, high-contrast severity colors (tested for contrast ratio, not just "red/yellow/green"), minimum 44×44dp tap targets, no gesture-only navigation, screen-reader labels on every interactive element.
- **State management:** Riverpod or Bloc — pick one and stay consistent (Riverpod is generally less boilerplate for a solo/small-team course project).
- **Offline behavior:** cache the last-fetched medication list and alerts locally (e.g., Hive/SQLite on-device) so the app is still useful with no signal; queue any writes made offline.
- **Scan flow UX:** camera → OCR preview with the *proposed* drug name shown for confirmation before it's added — never auto-add a scanned drug without the user confirming, since OCR misreads are exactly the kind of silent error this app exists to prevent.

## 8. Cybersecurity

Treat medication data as sensitive personal health information even though formal regulatory certification is out of scope for a course deliverable.

- **Transport:** HTTPS/TLS everywhere; no plaintext API calls, even in local dev if avoidable.
- **Auth:** Argon2 (or bcrypt) password hashing, JWT access tokens with short expiry + refresh token rotation, tokens stored in `flutter_secure_storage` (Keychain/Keystore) — never `SharedPreferences`/plain files.
- **Authorization:** RBAC between a user and their linked caregiver(s) — enforce "view-only" vs "manage" server-side on every request, not just hidden in the UI.
- **Input handling:** Pydantic validation on every request; all Cypher queries parameterized (never string-concatenated — this is Cypher injection, the graph-DB analogue of SQL injection).
- **Rate limiting:** on `/auth/login` and `/auth/register` to blunt brute-force/credential-stuffing.
- **Secrets:** DB credentials, JWT signing key, and any LLM API keys in environment variables / Docker secrets, `.env` in `.gitignore`, never committed.
- **Data minimization & retention:** scanned images are processed for OCR and then discarded (or encrypted at rest if retained for debugging), not kept indefinitely.
- **Encryption at rest:** encrypt sensitive fields (medication list, health notes) at the database or disk level.
- **Logging:** structured logs, but **no PII/PHI in log bodies** — log user IDs, not names/drug lists, in plaintext logs.
- **Dependency hygiene:** enable GitHub Dependabot / `pip-audit` / `flutter pub outdated` in CI so known-vulnerable packages get flagged.
- **CORS:** explicit allow-list of origins, not `*`, once you have a real frontend origin to allow.

---

## 9. Things you likely still need

A few pieces that tend to get missed until late in a project like this:

- **Data source licensing note:** cite DDInter/RxNorm explicitly in the app (an "About the data" screen) — this is both good practice and an easy grading point for academic honesty on data provenance.
- **Testing strategy:** unit tests for the interaction engine against a fixed set of *known* DDInter pairs (so you can prove correctness, not just "it runs"); integration tests for the add-medication → alert-generated flow; a basic accessibility pass (font scaling, screen reader) before the final demo.
- **Alert fatigue design:** not every interaction should interrupt the user the same way — reserve hard interruptive alerts for Major/Contraindicated severity; Minor/Moderate can be a badge in the medication list instead, or you'll train users to dismiss everything.
- **Legal/medical disclaimer:** persistent, not just a one-time onboarding screen — visible on every alert screen.
- **Observability:** a `/health` endpoint and basic error tracking (even just structured logs to start) so a broken interaction check fails loudly, not silently.
- **Versioning the dataset:** store and display which DDInter version is loaded, so a "why didn't it catch this?" question during your demo has a real answer.
- **Dev workflow note:** since you're building in Antigravity with multiple models available, it's worth deciding per-task which model drives — e.g., a large-context/multimodal model for the OCR + UI-heavy frontend work, and whichever model you trust most for the interaction-engine logic (this is the one place in the app where a subtly wrong answer is a safety issue, not a cosmetic bug — so treat that service function as your highest-scrutiny code review target regardless of which model wrote it).
- **Roadmap / stretch goals** (explicitly out of v1, don't build yet): multilingual support, caregiver dashboard with multiple monitored users, pharmacy/EHR import, wearable reminder integration.
