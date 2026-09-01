# CascadeX — Grader / Demo Walkthrough Script

> **For:** Course graders, demo viewers, and interviewers.
> **Time estimate:** ~12–15 minutes end-to-end.
> **Prerequisites:** Docker Desktop installed and running; the repo cloned.

---

## Prerequisites Checklist

- [ ] Docker Desktop is running
- [ ] Repository is cloned: `git clone <repo-url> && cd cascadex`
- [ ] You have a `.env` file in `backend/` (copy from `.env.example`)
- [ ] Optionally: `GEMINI_API_KEY` set in `.env` for LLM features (fuzzy matching + plain-language rewrites)

---

## Step 1 — Start the Full Stack

```bash
# From the repo root (cascadex/)
docker compose up -d
```

Wait ~30 seconds for Neo4j to become healthy (check with `docker compose ps`).

Expected: all services show `Up (healthy)`.

---

## Step 2 — Seed the Drug Database (first run only)

```bash
docker compose --profile seed up seeder
```

Expected output: logs showing `Import complete — version=ddinter-fixture-v1 drugs=32 interactions=16`.

This is **idempotent** — safe to re-run; uses `MERGE` not `CREATE`.

---

## Step 3 — Verify the Stack is Ready

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "neo4j": "connected",
  "app_version": "1.0.0",
  "drug_count": 32,
  "llm_mode": "active",
  "dataset_version": "ddinter-fixture-v1"
}
```

> **`drug_count` must be ≥ 32** for the demo to work.
> **`llm_mode`** is `"active"` when `GEMINI_API_KEY` is set, `"stub"` otherwise.

---

## Step 4 — Register a User

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Demo Patient",
    "date_of_birth": "1955-06-15",
    "email": "demo@cascadex.app",
    "password": "Demo_Pass_123!"
  }' | jq
```

Expected: `201 Created` with `user_id`.

---

## Step 5 — Log In and Get Access Token

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email_or_phone": "demo@cascadex.app", "password": "Demo_Pass_123!"}' \
  | jq -r '.access_token')

echo "Token: $TOKEN"
```

Expected: a non-empty JWT string.

---

## Step 6 — Add First Medication (Warfarin)

```bash
curl -s -X POST http://localhost:8000/api/v1/medications/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "drug_id": "D001",
    "drug_name": "warfarin",
    "start_date": "2024-01-01",
    "indication": "atrial fibrillation",
    "input_method": "manual"
  }' | jq
```

Expected: `201 Created` with `entry_id`.

---

## Step 7 — Add an Interacting Drug (Aspirin — major DDI)

```bash
curl -s -X POST http://localhost:8000/api/v1/medications/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "drug_id": "D002",
    "drug_name": "aspirin",
    "start_date": "2024-06-01",
    "indication": "pain",
    "input_method": "manual"
  }' | jq
```

Expected: `201 Created`.

---

## Step 8 — Check Drug Interactions → See the Alert

```bash
curl -s http://localhost:8000/api/v1/medications/interactions \
  -H "Authorization: Bearer $TOKEN" | jq
```

Expected response contains an interaction with:
- `severity`: `"major"`
- `drug_a_name`: `"warfarin"`, `drug_b_name`: `"aspirin"`
- `mechanism`: DDInter text describing anticoagulation risk
- `plain_language`: plain-English rewrite (only if `llm_mode: active`)
- `is_clean`: `false`

> ⚠️ The response also contains the disclaimer: this is not a substitute for pharmacist/doctor advice.

---

## Step 9 — Acknowledge the Alert

```bash
# First get the alert_id from the previous response or list alerts
ALERTS=$(curl -s http://localhost:8000/api/v1/alerts/ \
  -H "Authorization: Bearer $TOKEN")
ALERT_ID=$(echo $ALERTS | jq -r '.alerts[0].alert_id')

curl -s -X PATCH http://localhost:8000/api/v1/alerts/${ALERT_ID}/acknowledge \
  -H "Authorization: Bearer $TOKEN" | jq
```

Expected: `200 OK` with `acknowledged: true`.

---

## Step 10 — OCR Scan Demo (optional — tests the fuzzy LLM match)

```bash
# Submit noisy OCR text as if from a prescription label
curl -s -X POST http://localhost:8000/api/v1/scans \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ocr_text": "WARFRIN 5mg TABLET take once daily"}' | jq
```

Expected: `matched_drug.generic_name: "warfarin"`, `match_method: "exact_generic"` or `"fuzzy_llm"` depending on LLM mode.

---

## Step 11 — Interaction History + Export

```bash
# Get interaction history
curl -s http://localhost:8000/api/v1/history/ \
  -H "Authorization: Bearer $TOKEN" | jq

# Export as PDF (returns binary — save to file)
curl -s http://localhost:8000/api/v1/history/export/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -o /tmp/cascadex_history.pdf

echo "PDF saved. Size: $(wc -c < /tmp/cascadex_history.pdf) bytes"
```

Expected: History JSON with interaction entries; PDF file > 1KB.

---

## Step 12 — View Full API Documentation

Open in browser: [http://localhost:8000/docs](http://localhost:8000/docs)

The Swagger UI shows all endpoints, schemas, and example responses. The ReDoc view is available at `/redoc`.

---

## Step 13 — Run the Test Suite (optional for grader)

```bash
cd backend
pip install -r requirements.txt
pytest --tb=short -q
```

Expected: All tests pass. Any test marked `[SKIPPED]` with "Neo4j not running" is expected in environments without Docker.

---

## Stopping the Stack

```bash
docker compose down
```

To also remove Neo4j data volume (full reset):
```bash
docker compose down -v
```

---

## Key Demo Talking Points

| Feature | Where to show it |
|---|---|
| Drug-drug interaction check (major) | Step 8 — warfarin + aspirin severity `"major"` |
| Unmatched drug safety (NFR-4) | POST `/medications/` with `drug_id: "FAKE_ID"` → 400 + `drug_unrecognized` |
| LLM plain-language rewrite | Step 8 — `plain_language` field (active LLM mode) |
| OCR fuzzy matching | Step 10 — typo "WARFRIN" resolved to "warfarin" |
| Alert acknowledge flow | Step 9 — PATCH `/alerts/{id}/acknowledge` |
| PDF export | Step 11 — binary PDF response |
| Field encryption | Scan record's `ocr_text` stored as Fernet ciphertext in Neo4j |
| Structured PII-free logs | `docker compose logs backend` — only user_ids, not names/drugs |
