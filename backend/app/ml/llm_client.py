"""
CascadeX LLM client — Gemini wrapper for Phase 05 (OCR fuzzy match) and
Phase 06 (plain-language interaction rewrites).

Safety contract (non-negotiable):
1. ``match_drug_name()`` selects ONLY from the caller-supplied ``candidates``
   list.  It can never return a name that is not already in that list.
2. ``plain_language_rewrite()`` only rewrites text — it NEVER decides whether
   an interaction exists.  Called by the Phase 06 engine *after* a real
   INTERACTS_WITH edge is already confirmed.
3. If ``GEMINI_API_KEY`` is empty (dev / test / CI), both functions fall back
   to deterministic local logic — no network calls, no failures.

Stub-mode behaviour (no API key):
- ``match_drug_name``: uses ``difflib.get_close_matches`` (cutoff 0.6).
- ``plain_language_rewrite``: returns the original string unchanged.
"""

from __future__ import annotations

import logging
from difflib import get_close_matches

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _gemini_model():
    """Return a configured Gemini GenerativeModel, or None in stub mode."""
    if not settings.gemini_api_key:
        return None
    try:
        import google.generativeai as genai  # type: ignore[import]

        genai.configure(api_key=settings.gemini_api_key)
        return genai.GenerativeModel("gemini-1.5-flash")
    except ImportError:
        logger.warning(
            "google-generativeai package not installed — LLM features disabled (stub mode)"
        )
        return None
    except Exception as exc:
        logger.warning("Gemini initialisation failed: %s — stub mode active", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def match_drug_name(ocr_text: str, candidates: list[str]) -> str | None:
    """Select the best drug name for ``ocr_text`` from ``candidates``.

    Safety contract:
    - Return value is ALWAYS an element of ``candidates`` or ``None``.
    - If ``candidates`` is empty → always returns ``None``.
    - The LLM (when enabled) is given only the candidate list; it cannot
      produce a name that is not in the list.

    Stages:
    1. Exact / close match via ``difflib`` (no cost, always attempted first).
    2. Gemini prompt constrained to the candidate list (only if no close match
       and API key is configured).

    Args:
        ocr_text:   Raw text from ML Kit OCR (may be misspelled/fragmented).
        candidates: Pre-filtered drug names from the Neo4j catalog.

    Returns:
        The best matching name from ``candidates``, or ``None``.
    """
    if not candidates:
        return None

    ocr_lower = ocr_text.lower().strip()
    cands_lower = [c.lower() for c in candidates]

    # ── Stage 1: deterministic close match ─────────────────────────────────
    if ocr_lower in cands_lower:
        idx = cands_lower.index(ocr_lower)
        logger.debug("match_drug_name: exact hit '%s'", candidates[idx])
        return candidates[idx]

    close = get_close_matches(ocr_lower, cands_lower, n=1, cutoff=0.6)
    if close:
        idx = cands_lower.index(close[0])
        logger.debug("match_drug_name: close hit '%s' for '%s'", candidates[idx], ocr_text)
        return candidates[idx]

    # ── Stage 2: Gemini fuzzy match ─────────────────────────────────────────
    model = _gemini_model()
    if model is None:
        logger.debug("match_drug_name: stub mode — no match for '%s'", ocr_text)
        return None

    bullet_list = "\n".join(f"- {c}" for c in candidates)
    prompt = (
        "You are a drug-name matcher for a medication safety app.\n"
        f'The OCR scanner read: "{ocr_text}"\n\n'
        "Pick the BEST match from the list below. "
        "If none match confidently, reply exactly: NO_MATCH\n\n"
        f"Candidates:\n{bullet_list}\n\n"
        "Reply with ONLY the exact candidate name, or NO_MATCH. No explanation."
    )

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        if raw == "NO_MATCH":
            logger.info("match_drug_name: LLM → NO_MATCH for '%s'", ocr_text)
            return None
        # Safety gate: reject anything not in the original candidate list
        if raw.lower() in cands_lower:
            idx = cands_lower.index(raw.lower())
            logger.info(
                "match_drug_name: LLM matched '%s' → '%s'", ocr_text, candidates[idx]
            )
            return candidates[idx]
        logger.warning(
            "match_drug_name: LLM returned '%s' NOT in candidates — rejected", raw
        )
        return None
    except Exception as exc:
        logger.error("match_drug_name: LLM call failed (%s) — returning None", exc)
        return None


def plain_language_rewrite(mechanism: str) -> str:
    """Rewrite a DDInter mechanism string into plain English.

    Safety contract:
    - This function ONLY rewrites text. It never decides whether an
      interaction exists — that decision is made by the Phase 06 engine
      before this function is ever called.
    - If the LLM is unavailable, returns ``mechanism`` unchanged.

    Args:
        mechanism: Raw DDInter mechanism string (e.g. "Pharmacodynamic synergism").

    Returns:
        A plain-language rewrite, or ``mechanism`` if the LLM is unavailable.
    """
    if not mechanism or not mechanism.strip():
        return mechanism

    model = _gemini_model()
    if model is None:
        return mechanism  # stub: return original

    prompt = (
        "Rewrite the following drug interaction mechanism in plain English "
        "for an elderly patient with no medical training. "
        "Keep it to 1–2 sentences. Do NOT add warnings or advice.\n\n"
        f"Mechanism: {mechanism}\n\nPlain English:"
    )
    try:
        response = model.generate_content(prompt)
        rewritten = response.text.strip()
        return rewritten if rewritten else mechanism
    except Exception as exc:
        logger.error("plain_language_rewrite: LLM call failed (%s) — returning original", exc)
        return mechanism
