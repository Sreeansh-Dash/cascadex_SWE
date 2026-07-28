"""
CascadeX DDInter/RxNorm data import job.

Usage
-----
Run against the fixture dataset (for CI / local dev)::

    python -m data.seed_ddinter \\
        --source backend/data/fixtures \\
        --version test-v1

Run against a real DDInter export (columns must match the fixture schema)::

    python -m data.seed_ddinter \\
        --source /path/to/ddinter_export \\
        --version ddinter-2.0-2024-01

Dry-run mode (parse + validate, no writes)::

    python -m data.seed_ddinter \\
        --source backend/data/fixtures \\
        --version test-v1 \\
        --dry-run

Expected CSV columns
--------------------
drugs_fixture.csv (or drugs.csv):
    drug_id, generic_name, drug_class, atc_code, default_form,
    external_source_id

brand_names_fixture.csv (or brand_names.csv):
    brand_id, drug_id, brand_name, manufacturer

interactions_fixture.csv (or interactions.csv):
    interaction_id, drug_a_id, drug_b_id, severity, mechanism,
    management_advice, source

Design notes
------------
- All Cypher queries use MERGE (not CREATE) — re-running with the same
  ``--version`` is fully idempotent; node/edge counts do not change.
- Interaction edges are stored as DIRECTED (drug_a → drug_b) but the
  interaction engine (Phase 06) queries them as UNDIRECTED.  This avoids
  duplicate edges while still catching both orderings at query time.
- A ``DatasetVersion`` node is MERGE'd on every run so the /health endpoint
  and the About-the-data screen (Phase 08) can report exactly which dataset
  is loaded.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from neo4j import AsyncGraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSV discovery helpers
# ---------------------------------------------------------------------------

def _find_csv(source_dir: Path, *candidates: str) -> Path:
    """Return the first matching CSV filename inside *source_dir*.

    Raises FileNotFoundError if none of the candidate names exist.
    """
    for name in candidates:
        p = source_dir / name
        if p.exists():
            return p
    raise FileNotFoundError(
        f"None of {list(candidates)} found in {source_dir}"
    )


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# Import functions
# ---------------------------------------------------------------------------

async def import_drugs(session, rows: list[dict], version: str, dry_run: bool) -> int:
    """MERGE Drug nodes from CSV rows.

    Returns:
        Number of rows processed.
    """
    if dry_run:
        logger.info("[dry-run] Would import %d Drug nodes", len(rows))
        return len(rows)

    cypher = """
    UNWIND $rows AS row
    MERGE (d:Drug {drug_id: row.drug_id})
    SET d.generic_name      = toLower(trim(row.generic_name)),
        d.drug_class         = row.drug_class,
        d.atc_code           = row.atc_code,
        d.default_form       = row.default_form,
        d.external_source_id = row.external_source_id,
        d.dataset_version    = $version
    """
    await session.run(cypher, rows=rows, version=version)
    logger.info("Imported/updated %d Drug nodes", len(rows))
    return len(rows)


async def import_brands(session, rows: list[dict], dry_run: bool) -> int:
    """MERGE DrugBrandName nodes and BRAND_OF edges.

    Returns:
        Number of rows processed.
    """
    if dry_run:
        logger.info("[dry-run] Would import %d DrugBrandName nodes", len(rows))
        return len(rows)

    cypher = """
    UNWIND $rows AS row
    MATCH (d:Drug {drug_id: row.drug_id})
    MERGE (b:DrugBrandName {brand_id: row.brand_id})
    SET b.brand_name   = toLower(trim(row.brand_name)),
        b.manufacturer = row.manufacturer
    MERGE (b)-[:BRAND_OF]->(d)
    """
    await session.run(cypher, rows=rows)
    logger.info("Imported/updated %d DrugBrandName nodes", len(rows))
    return len(rows)


async def import_interactions(session, rows: list[dict], dry_run: bool) -> int:
    """MERGE INTERACTS_WITH edges between Drug nodes.

    Edge direction: drug_a → drug_b (directed, but queried undirected in
    Phase 06 — see interaction_engine.py for the rationale).

    Returns:
        Number of rows processed (not necessarily unique edges — re-runs
        update existing edges in place via MERGE).
    """
    if dry_run:
        logger.info("[dry-run] Would import %d interaction edges", len(rows))
        return len(rows)

    cypher = """
    UNWIND $rows AS row
    MATCH (a:Drug {drug_id: row.drug_a_id})
    MATCH (b:Drug {drug_id: row.drug_b_id})
    MERGE (a)-[r:INTERACTS_WITH {interaction_id: row.interaction_id}]->(b)
    SET r.severity          = row.severity,
        r.mechanism         = row.mechanism,
        r.management_advice = row.management_advice,
        r.source            = row.source
    """
    await session.run(cypher, rows=rows)
    logger.info("Imported/updated %d INTERACTS_WITH edges", len(rows))
    return len(rows)


async def upsert_dataset_version(
    session,
    version: str,
    drug_count: int,
    interaction_count: int,
    dry_run: bool,
) -> None:
    """MERGE a DatasetVersion node recording this import run."""
    if dry_run:
        logger.info("[dry-run] Would upsert DatasetVersion '%s'", version)
        return

    cypher = """
    MERGE (v:DatasetVersion {version: $version})
    SET v.source            = 'DDInter_2.0',
        v.imported_at       = $imported_at,
        v.drug_count        = $drug_count,
        v.interaction_count = $interaction_count
    """
    await session.run(
        cypher,
        version=version,
        imported_at=datetime.now(UTC).isoformat(),
        drug_count=drug_count,
        interaction_count=interaction_count,
    )
    logger.info("DatasetVersion '%s' upserted", version)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_import(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    source_dir: Path,
    version: str,
    dry_run: bool,
) -> None:
    """Full import pipeline: schema → drugs → brands → interactions → version node."""
    # Locate CSVs — accept both fixture names and production names
    drugs_path = _find_csv(source_dir, "drugs_fixture.csv", "drugs.csv")
    brands_path = _find_csv(source_dir, "brand_names_fixture.csv", "brand_names.csv")
    interactions_path = _find_csv(
        source_dir, "interactions_fixture.csv", "interactions.csv"
    )

    drug_rows = _read_csv(drugs_path)
    brand_rows = _read_csv(brands_path)
    interaction_rows = _read_csv(interactions_path)

    logger.info(
        "Parsed: %d drugs, %d brands, %d interactions from %s",
        len(drug_rows), len(brand_rows), len(interaction_rows), source_dir,
    )

    if dry_run:
        logger.info("=== DRY RUN — no writes to Neo4j ===")
        # Still validate CSV shapes
        for row in drug_rows:
            assert "drug_id" in row and "generic_name" in row, "Invalid drug CSV shape"
        for row in brand_rows:
            assert "brand_id" in row and "drug_id" in row, "Invalid brand CSV shape"
        for row in interaction_rows:
            assert "interaction_id" in row and "drug_a_id" in row, "Invalid interaction CSV shape"
        logger.info("Dry-run validation passed.")
        return

    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        async with driver.session() as session:
            # Apply schema first (idempotent)
            from app.db.schema import ensure_constraints  # noqa: PLC0415
            await ensure_constraints(session)

            drug_count = await import_drugs(session, drug_rows, version, dry_run=False)
            await import_brands(session, brand_rows, dry_run=False)
            interaction_count = await import_interactions(session, interaction_rows, dry_run=False)
            await upsert_dataset_version(
                session, version, drug_count, interaction_count, dry_run=False
            )
    finally:
        await driver.close()

    logger.info(
        "Import complete — version=%s drugs=%d interactions=%d",
        version, drug_count, interaction_count,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import DDInter/RxNorm data into CascadeX Neo4j graph."
    )
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Directory containing the drug/brand/interaction CSV files.",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Dataset version label, e.g. 'ddinter-2.0-2024-01'.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate CSVs without writing to Neo4j.",
    )
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.source.exists():
        logger.error("Source directory not found: %s", args.source)
        sys.exit(1)

    asyncio.run(
        run_import(
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
            source_dir=args.source,
            version=args.version,
            dry_run=args.dry_run,
        )
    )
