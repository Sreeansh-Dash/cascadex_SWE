# CascadeX

> A patient-facing app that tracks medications and warns users when two or more
> of those medications, taken together, are known to cause an adverse drug-to-drug
> interaction (DDI).

**⚠️ Disclaimer:** CascadeX is a course demonstration project, not a certified medical device. It does not replace a pharmacist or doctor. Always consult a healthcare professional for medical advice.

---

## What is CascadeX?

CascadeX helps elderly patients and their caregivers manage multiple prescriptions safely. Users enter medications manually or by photographing packaging; the system checks against the [DDInter 2.0](https://ddinter.scbdd.com/) dataset and raises a plain-language warning for known interactions.

See [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md) for the full architecture and design rationale, and [`docs/SRS.md`](docs/SRS.md) for the requirements specification.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Flutter (Dart, stable) + Riverpod + Hive |
| Backend | FastAPI (Python 3.11+) |
| Database | Neo4j 5 (graph) |
| Auth | JWT (Argon2 password hashing) |
| OCR | Google ML Kit (on-device) |
| AI assist | Claude/Gemini API (fuzzy match + plain-language rewrites only) |
| CI/CD | GitHub Actions + Docker Compose |

---

## Local Development Setup

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Neo4j + backend)
- [Flutter SDK](https://flutter.dev/docs/get-started/install) (stable channel)
- Python 3.11+ (optional, for running backend outside Docker)

### 1. Clone and configure

```bash
git clone <repo-url>
cd cascadex

# Copy the environment template and fill in your values
cp backend/.env.example backend/.env
```

Edit `backend/.env`:
```
NEO4J_PASSWORD=your_chosen_password
JWT_SECRET=a_long_random_secret_string
ENV=dev
```

### 2. Start the backend + Neo4j

```bash
docker compose up --build
```

- FastAPI API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474 (login: `neo4j` / your password)
- Health check: http://localhost:8000/health

### 3. Run the Flutter app

```bash
cd frontend
flutter pub get
flutter run          # physical device or emulator
# OR
flutter run -d chrome  # web preview
```

---

## Running Tests

### Backend

```bash
cd backend
pip install -r requirements.txt
pytest --tb=short -q
```

### Frontend

```bash
cd frontend
flutter test
```

---

## Project Structure

```
cascadex/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/      # Route handlers (auth, medications, scans, alerts, history)
│   │   ├── core/     # Config, security, dependency injection
│   │   ├── db/       # Neo4j session management
│   │   ├── models/   # Pydantic schemas
│   │   ├── services/ # Business logic
│   │   ├── ml/       # LLM client (Phase 05+)
│   │   └── main.py
│   ├── tests/
│   ├── data/         # DDInter/RxNorm data + fixtures
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/         # Flutter mobile app
│   ├── lib/
│   │   ├── screens/  # UI screens
│   │   ├── widgets/  # Reusable components
│   │   ├── services/ # API client, secure storage
│   │   ├── state/    # Riverpod providers
│   │   ├── theme/    # Design tokens
│   │   └── main.dart
│   └── test/
├── docs/             # SRS, Project Overview, ER Diagram
├── docker-compose.yml
├── .github/workflows/ci.yml
└── README.md
```

---

## Build Phases

| Phase | Description | Status |
|---|---|---|
| 01 | Infrastructure scaffold | ✅ Done |
| 02 | Drug data ingestion (DDInter/RxNorm) | ✅ Done |
| 03 | Auth & users (JWT + Argon2 + RBAC) | ✅ Done |
| 04 | Medication CRUD + dose logging | ⏳ Pending |
| 05 | OCR scan-to-add flow | ⏳ Pending |
| 06 | Interaction engine | ⏳ Pending |
| 07 | Alerts & notifications | ⏳ Pending |
| 08 | History, accessibility, full Flutter UI | ⏳ Pending |
| 09 | Security hardening + deployment | ⏳ Pending |

---

## Course & Academic Info

**Course:** BCSE301L – Software Engineering  
**Dataset:** DDInter 2.0 (open, CC-licensed drug interaction dataset)  
**Name normalization:** RxNorm (US National Library of Medicine)
