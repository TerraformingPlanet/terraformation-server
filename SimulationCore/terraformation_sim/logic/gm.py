"""
logic/gm.py — Pure GM (Game Master) balance-detection and lever functions.

No side effects, no runtime state. All functions are synchronous and can be
tested independently of the simulation loop.

Phase 11.3 M1 scope:
    - Leaderboard imbalance metric (score_max / score_median)
    - Detect whether imbalance exceeds a threshold

Phase 11.3 M2 scope:
    - Context-based lever picker
    - 3 plan-builder helpers: alien_pop, megastructure, empire_galactique
"""
from __future__ import annotations

import random
import statistics

from ..models import ScoreboardEntry


def compute_leaderboard_imbalance(scoreboard: list[ScoreboardEntry]) -> float:
    """
    Return score_max / score_median for corps with score > 0.

    Returns 0.0 when fewer than 2 corps have a positive score (no meaningful ratio).
    """
    positive_scores = [e.score for e in scoreboard if e.score > 0.0]
    if len(positive_scores) < 2:
        return 0.0
    score_max = max(positive_scores)
    score_median = statistics.median(positive_scores)
    if score_median == 0.0:
        return 0.0
    return score_max / score_median


def detect_imbalance(
    scoreboard: list[ScoreboardEntry],
    threshold: float = 2.5,
) -> bool:
    """
    Return True if compute_leaderboard_imbalance(scoreboard) >= threshold.

    Default threshold of 2.5 means the leader has at least 2.5× the median score.
    """
    return compute_leaderboard_imbalance(scoreboard) >= threshold


def pick_gm_lever(last_lever: str | None, context: dict) -> str:
    """
    Select the next GM lever based on imbalance ratio and last lever used.

    Rules (in priority order):
    1. ratio >= 5.0 and last_lever != 'empire_galactique' → 'empire_galactique'
    2. last_lever != 'alien_pop'                          → 'alien_pop'
    3. fallback                                            → 'megastructure'
    """
    ratio = context.get("imbalanceRatio", 0.0)
    if ratio >= 5.0 and last_lever != "empire_galactique":
        return "empire_galactique"
    if last_lever != "alien_pop":
        return "alien_pop"
    return "megastructure"


def build_alien_pop_plan(
    tick: int,
    candidate_tile_ids: list[str],
    n: int = 6,
) -> list[str]:
    """
    Select up to *n* tile IDs from *candidate_tile_ids* for an alien population state.

    Returns a (possibly shorter) list when fewer than *n* candidates exist.
    *tick* is accepted for API symmetry and future seeding.
    """
    return random.sample(candidate_tile_ids, min(n, len(candidate_tile_ids)))


def build_megastructure_plan(tick: int) -> tuple[str, str]:
    """
    Return (event_name, description) for a megastructure discovery event.

    Pure — no randomness, deterministic for a given tick.
    """
    return (
        f"Mégastructure Tique {tick}",
        f"Signal d'origine inconnue détecté au tique {tick}. "
        "Analyse en cours — la structure défie toute classification connue.",
    )


def build_empire_galactique_plan(
    tick: int,
    all_tile_ids: list[str],
    n: int = 15,
) -> list[str]:
    """
    Select up to *n* tile IDs from *all_tile_ids* for the galactic empire state.

    Returns a (possibly shorter) list when fewer than *n* tiles exist.
    *tick* is accepted for API symmetry and future seeding.
    """
    return random.sample(all_tile_ids, min(n, len(all_tile_ids)))
