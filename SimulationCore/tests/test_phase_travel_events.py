"""
test_phase_travel_events.py — Phase Travel Events : Incidents sur ExpeditionUnit.

Tests couverts :
    - Nouveaux EventType : Piraterie, Panne, Decouverte
    - EventData JSON roundtrip
    - EventEffect structure

Pas de Docker, pas de réseau. Durée < 1 s.
"""
import json
import sys
import importlib.util
from pathlib import Path

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load("models", "models.py")

EventData = _models.EventData
EventType = _models.EventType
EventEffect = _models.EventEffect


# ── Test 1 : Nouveaux EventType ──────────────────────────────────────────────

def test_new_event_types():
    """Vérifie que les nouveaux EventType existent."""
    assert EventType.Piraterie == 9
    assert EventType.Panne == 10
    assert EventType.Decouverte == 11
    print("✓ New EventType values: Piraterie=9, Panne=10, Decouverte=11")


# ── Test 2 : EventData avec nouveaux types ────────────────────────────────────

def test_event_data_with_new_types():
    """EventData accepte les nouveaux types d'événements."""
    for event_type in [EventType.Piraterie, EventType.Panne, EventType.Decouverte]:
        event = EventData(
            id=f"test_{event_type.name.lower()}",
            eventType=event_type,
            name=f"Test {event_type.name}",
            description=f"Test event for {event_type.name}",
            tick=1,
            affectedEntityId="corp1",
            affectedEntityType="corporation",
        )
        assert event.eventType == event_type
        assert event.affectedEntityId == "corp1"
    print("✓ EventData accepts new event types")


# ── Test 3 : EventEffect pour effets de trajet ───────────────────────────────

def test_event_effect_for_travel_events():
    """EventEffect peut représenter les effets des événements de trajet."""
    # Piracy: resource loss
    piracy_effect = EventEffect(resourceType="Food", resourceDelta=-10.0)
    assert piracy_effect.resourceType == "Food"
    assert piracy_effect.resourceDelta == -10.0
    
    # Discovery: reputation gain
    discovery_effect = EventEffect(reputationDelta=0.1)
    assert discovery_effect.reputationDelta == 0.1
    
    # Breakdown: no immediate effect (delay handled separately)
    breakdown_effect = EventEffect()
    assert breakdown_effect.resourceDelta == 0.0
    assert breakdown_effect.reputationDelta == 0.0
    
    print("✓ EventEffect structures for travel event effects")


# ── Test 4 : EventData JSON roundtrip ────────────────────────────────────────

def test_event_data_json_roundtrip():
    """EventData avec nouveaux types survive JSON serialization."""
    event = EventData(
        id="travel_event_test",
        eventType=EventType.Piraterie,
        name="Pirate Attack",
        description="Expedition attacked by space pirates",
        tick=42,
        affectedEntityId="corp1",
        affectedEntityType="corporation",
        effect=EventEffect(resourceType="Metal", resourceDelta=-5.0),
    )
    
    json_str = event.model_dump_json()
    data = json.loads(json_str)
    event2 = EventData.model_validate(data)
    
    assert event2.id == event.id
    assert event2.eventType == EventType.Piraterie
    assert event2.effect.resourceType == "Metal"
    assert event2.effect.resourceDelta == -5.0
    
    print("✓ EventData JSON roundtrip with new types")


# ── Test 5 : EventType enum values ───────────────────────────────────────────

def test_event_type_enum_values():
    """Tous les EventType ont des valeurs uniques."""
    types = [
        EventType.RencontreAlienne,
        EventType.TempeteSolaire,
        EventType.DecouverteMiniere,
        EventType.CriseEconomique,
        EventType.SabotageCorpo,
        EventType.Rebellion,
        EventType.MigrationPopulation,
        EventType.DecouverteMegastructure,
        EventType.EmpireGalactique,
        EventType.Piraterie,
        EventType.Panne,
        EventType.Decouverte,
    ]
    
    values = [t.value for t in types]
    assert len(values) == len(set(values)), "EventType values must be unique"
    
    # Check that new ones are at the end
    assert EventType.Piraterie.value == 9
    assert EventType.Panne.value == 10
    assert EventType.Decouverte.value == 11
    
    print(f"✓ EventType enum: {len(types)} types, all unique values")


# ── Test 6 : EventEffect JSON roundtrip ──────────────────────────────────────

def test_event_effect_json_roundtrip():
    """EventEffect survive JSON serialization."""
    effect = EventEffect(
        resourceType="Food",
        resourceDelta=-15.0,
        creditsDelta=0.0,
        reputationDelta=0.05,
        populationDelta=0.0,
    )
    
    json_str = effect.model_dump_json()
    data = json.loads(json_str)
    effect2 = EventEffect.model_validate(data)
    
    assert effect2.resourceType == "Food"
    assert effect2.resourceDelta == -15.0
    assert effect2.reputationDelta == 0.05
    
    print("✓ EventEffect JSON roundtrip")