"""
Tests for backend/data/seed_ddinter.py — the DDInter import job.

All tests that write to Neo4j require a live instance (Docker Compose).
The dry-run test does NOT need Neo4j — it only validates CSV parsing.

To run locally (with Docker running):
    cd backend
    pytest tests/test_seed_ddinter.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

FIXTURES_DIR = Path(__file__).parent.parent / "data" / "fixtures"
TEST_VERSION = "pytest-test-v1"

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def clean_neo4j():
    """Provide a Neo4j session and wipe test data before/after each test."""
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
    async with driver.session() as session:
        # Tear down test nodes from previous runs
        await session.run(
            "MATCH (n) WHERE n.dataset_version = $v DETACH DELETE n",
            v=TEST_VERSION,
        )
        await session.run(
            "MATCH (v:DatasetVersion {version: $v}) DETACH DELETE v",
            v=TEST_VERSION,
        )
    try:
        async with driver.session() as session:
            yield session
    finally:
        # Cleanup after test
        async with driver.session() as cleanup_session:
            await cleanup_session.run(
                "MATCH (n) WHERE n.dataset_version = $v DETACH DELETE n",
                v=TEST_VERSION,
            )
            await cleanup_session.run(
                "MATCH (v:DatasetVersion {version: $v}) DETACH DELETE v",
                v=TEST_VERSION,
            )
        await driver.close()


def test_dry_run_writes_nothing():
    """Dry-run mode parses and validates CSVs without connecting to Neo4j."""
    import asyncio

    from data.seed_ddinter import run_import

    # Use obviously invalid Neo4j URI — if it tries to connect it will fail fast
    async def _run():
        await run_import(
            neo4j_uri="bolt://127.0.0.1:19999",  # nothing listening here
            neo4j_user="x",
            neo4j_password="x",
            source_dir=FIXTURES_DIR,
            version="dry-run-test",
            dry_run=True,
        )

    # Should complete without raising (no connection attempt in dry-run)
    asyncio.run(_run())


async def test_import_creates_expected_node_counts(clean_neo4j):
    """Importing the fixture CSVs creates Drug, DrugBrandName, and DatasetVersion nodes."""
    from data.seed_ddinter import run_import

    await run_import(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
        source_dir=FIXTURES_DIR,
        version=TEST_VERSION,
        dry_run=False,
    )

    # Check Drug count
    result = await clean_neo4j.run(
        "MATCH (d:Drug {dataset_version: $v}) RETURN count(d) AS cnt",
        v=TEST_VERSION,
    )
    record = await result.single()
    assert record["cnt"] == 32, f"Expected 32 Drug nodes, got {record['cnt']}"

    # Check DatasetVersion node exists
    result = await clean_neo4j.run(
        "MATCH (v:DatasetVersion {version: $v}) RETURN v.drug_count AS dc",
        v=TEST_VERSION,
    )
    record = await result.single()
    assert record is not None, "DatasetVersion node not created"
    assert record["dc"] == 32

    # Check INTERACTS_WITH edge count
    result = await clean_neo4j.run(
        "MATCH ()-[r:INTERACTS_WITH]->() RETURN count(r) AS cnt"
    )
    record = await result.single()
    assert record["cnt"] >= 16, f"Expected at least 16 interaction edges, got {record['cnt']}"


async def test_re_import_same_version_is_idempotent(clean_neo4j):
    """Running the import twice with the same version must not duplicate nodes."""
    from data.seed_ddinter import run_import

    kwargs = dict(
        neo4j_uri=NEO4J_URI,
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
        source_dir=FIXTURES_DIR,
        version=TEST_VERSION,
        dry_run=False,
    )

    await run_import(**kwargs)
    await run_import(**kwargs)  # second run — idempotent

    result = await clean_neo4j.run(
        "MATCH (d:Drug {dataset_version: $v}) RETURN count(d) AS cnt",
        v=TEST_VERSION,
    )
    record = await result.single()
    assert record["cnt"] == 32, (
        f"Idempotency broken: expected 32 Drug nodes after 2 imports, got {record['cnt']}"
    )
