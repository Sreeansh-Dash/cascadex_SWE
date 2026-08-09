"""
CascadeX Neo4j schema — constraints and indexes.

Run `ensure_constraints(session)` once at startup (or before import) to
guarantee uniqueness and fast lookup on all core node labels.

All Cypher here uses ``IF NOT EXISTS`` so the function is fully idempotent:
calling it multiple times on the same database is safe and produces no errors.
"""

from neo4j import AsyncSession


async def ensure_constraints(session: AsyncSession) -> None:
    """Create all uniqueness constraints and indexes for CascadeX nodes.

    Idempotent — safe to run on an already-configured database.  Every
    statement uses ``CREATE CONSTRAINT … IF NOT EXISTS`` or
    ``CREATE INDEX … IF NOT EXISTS``.

    Args:
        session: An open Neo4j async session.
    """
    statements = [
        # ── Uniqueness constraints ──────────────────────────────────────────
        # Drug
        """
        CREATE CONSTRAINT drug_id_unique IF NOT EXISTS
        FOR (d:Drug) REQUIRE d.drug_id IS UNIQUE
        """,
        # DrugBrandName
        """
        CREATE CONSTRAINT brand_id_unique IF NOT EXISTS
        FOR (b:DrugBrandName) REQUIRE b.brand_id IS UNIQUE
        """,
        # DrugInteraction
        """
        CREATE CONSTRAINT interaction_id_unique IF NOT EXISTS
        FOR (i:DrugInteraction) REQUIRE i.interaction_id IS UNIQUE
        """,
        # DatasetVersion
        """
        CREATE CONSTRAINT dataset_version_unique IF NOT EXISTS
        FOR (v:DatasetVersion) REQUIRE v.version IS UNIQUE
        """,

        # ── Lookup indexes ──────────────────────────────────────────────────
        # Drug.generic_name — used heavily by drug_normalizer and catalog search
        """
        CREATE INDEX drug_generic_name IF NOT EXISTS
        FOR (d:Drug) ON (d.generic_name)
        """,
        # DrugBrandName.brand_name — used by brand → generic resolution
        """
        CREATE INDEX brand_name IF NOT EXISTS
        FOR (b:DrugBrandName) ON (b.brand_name)
        """,
        # ScanRecord — Phase 05 OCR scan audit trail
        """
        CREATE CONSTRAINT scan_id_unique IF NOT EXISTS
        FOR (s:ScanRecord) REQUIRE s.scan_id IS UNIQUE
        """,
    ]

    for stmt in statements:
        await session.run(stmt.strip())
