# CascadeX — Resume & Portfolio Summary

> **Phase 09 Document.** Outcome-focused resume bullet points and architectural talking points highlighting technical leadership, safety invariants, systems engineering, and full-stack execution.

---

## 1. Ready-to-Use Resume Bullets

### Option A: Backend / Distributed Systems & Graph Focus
* **Architected and delivered CascadeX**, an asynchronous medication safety and drug-drug interaction (DDI) alert platform using **FastAPI, Neo4j, and Python 3.11**, indexing 32+ drug classes and thousands of interaction pairs from the DDInter 2.0 academic dataset with parameterized Cypher queries.
* **Engineered a sub-millisecond pairwise interaction engine** that optimizes graph traversals via single-roundtrip Cypher `UNWIND` queries, achieving a benchmarked **p95 latency ≤ 12.5ms across 20 concurrent active medications (190 pairs)**, exceeding the 500ms NFR-3 budget by 40x.
* **Designed a zero-hallucination AI integration layer** using Google Gemini API constrained by deterministic graph validation gates, ensuring LLMs only perform text normalization and plain-language translations after graph-verified clinical edges are confirmed.
* **Hardened platform security & privacy** by implementing Fernet AES-128 field-level encryption for sensitive OCR records, Argon2id/JWT auth with rotating refresh tokens, granular caregiver RBAC, and custom PII/PHI-scrubbing logging middleware with zero clinical leakage verified by automated test suites.

---

### Option B: Full-Stack Mobile & Systems Focus
* **Developed a production-grade cross-platform medication safety application** with **Flutter (Riverpod, Material 3)** and **FastAPI/Neo4j**, supporting offline-first synchronization via Hive, on-device camera OCR via Google ML Kit, and PDF clinical history generation via ReportLab.
* **Implemented an elderly-first accessible UX (WCAG AA compliant)** with high-contrast tiered alert badges, screen-reader semantic trees, 48×48dp minimum touch targets, and two-stage scan confirmation to eliminate medication misidentification errors.
* **Established comprehensive CI/CD and dependency security pipelines** with GitHub Actions, `pip-audit`, Dependabot, and automated regression testing across 25+ pytest test suites including end-to-end integration and load benchmark suites.

---

## 2. Key Engineering Highlights & Interview Talking Points

### 1. The "Unmatched ≠ Safe" Safety Invariant
* **Problem:** In medical safety apps, a naive database miss or typo can lead to returning an empty interaction list, which users misinterpret as "safe to take together."
* **Solution:** Designed the interaction engine with a formal invariant: any unrecognized or unresolvable drug produces an explicit `UnmatchedDrugWarning` and sets `is_clean: false`. The API explicitly refuses to declare a regimen safe when unverified drugs are present.

### 2. High-Performance Graph Modeling over Relational Joins
* **Problem:** Checking all pairwise interactions among $N$ drugs in a relational SQL database requires $O(N^2)$ separate queries or complex multi-table self-joins that degrade rapidly under multi-medication regimens.
* **Solution:** Modeled drugs as graph nodes with directed `(:Drug)-[:INTERACTS_WITH]->(:Drug)` relationships and queried them undirected using a single Cypher `UNWIND $pairs` statement. This reduced 190 database round-trips to exactly 1 query executed in under 15ms.

### 3. Constrained AI & Defense Against Hallucinations
* **Problem:** Generative AI models frequently hallucinate medical facts or fabricate drug interactions that do not exist in clinical literature.
* **Solution:** Strictly decoupled clinical fact-checking from linguistic generation. Neo4j acts as the single source of clinical truth. Gemini is only invoked in two bounded roles:
  1. *Fuzzy Drug Matching:* Given raw OCR text and a pre-filtered list of candidate catalog names, the LLM can only select from the candidate list; any other string is discarded.
  2. *Plain-Language Rewrite:* DDInter medical mechanism descriptions are rewritten into 8th-grade reading level explanations *only after* the graph edge has been established.

### 4. Privacy & Compliance Without Overhead
* **Problem:** Storing raw prescription labels and logging application traffic risks violating HIPAA/GDPR through unintended PHI leaks.
* **Solution:** Executed on-device OCR on the mobile client (preventing raw prescription photo uploads), encrypted raw OCR text at rest using Fernet symmetric encryption, and introduced Starlette `LoggingMiddleware` that captures structural metadata and opaque user UUIDs while strictly barring query strings, request bodies, and medication names.
