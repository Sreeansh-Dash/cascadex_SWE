"""
CascadeX integration test conftest.

Provides a real Neo4j-backed AsyncClient for all Phase 04+ integration tests.

Strategy:
- Uses the real FastAPI app with real Neo4j (bolt://localhost:7687).
- All fixtures are function-scoped to avoid pytest-asyncio event_loop scope issues.
- Drug catalog is seeded per test (idempotent MERGE - fast after first run).
- User/Medication/Dose/Scan/Alert nodes are cleaned up after each test for isolation.

Phase 06 additions:
- seed_drug_catalog seeds the FULL DDInter fixture drug list (not just 4 drugs).
- seed_drug_catalog also seeds known INTERACTS_WITH edges for interaction engine tests.
- Teardown now also cleans InteractionAlert nodes.

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
    """Direct Neo4j driver for setup/teardown - bypasses FastAPI.

    Skips gracefully when Neo4j is not running (unit tests don't need it).
    """
    import pytest
    from neo4j.exceptions import ServiceUnavailable
    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    try:
        await driver.verify_connectivity()
    except ServiceUnavailable:
        await driver.close()
        pytest.skip("Neo4j not running - skipping integration test")
    yield driver
    await driver.close()


# ---------------------------------------------------------------------------
# Seed drug catalog (idempotent MERGE — runs per test but is fast)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def seed_drug_catalog(neo4j_driver):
    """Seed full DDInter drug catalog + known interaction edges before each test.

    Idempotent (MERGE) — safe to call repeatedly.  Seeds:
    - All 32 drugs from drugs_fixture.csv
    - Brand name nodes for the original 4 Phase 04 drugs
    - Key INTERACTS_WITH edges for Phase 06 interaction engine tests

    Auto-skipped when neo4j_driver skips (unit tests without Neo4j).
    """
    async with neo4j_driver.session() as session:
        # Schema constraints (idempotent)
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

        # Phase 06: wipe ALL INTERACTS_WITH edges before re-seeding.
        # This prevents stale relationships from prior seed_ddinter.py runs
        # (which may have seeded edges without interaction_id keys or in both
        # directions) from causing the engine tests to find duplicate pairs.
        # Drug nodes and all other nodes are preserved.
        await session.run("MATCH ()-[r:INTERACTS_WITH]->() DELETE r")

        # Full DDInter drug catalog (32 drugs)
        drugs = [
            {"drug_id": "D001",    "generic_name": "warfarin",        "drug_class": "anticoagulant",               "atc_code": "B01AA03", "default_form": "tablet",  "external_source_id": "DDI-001"},
            {"drug_id": "D002",    "generic_name": "aspirin",         "drug_class": "antiplatelet",                "atc_code": "B01AC06", "default_form": "tablet",  "external_source_id": "DDI-002"},
            {"drug_id": "D003",    "generic_name": "metformin",       "drug_class": "biguanide antidiabetic",      "atc_code": "A10BA02", "default_form": "tablet",  "external_source_id": "DDI-003"},
            {"drug_id": "D004",    "generic_name": "lisinopril",      "drug_class": "ACE inhibitor",              "atc_code": "C09AA03", "default_form": "tablet",  "external_source_id": "DDI-004"},
            {"drug_id": "D005",    "generic_name": "atorvastatin",    "drug_class": "statin",                     "atc_code": "C10AA05", "default_form": "tablet",  "external_source_id": "DDI-005"},
            {"drug_id": "D006",    "generic_name": "amiodarone",      "drug_class": "antiarrhythmic",             "atc_code": "C01BD01", "default_form": "tablet",  "external_source_id": "DDI-006"},
            {"drug_id": "D007",    "generic_name": "fluoxetine",      "drug_class": "SSRI antidepressant",        "atc_code": "N06AB03", "default_form": "capsule", "external_source_id": "DDI-007"},
            {"drug_id": "D008",    "generic_name": "metoprolol",      "drug_class": "beta-blocker",               "atc_code": "C07AB02", "default_form": "tablet",  "external_source_id": "DDI-008"},
            {"drug_id": "D009",    "generic_name": "omeprazole",      "drug_class": "proton pump inhibitor",      "atc_code": "A02BC01", "default_form": "capsule", "external_source_id": "DDI-009"},
            {"drug_id": "D010",    "generic_name": "ciprofloxacin",   "drug_class": "fluoroquinolone antibiotic", "atc_code": "J01MA02", "default_form": "tablet",  "external_source_id": "DDI-010"},
            {"drug_id": "D011",    "generic_name": "simvastatin",     "drug_class": "statin",                     "atc_code": "C10AA01", "default_form": "tablet",  "external_source_id": "DDI-011"},
            {"drug_id": "D012",    "generic_name": "digoxin",         "drug_class": "cardiac glycoside",          "atc_code": "C01AA05", "default_form": "tablet",  "external_source_id": "DDI-012"},
            {"drug_id": "D013",    "generic_name": "clopidogrel",     "drug_class": "antiplatelet",               "atc_code": "B01AC04", "default_form": "tablet",  "external_source_id": "DDI-013"},
            {"drug_id": "D014",    "generic_name": "phenytoin",       "drug_class": "antiepileptic",              "atc_code": "N03AB02", "default_form": "capsule", "external_source_id": "DDI-014"},
            {"drug_id": "D015",    "generic_name": "rifampicin",      "drug_class": "rifamycin antibiotic",       "atc_code": "J04AB02", "default_form": "capsule", "external_source_id": "DDI-015"},
            {"drug_id": "D016",    "generic_name": "amlodipine",      "drug_class": "calcium channel blocker",    "atc_code": "C08CA01", "default_form": "tablet",  "external_source_id": "DDI-016"},
            {"drug_id": "D017",    "generic_name": "methotrexate",    "drug_class": "antimetabolite",             "atc_code": "L04AX03", "default_form": "tablet",  "external_source_id": "DDI-017"},
            {"drug_id": "D018",    "generic_name": "lithium",         "drug_class": "mood stabilizer",            "atc_code": "N05AN01", "default_form": "tablet",  "external_source_id": "DDI-018"},
            {"drug_id": "D019",    "generic_name": "sildenafil",      "drug_class": "PDE5 inhibitor",             "atc_code": "G04BE03", "default_form": "tablet",  "external_source_id": "DDI-019"},
            {"drug_id": "D020",    "generic_name": "nitroglycerin",   "drug_class": "nitrate",                    "atc_code": "C01DA02", "default_form": "tablet",  "external_source_id": "DDI-020"},
            {"drug_id": "D021",    "generic_name": "spironolactone",  "drug_class": "potassium-sparing diuretic", "atc_code": "C03DA01", "default_form": "tablet",  "external_source_id": "DDI-021"},
            {"drug_id": "D022",    "generic_name": "furosemide",      "drug_class": "loop diuretic",              "atc_code": "C03CA01", "default_form": "tablet",  "external_source_id": "DDI-022"},
            {"drug_id": "D023",    "generic_name": "tramadol",        "drug_class": "opioid analgesic",           "atc_code": "N02AX02", "default_form": "capsule", "external_source_id": "DDI-023"},
            {"drug_id": "D024",    "generic_name": "sertraline",      "drug_class": "SSRI antidepressant",        "atc_code": "N06AB06", "default_form": "tablet",  "external_source_id": "DDI-024"},
            {"drug_id": "D025",    "generic_name": "ibuprofen",       "drug_class": "NSAID",                      "atc_code": "M01AE01", "default_form": "tablet",  "external_source_id": "DDI-025"},
            {"drug_id": "D026",    "generic_name": "clarithromycin",  "drug_class": "macrolide antibiotic",       "atc_code": "J01FA09", "default_form": "tablet",  "external_source_id": "DDI-026"},
            {"drug_id": "D027",    "generic_name": "carbamazepine",   "drug_class": "antiepileptic",              "atc_code": "N03AF01", "default_form": "tablet",  "external_source_id": "DDI-027"},
            {"drug_id": "D028",    "generic_name": "verapamil",       "drug_class": "calcium channel blocker",    "atc_code": "C08DA01", "default_form": "tablet",  "external_source_id": "DDI-028"},
            {"drug_id": "D029",    "generic_name": "ketoconazole",    "drug_class": "azole antifungal",           "atc_code": "J02AB02", "default_form": "tablet",  "external_source_id": "DDI-029"},
            {"drug_id": "D030",    "generic_name": "levodopa",        "drug_class": "dopaminergic",               "atc_code": "N04BA01", "default_form": "tablet",  "external_source_id": "DDI-030"},
            {"drug_id": "D031",    "generic_name": "theophylline",    "drug_class": "xanthine bronchodilator",    "atc_code": "R03DA04", "default_form": "tablet",  "external_source_id": "DDI-031"},
            {"drug_id": "D032",    "generic_name": "azathioprine",    "drug_class": "immunosuppressant",          "atc_code": "L04AX01", "default_form": "tablet",  "external_source_id": "DDI-032"},
            # Legacy drug_ids used by Phase 04 tests (kept for backward compat)
            {"drug_id": "drug_war01", "generic_name": "warfarin",    "drug_class": "anticoagulant", "atc_code": "B01AA03", "default_form": "tablet",  "external_source_id": "DB00682"},
            {"drug_id": "drug_asp01", "generic_name": "aspirin",     "drug_class": "analgesic",     "atc_code": "B01AC06", "default_form": "tablet",  "external_source_id": "DB00945"},
            {"drug_id": "drug_ibu01", "generic_name": "ibuprofen",   "drug_class": "nsaid",         "atc_code": "M01AE01", "default_form": "tablet",  "external_source_id": "DB01050"},
            {"drug_id": "drug_sim01", "generic_name": "simvastatin", "drug_class": "statin",        "atc_code": "C10AA01", "default_form": "tablet",  "external_source_id": "DB00641"},
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

        # Brand names (Phase 04 legacy brands)
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

        # Phase 06: INTERACTS_WITH edges — mirroring the DDInter fixture
        # These are the ground-truth pairs used in test_interaction_engine_core.py
        interactions = [
            # Major interactions
            {"a": "D001", "b": "D002", "severity": "major",
             "mechanism": "Additive anticoagulation and antiplatelet effects dramatically increase hemorrhage risk. Warfarin inhibits vitamin K-dependent clotting factors; aspirin impairs platelet aggregation and causes gastric mucosal damage.",
             "management_advice": "Avoid combination unless explicitly directed by a physician. If co-administration is necessary monitor INR closely and watch for signs of bleeding.",
             "source": "DDInter_2.0", "interaction_id": "INT001"},
            {"a": "D001", "b": "D006", "severity": "major",
             "mechanism": "Amiodarone inhibits CYP2C9 reducing warfarin clearance by up to 50% leading to markedly elevated INR and bleeding risk.",
             "management_advice": "Reduce warfarin dose by 30-50% when starting amiodarone. Monitor INR weekly for at least 2 months then monthly.",
             "source": "DDInter_2.0", "interaction_id": "INT002"},
            {"a": "D019", "b": "D020", "severity": "major",
             "mechanism": "PDE5 inhibitors potentiate the vasodilatory effect of nitrates causing severe unpredictable hypotension that can be life-threatening.",
             "management_advice": "Combination is contraindicated. Do not use sildenafil within 24 hours of nitrate administration.",
             "source": "DDInter_2.0", "interaction_id": "INT003"},
            {"a": "D026", "b": "D011", "severity": "major",
             "mechanism": "Clarithromycin strongly inhibits CYP3A4 raising simvastatin plasma levels 10-fold greatly increasing the risk of myopathy and rhabdomyolysis.",
             "management_advice": "Suspend simvastatin therapy during clarithromycin course. Restart simvastatin 5 days after completing the antibiotic.",
             "source": "DDInter_2.0", "interaction_id": "INT005"},
            # Moderate interactions
            {"a": "D007", "b": "D023", "severity": "moderate",
             "mechanism": "Both fluoxetine and tramadol increase central serotonergic activity. Co-administration raises the risk of serotonin syndrome.",
             "management_advice": "Use with caution. Monitor for agitation hyperthermia rapid heart rate and tremor. Reduce doses if combination is unavoidable.",
             "source": "DDInter_2.0", "interaction_id": "INT007"},
            {"a": "D008", "b": "D028", "severity": "moderate",
             "mechanism": "Both metoprolol and verapamil slow AV node conduction. Their combination can cause additive bradycardia heart block and reduced cardiac output.",
             "management_advice": "Use with extreme caution if at all. Monitor heart rate and PR interval. Avoid IV verapamil in patients on beta-blockers.",
             "source": "DDInter_2.0", "interaction_id": "INT008"},
            {"a": "D003", "b": "D004", "severity": "minor",
             "mechanism": "ACE inhibitors can increase insulin sensitivity in type 2 diabetics on metformin leading to a slightly increased risk of hypoglycemia.",
             "management_advice": "Monitor blood glucose more frequently when starting lisinopril. Patient education on hypoglycemia symptoms.",
             "source": "DDInter_2.0", "interaction_id": "INT014"},
            # Minor interactions
            {"a": "D001", "b": "D009", "severity": "minor",
             "mechanism": "Omeprazole inhibits CYP2C19 which has a minor role in S-warfarin metabolism. Effect on INR is generally small but may be clinically relevant in sensitive patients.",
             "management_advice": "Recheck INR 1-2 weeks after starting omeprazole. Dose adjustment of warfarin is rarely needed but monitor.",
             "source": "DDInter_2.0", "interaction_id": "INT013"},
            {"a": "D005", "b": "D016", "severity": "minor",
             "mechanism": "Both atorvastatin and amlodipine are CYP3A4 substrates. Amlodipine mildly increases atorvastatin exposure by 18%. Effect is generally clinically insignificant at standard doses.",
             "management_advice": "No routine dose adjustment needed. Use clinical judgment if highest atorvastatin doses are used.",
             "source": "DDInter_2.0", "interaction_id": "INT015"},
        ]
        for ix in interactions:
            await session.run(
                """
                MATCH (a:Drug {drug_id: $a})
                MATCH (b:Drug {drug_id: $b})
                MERGE (a)-[r:INTERACTS_WITH {interaction_id: $interaction_id}]->(b)
                SET r.severity          = $severity,
                    r.mechanism         = $mechanism,
                    r.management_advice = $management_advice,
                    r.source            = $source
                """,
                ix,
            )

    yield  # run the test

    # ---------------------------------------------------------------------------
    # Teardown: delete all user-generated data, preserve Drug catalog
    # ---------------------------------------------------------------------------
    async with neo4j_driver.session() as session:
        # DETACH DELETE cascades to relationships; order avoids constraint errors
        await session.run("MATCH (a:InteractionAlert) DETACH DELETE a")
        await session.run("MATCH (s:ScanRecord)   DETACH DELETE s")
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
# Shared helpers — fixtures for Phase 05+ tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def auth_factory(client):
    """Return a coroutine factory that registers+logs in a unique user.

    For Phase 05+ tests that want a fixture-injected helper::

        async def test_something(client, auth_factory):
            headers = await auth_factory(suffix="_foo")
    """
    async def _factory(suffix: str = "") -> dict:
        return await register_and_login(client, suffix=suffix)

    return _factory


@pytest_asyncio.fixture
async def seed_drug():
    """Return a DrugRead for the seeded warfarin drug (already in DB via autouse fixture)."""
    from app.models.drug import DrugRead
    return DrugRead(
        drug_id="drug_war01",
        generic_name="warfarin",
        drug_class="anticoagulant",
        atc_code="B01AA03",
        default_form="tablet",
        external_source_id="DB00682",
    )


# ---------------------------------------------------------------------------
# Standalone helper — imported by ALL test modules (Phase 04+)
# ---------------------------------------------------------------------------


async def register_and_login(client: AsyncClient, suffix: str = "") -> dict:
    """Register a unique user and return Bearer auth headers.

    Uses a random UUID so multiple calls per test never collide.
    Imported directly by test modules; also called inside the auth_factory fixture.
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
