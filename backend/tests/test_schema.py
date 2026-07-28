"""
Tests for backend/app/db/schema.py — ensure_constraints.

These tests run against a REAL Neo4j instance via the Docker Compose stack.

To run locally (with Docker running):
    cd backend
    pytest tests/test_schema.py -v
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def neo4j_session():
    """Provide a live Neo4j session (function-scoped, fresh driver per test)."""
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
    try:
        async with driver.session() as session:
            yield session
    finally:
        await driver.close()


async def test_ensure_constraints_is_idempotent(neo4j_session):
    """Running ensure_constraints twice must not raise an error."""
    from app.db.schema import ensure_constraints

    # First run
    await ensure_constraints(neo4j_session)
    # Second run — must be silent (IF NOT EXISTS guards)
    await ensure_constraints(neo4j_session)


async def test_drug_unique_constraint_exists(neo4j_session):
    """After ensure_constraints, a uniqueness constraint on Drug.drug_id exists."""
    from app.db.schema import ensure_constraints

    await ensure_constraints(neo4j_session)

    result = await neo4j_session.run("SHOW CONSTRAINTS")
    records = await result.data()

    constraint_names = [r.get("name", "") for r in records]
    assert any("drug_id" in name.lower() for name in constraint_names), (
        f"drug_id_unique constraint not found. Constraints: {constraint_names}"
    )


async def test_interaction_unique_constraint_exists(neo4j_session):
    """After ensure_constraints, a uniqueness constraint on interaction_id exists."""
    from app.db.schema import ensure_constraints

    await ensure_constraints(neo4j_session)

    result = await neo4j_session.run("SHOW CONSTRAINTS")
    records = await result.data()

    constraint_names = [r.get("name", "") for r in records]
    assert any("interaction_id" in name.lower() for name in constraint_names), (
        f"interaction_id_unique constraint not found. Constraints: {constraint_names}"
    )


async def test_dataset_version_constraint_exists(neo4j_session):
    """After ensure_constraints, a uniqueness constraint on DatasetVersion.version exists."""
    from app.db.schema import ensure_constraints

    await ensure_constraints(neo4j_session)

    result = await neo4j_session.run("SHOW CONSTRAINTS")
    records = await result.data()

    constraint_names = [r.get("name", "") for r in records]
    assert any("dataset_version" in name.lower() for name in constraint_names), (
        f"dataset_version_unique constraint not found. Constraints: {constraint_names}"
    )
