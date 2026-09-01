# CascadeX — Security Controls & Threat Model

> **Phase 09 Document.** Maps all implemented security controls directly to `docs/PROJECT_OVERVIEW.md` §8. This document distinguishes between controls enforced in code and the bounded scope of a course demonstration system.

---

## 1. Security Architecture Summary

CascadeX treats all patient medication records, dose schedules, and interaction alerts as sensitive personal health data. While formal HIPAA / FDA Software as a Medical Device (SaMD) regulatory compliance is outside the scope of this course project (see §10), the system is built with industry-grade defense-in-depth principles:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Mobile Client (Flutter)                       │
│  - On-Device ML Kit OCR (zero cloud OCR transport)                     │
│  - flutter_secure_storage (OS Keychain / Keystore for JWTs)            │
│  - Hive local encrypted cache (offline-safe)                           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ TLS 1.3 / HTTPS
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         FastAPI API Gateway                            │
│  - Explicit CORS allow-list (no wildcard '*')                          │
│  - Rate limiting on /auth (slowapi)                                    │
│  - Pydantic strict schema validation                                   │
│  - LoggingMiddleware: PII/PHI-free structured request logging           │
│  - Short-lived JWT verification (HS256 / configurable asymmetric)      │
│  - Server-side RBAC (Patient vs Caregiver permissions)                 │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Parameterized Cypher
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                            Neo4j 5 Graph DB                            │
│  - Parameterized queries only (Cypher injection immune)                │
│  - Application-level field encryption at rest (Fernet AES-128-CBC)     │
│  - Encrypted properties: ScanRecord.ocr_text                           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Authentication & Credential Storage

| Threat | Control Implemented | Verification / Code Reference |
|---|---|---|
| Password credential stuffing / rainbow tables | **Argon2id** password hashing (`argon2-cffi`) with secure salt generation per user | `app/core/security.py:hash_password()`, `test_auth_register_login.py` |
| Token theft / replay attacks | **Short-lived JWT access tokens** (15 min default) with **rotating refresh tokens** (7 days default) stored with unique `jti` | `app/core/security.py:create_access_token()`, `test_auth_tokens.py` |
| Mobile token extraction | Tokens stored in **OS Keychain (iOS)** and **EncryptedSharedPreferences / KeyStore (Android)** via `flutter_secure_storage`, never plain `SharedPreferences` | `frontend/lib/services/secure_storage.dart` |
| Brute-force login / OTP attacks | **Rate limiting** via `slowapi` on `/api/v1/auth/login` and `/api/v1/auth/register` (10 req/min in prod) | `app/api/auth.py`, `app/main.py` |

---

## 3. Authorization & Multi-Tenancy (RBAC)

- **User Scoping:** Every medication, schedule, log, scan, and alert query is explicitly scoped to the authenticated `user_id` extracted from the verified JWT.
- **Caregiver RBAC:** Caregiver-patient relationships are modeled as `(:User)-[:MONITORED_BY]->(:Caregiver)` with granular `permission_level` (`"view"` vs `"manage"`).
- **Server-Side Enforcement:** Permission checks are executed strictly server-side in route dependencies before database operations occur, never relying on UI visibility toggles.
- **Verification:** Verified by `tests/test_caregiver_rbac.py` and `tests/test_medications_scoping.py`.

---

## 4. Injection Protection & Data Integrity

- **Parameterized Cypher Queries:** 100% of queries against Neo4j use parameterized arguments (`$user_id`, `$drug_id`, `$pairs`). String concatenation of user inputs into Cypher queries is strictly prohibited across the codebase, eliminating Cypher injection vulnerabilities.
- **Strict Pydantic Validation:** All request payloads are strictly validated using Pydantic v2 schemas (`ScanCreate`, `MedicationCreate`, `UserRegister`, etc.), rejecting malformed fields, unauthorized types, and oversized strings before business logic execution.

---

## 5. Field-Level Encryption at Rest

### What is Encrypted
- `ScanRecord.ocr_text`: Raw OCR text extracted from pill bottle labels (which may contain patient names, prescription numbers, doctor names, and clinic locations) is encrypted using **Fernet symmetric encryption** (AES-128-CBC + HMAC-SHA256 authentication) before writing to Neo4j.
- Key management: Derived from `FIELD_ENCRYPTION_KEY` environment variable. In dev/test environments without a key, the system operates in a safe passthrough mode.

### What is Kept as Structured Graph Nodes
- Canonical `Drug` nodes, `INTERACTS_WITH` relationships, and standard medication entries are stored as structured graph properties to allow high-performance graph index matching and Cypher UNWIND traversal (NFR-3).

### Verification
- Tested in `backend/tests/test_encryption_at_rest.py`: validates ciphertext storage, decryption fidelity, random IV variation, and error handling on invalid keys.

---

## 6. Observability & Privacy-Preserving Logging

Medical safety systems must remain observable without leaking Protected Health Information (PHI) or Personally Identifiable Information (PII) into log aggregation systems.

- **`LoggingMiddleware` (`app/middleware/logging_middleware.py`):**
  - **Logged:** HTTP method, URL path, HTTP status code, request latency in milliseconds, and opaque `user_id` UUID.
  - **Explicitly Excluded & Never Logged:** Request body, response body, Authorization headers/tokens, query parameters (which may contain search queries), patient names, email addresses, and medication/drug names.
- **Verification:** Verified by `backend/tests/test_logging_no_pii.py` which executes live API operations and asserts that zero drug names or emails appear in captured log streams.

---

## 7. Transport Security & CORS

- **CORS Allow-List:** `CORSMiddleware` uses an explicit, configurable origin allow-list loaded from `ALLOWED_ORIGINS` in `config.py` (default: `http://localhost:3000,http://localhost:8080`). Wildcard `*` is prohibited in production.
- **Verification:** Verified by `backend/tests/test_security_headers_cors.py` ensuring disallowed origins (e.g., `http://evil.com`) are rejected and no wildcard headers are emitted.

---

## 8. AI Safety & Privacy Invariants

The backend interfaces with Google Gemini (`gemini-1.5-flash`) under strict architectural constraints:

1. **Deterministic Edge Invariant:** The LLM is **never** used to originate, infer, or predict drug-drug interactions. Pairwise interactions are strictly determined by confirmed `INTERACTS_WITH` graph edges from the DDInter 2.0 academic dataset.
2. **Post-Query Plain Language Rewrite:** `plain_language_rewrite()` is invoked only *after* Neo4j returns a verified interaction edge.
3. **Candidate List Confinement:** `match_drug_name()` receives only candidate drug names extracted from the local catalog; it cannot return any name outside this candidate list.
4. **On-Device OCR:** OCR extraction is performed entirely on the client mobile device via Google ML Kit Text Recognition, preventing unvetted raw prescription images from being uploaded to cloud services.

---

## 9. Dependency Vulnerability Management

- **Automated CI Scanning:** GitHub Actions CI executes `pip-audit` on every push and pull request, failing the build on packages with known critical/high CVEs.
- **Dependabot:** Configured in `.github/dependabot.yml` for weekly automated dependency updates covering `pip` (backend), `pub` (Flutter frontend), and `github-actions`.
- **Flutter Auditing:** CI executes `flutter pub outdated` to flag deprecated or vulnerable frontend dependencies.

---

## 10. Scope Boundaries & Disclaimers

> ⚠️ **Academic Demonstration Disclaimer:**
> CascadeX is developed as a course software engineering project and educational prototype. It has **not** undergone formal FDA 510(k) clearance, CE mark certification as Software as a Medical Device (SaMD), or formal HIPAA compliance audit. It must not be used as a sole diagnostic tool or replacement for professional clinical judgment by a licensed pharmacist or physician.
