"""
CascadeX integration test conftest.

Provides a real Neo4j-backed AsyncClient for all Phase 04+ integration tests.

Strategy:
- Uses the real FastAPI app with real Neo4j (bolt://localhost:7687).
- All fixtures are function-scoped to avoid pytest-asyncio event_loop scope issues.
- Drug catalog is seeded per test (idempotent MERGE — fast after first run).
- User/Medication/Dose nodes are cleaned up after each test for isolation.

Environment: requires Neo4j running.
  Start with: docker compose up -d neo4j  (from cascadex/ directory)
"""

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from neo4j import AsyncGraphDatabase

# Set environment variables BEFORE importing app (config reads at import time)
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"
os.environ["JWT_SECRET"] = "cascadex_jwt_secret_dev_key_not_for_production_32chars"
os.environ["ENV"] = "test"  # disables rate limiting (see settings.rate_limit_register)
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

from app.db.neo4j_session import init_driver  # noqa: E402
from app.main import app  # noqa: E402

# ---------------------------------------------------------------------------
# Neo4j direct driver — function-scoped to avoid event_loop scope mismatch
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def neo4j_driver():
    """Direct Neo4j driver for setup/teardown — bypasses FastAPI."""
    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    await driver.verify_connectivity()
    yield driver
    await driver.close()


# ---------------------------------------------------------------------------
# Seed drug catalog (idempotent MERGE — runs per test but is fast)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def seed_drug_catalog(neo4j_driver):
    """Seed minimal drug catalog before each test (idempotent MERGE).

    Creates 4 Drug nodes + 3 brand name nodes + schema constraints.
    MERGE makes this safe to call repeatedly — no duplicates.
    """
    async with neo4j_driver.session() as session:
        # Schema constraints (idempotent — safe to call every time)
        constraints = [
            "CREATE CONSTRAINT drug_id_unique IF NOT EXISTS FOR (d:Drug) REQUIRE d.drug_id IS UNIQUE",
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
            "CREATE CONSTRAINT caregiver_id_unique IF NOT EXISTS FOR (c:Caregiver) REQUIRE c.caregiver_id IS UNIQUE",
            "CREATE CONSTRAINT med_entry_id_unique IF NOT EXISTS FOR (m:MedicationEntry) REQUIRE m.entry_id IS UNIQUE",
        ]
        for c in constraints:
            try:
                await session.run(c)
            except Exception:
                pass  # constraint already exists

        # Drug nodes (4 real drugs)
        drugs = [
            {"drug_id": "drug_war01", "generic_name": "warfarin",    "drug_class": "anticoagulant", "atc_code": "B01AA03", "default_form": "tablet", "external_source_id": "DB00682"},
            {"drug_id": "drug_asp01", "generic_name": "aspirin",     "drug_class": "analgesic",     "atc_code": "B01AC06", "default_form": "tablet", "external_source_id": "DB00945"},
            {"drug_id": "drug_ibu01", "generic_name": "ibuprofen",   "drug_class": "nsaid",         "atc_code": "M01AE01", "default_form": "tablet", "external_source_id": "DB01050"},
            {"drug_id": "drug_sim01", "generic_name": "simvastatin", "drug_class": "statin",        "atc_code": "C10AA01", "default_form": "tablet", "external_source_id": "DB00641"},
        ]
        for d in drugs:
            await session.run(
                """
                MERGE (d:Drug {drug_id: $drug_id})
                SET d.generic_name       = $generic_name,
                    d.drug_class         = $drug_class,
                    d.atc_code           = $atc_code,
                    d.default_form       = $default_form,
                    d.external_source_id = $external_source_id
                """,
                d,
            )

        # Brand names (3 brands)
        brands = [
            {"brand_name": "coumadin",  "drug_id": "drug_war01"},
            {"brand_name": "advil",     "drug_id": "drug_ibu01"},
            {"brand_name": "zocor",     "drug_id": "drug_sim01"},
        ]
        for b in brands:
            await session.run(
                """
                MATCH (d:Drug {drug_id: $drug_id})
                MERGE (bn:DrugBrandName {brand_name: $brand_name})
                MERGE (bn)-[:BRAND_OF]->(d)
                """,
                b,
            )

    yield  # run the test

    # ---------------------------------------------------------------------------
    # Teardown: delete all user-generated data, preserve Drug catalog
    # ---------------------------------------------------------------------------
    async with neo4j_driver.session() as session:
        # DETACH DELETE cascades to relationships; order avoids constraint errors
        await session.run("MATCH (l:DoseIntakeLog) DETACH DELETE l")
        await session.run("MATCH (s:DoseSchedule)  DETACH DELETE s")
        await session.run("MATCH (m:MedicationEntry) DETACH DELETE m")
        await session.run("MATCH (c:Caregiver)      DETACH DELETE c")
        await session.run("MATCH (u:User)           DETACH DELETE u")


# ---------------------------------------------------------------------------
# FastAPI AsyncClient wired to real Neo4j
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(seed_drug_catalog):  # noqa: ARG001 — dependency ensures DB is ready
    """AsyncClient connected to the FastAPI ASGI app with a live Neo4j backend."""
    await init_driver()  # ensure the FastAPI-level driver is initialised
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Shared helper used by multiple test modules
# ---------------------------------------------------------------------------

async def register_and_login(client: AsyncClient, suffix: str = "") -> dict:
    """Register a unique user and return Bearer auth headers.

    Uses a random UUID suffix so multiple calls within one test don't collide.
    Login body uses JSON (LoginRequest schema — NOT OAuth2 form data).
    """
    import uuid
    uid = uuid.uuid4().hex[:10]
    email = f"test_{uid}{suffix}@cascadex-test.com"

    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Test User {uid}",
            "date_of_birth": "1960-03-15",
            "email": email,
            "password": "Secure_Pass_123!",
        },
    )
    assert reg.status_code == 201, f"Register failed [{reg.status_code}]: {reg.text}"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email_or_phone": email, "password": "Secure_Pass_123!"},
    )
    assert login.status_code == 200, f"Login failed [{login.status_code}]: {login.text}"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}
