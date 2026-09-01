"""
tests/perf/test_interaction_engine_perf.py — Phase 09 / NFR-3

Performance budget test for the interaction engine.

NFR-3 (SRS §4.1): The pairwise drug-drug interaction check for a user with
~20 active medications must complete server-side in ≤ 500ms at p95.

Strategy:
  - Use the 20 drugs from the DDInter fixture that have the most edges
    (all D001–D020 are in the fixture), giving C(20,2) = 190 pairs to check.
  - Run check_pairs() N=30 times against a live Neo4j session.
  - Compute p95 latency across all runs.
  - FAIL (not warn) if p95 > 500ms.

This test requires Neo4j to be running.  It is automatically skipped when
the database is not reachable (same skip strategy as other integration tests).
"""

from __future__ import annotations

import statistics
import time

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

# ---------------------------------------------------------------------------
# 20-drug ID list (worst-case realistic active medication list per SRS §4.1)
# All 20 are present in the DDInter fixture (drugs_fixture.csv).
# ---------------------------------------------------------------------------
_PERF_20_DRUG_IDS = [
    "D001",  # warfarin
    "D002",  # aspirin
    "D003",  # metformin
    "D004",  # lisinopril
    "D005",  # atorvastatin
    "D006",  # amiodarone
    "D007",  # fluoxetine
    "D008",  # metoprolol
    "D009",  # omeprazole
    "D010",  # ciprofloxacin
    "D011",  # simvastatin
    "D012",  # digoxin
    "D013",  # clopidogrel
    "D014",  # phenytoin
    "D015",  # rifampicin
    "D016",  # amlodipine
    "D017",  # methotrexate
    "D018",  # lithium
    "D019",  # sildenafil
    "D020",  # nitroglycerin
]

_N_RUNS = 30          # number of repeated calls for p95 computation
_BUDGET_MS = 500.0    # NFR-3 budget


@pytest_asyncio.fixture
async def perf_neo4j_session(seed_drug_catalog):  # noqa: ARG001
    """Open a direct Neo4j async session for performance timing.

    Reuses the autouse seed_drug_catalog to ensure all 20 drugs + interactions
    are present before timing begins.
    """
    import os
    driver = AsyncGraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "password"),
        ),
    )
    try:
        await driver.verify_connectivity()
    except Exception:
        await driver.close()
        pytest.skip("Neo4j not running — skipping performance test")

    async with driver.session() as session:
        yield session

    await driver.close()


@pytest.mark.asyncio
async def test_interaction_engine_p95_under_500ms(perf_neo4j_session) -> None:
    """NFR-3: p95 latency for 20-drug check_pairs must be ≤ 500ms.

    Fails the test (not just warns) if the budget is exceeded, ensuring this
    is enforced as a hard requirement, not a soft advisory.
    """
    from app.services.interaction_engine import check_pairs

    latencies: list[float] = []

    for _ in range(_N_RUNS):
        t0 = time.perf_counter()
        result = await check_pairs(
            session=perf_neo4j_session,
            drug_ids=_PERF_20_DRUG_IDS,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)
        # Sanity check: result must be a valid InteractionCheckResult
        assert result is not None

    # Compute p95
    latencies.sort()
    p95_idx = int(len(latencies) * 0.95)
    p95_ms = latencies[min(p95_idx, len(latencies) - 1)]
    p50_ms = statistics.median(latencies)
    p_max_ms = max(latencies)

    print(
        f"\n[perf] 20-drug check_pairs — N={_N_RUNS} runs\n"
        f"  p50 = {p50_ms:.1f}ms\n"
        f"  p95 = {p95_ms:.1f}ms\n"
        f"  max = {p_max_ms:.1f}ms\n"
        f"  budget = {_BUDGET_MS}ms"
    )

    assert p95_ms <= _BUDGET_MS, (
        f"NFR-3 VIOLATED: p95 latency {p95_ms:.1f}ms exceeds {_BUDGET_MS}ms budget "
        f"for a 20-drug interaction check. "
        f"(p50={p50_ms:.1f}ms, max={p_max_ms:.1f}ms over {_N_RUNS} runs)"
    )
