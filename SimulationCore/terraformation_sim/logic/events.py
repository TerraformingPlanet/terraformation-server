"""
Gameplay Events logic — Phase 8.

Pure functions: no side effects, no registry access, no `self`.
All state mutations happen in runtime.py via _process_event_tick_locked().
"""
from __future__ import annotations

import random
import uuid

from ..models import (
    CorporationData,
    EventData,
    EventEffect,
    EventType,
)
from ..registry import RESOURCE_REGISTRY

# ── Event catalogue ───────────────────────────────────────────────────────────

#: Static definitions for each event type.
#  weight: relative probability in the draw (sum = total weight pool).
#  resource / deltas: typical values — applied by apply_event_to_corporation().
GAME_EVENT_CONFIGS: list[dict] = [
    {
        "eventType": EventType.RencontreAlienne,
        "name": "Rencontre Extraterrestre",
        "description": "Une sonde détecte des signaux d'origine inconnue à proximité de la colonie.",
        "weight": 5,
        "creditsDelta": 0.0,
        "reputationDelta": 10.0,
        "resourceType": "",
        "resourceDelta": 0.0,
        "populationDelta": 0.0,
    },
    {
        "eventType": EventType.TempeteSolaire,
        "name": "Tempête Solaire",
        "description": "Une éjection de masse coronale perturbe les réseaux énergétiques de la colonie.",
        "weight": 15,
        "creditsDelta": -200.0,
        "reputationDelta": 0.0,
        "resourceType": "Energy",
        "resourceDelta": -50.0,
        "populationDelta": 0.0,
    },
    {
        "eventType": EventType.DecouverteMiniere,
        "name": "Découverte Minière",
        "description": "Des prospecteurs signalent un nouveau filon riche en minerai.",
        "weight": 20,
        "creditsDelta": 100.0,
        "reputationDelta": 5.0,
        "resourceType": "Iron",
        "resourceDelta": 80.0,
        "populationDelta": 0.0,
    },
    {
        "eventType": EventType.CriseEconomique,
        "name": "Crise Économique",
        "description": "Une bulle spéculative éclate sur les marchés coloniaux.",
        "weight": 12,
        "creditsDelta": -500.0,
        "reputationDelta": -15.0,
        "resourceType": "",
        "resourceDelta": 0.0,
        "populationDelta": 0.0,
    },
    {
        "eventType": EventType.SabotageCorpo,
        "name": "Sabotage Corporatif",
        "description": "Des agents rivaux ont saboté une installation stratégique.",
        "weight": 8,
        "creditsDelta": -300.0,
        "reputationDelta": -10.0,
        "resourceType": "Minerals",
        "resourceDelta": -30.0,
        "populationDelta": 0.0,
    },
    {
        "eventType": EventType.Rebellion,
        "name": "Rébellion Populaire",
        "description": "Des tensions sociales débordent en révolte ouverte dans un district.",
        "weight": 7,
        "creditsDelta": -150.0,
        "reputationDelta": -20.0,
        "resourceType": "",
        "resourceDelta": 0.0,
        "populationDelta": -500.0,
    },
    {
        "eventType": EventType.MigrationPopulation,
        "name": "Vague Migratoire",
        "description": "Une catastrophe dans un système voisin déclenche un afflux de réfugiés.",
        "weight": 13,
        "creditsDelta": 0.0,
        "reputationDelta": 5.0,
        "resourceType": "Food",
        "resourceDelta": -40.0,
        "populationDelta": 2000.0,
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

_WEIGHTS: list[int] = [cfg["weight"] for cfg in GAME_EVENT_CONFIGS]


def draw_event(tick: int, rng: random.Random, corp_id: str = "") -> EventData:
    """Randomly pick one event from the catalogue using weighted sampling."""
    cfg = rng.choices(GAME_EVENT_CONFIGS, weights=_WEIGHTS, k=1)[0]
    return EventData(
        id=str(uuid.uuid4()),
        eventType=cfg["eventType"],
        name=cfg["name"],
        description=cfg["description"],
        tick=tick,
        affectedEntityId=corp_id,
        affectedEntityType="corporation" if corp_id else "",
        effect=EventEffect(
            resourceType=cfg["resourceType"],
            resourceDelta=cfg["resourceDelta"],
            creditsDelta=cfg["creditsDelta"],
            reputationDelta=cfg["reputationDelta"],
            populationDelta=cfg["populationDelta"],
        ),
        isResolved=False,
    )


def apply_event_to_corporation(event: EventData, corp: CorporationData) -> CorporationData:
    """Return a *new* CorporationData with the event's effect applied."""
    updated = corp.model_copy(deep=True)
    effect = event.effect
    if effect.creditsDelta:
        updated.credits = max(0.0, updated.credits + effect.creditsDelta)
    if effect.resourceType and effect.resourceDelta:
        rt_name = effect.resourceType
        current = updated.resources.get(rt_name, 0.0)
        updated.resources[rt_name] = max(0.0, current + effect.resourceDelta)
    return updated
