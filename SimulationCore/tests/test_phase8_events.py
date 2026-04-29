"""
Test Phase 8 — Gameplay Events system.

Tests EventType/EventData models, draw_event, apply_event_to_corporation.
"""
import sys
import importlib.util
import random
from pathlib import Path

_SIM = Path(__file__).parent.parent / "terraformation_sim"

# ── Load models ───────────────────────────────────────────────────────────────
spec = importlib.util.spec_from_file_location(
    "terraformation_sim.models",
    _SIM / "models.py",
)
models = importlib.util.module_from_spec(spec)
sys.modules["terraformation_sim.models"] = models
spec.loader.exec_module(models)

# ── Load logic/events ─────────────────────────────────────────────────────────
spec2 = importlib.util.spec_from_file_location(
    "terraformation_sim.logic.events",
    _SIM / "logic" / "events.py",
)
events_logic = importlib.util.module_from_spec(spec2)
sys.modules["terraformation_sim.logic.events"] = events_logic
spec2.loader.exec_module(events_logic)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_event_type_enum():
    """EventType has 9 members, IntEnum values 0-8."""
    assert len(list(models.EventType)) == 12
    assert models.EventType.RencontreAlienne == 0
    assert models.EventType.MigrationPopulation == 6
    assert models.EventType.DecouverteMegastructure == 7
    assert models.EventType.EmpireGalactique == 8
    print("✓ EventType enum OK (9 members, 0-8)")


def test_event_effect_defaults():
    """EventEffect can be instantiated with all defaults."""
    e = models.EventEffect()
    assert e.resourceType == ""
    assert e.resourceDelta == 0.0
    assert e.creditsDelta == 0.0
    assert e.reputationDelta == 0.0
    assert e.populationDelta == 0.0
    print("✓ EventEffect defaults OK")


def test_event_data_defaults():
    """EventData can be instantiated with all defaults."""
    d = models.EventData()
    assert d.id == ""
    assert d.isResolved is False
    assert isinstance(d.effect, models.EventEffect)
    print("✓ EventData defaults OK")


def test_draw_event_returns_event_data():
    """draw_event() returns an EventData with valid eventType."""
    rng = random.Random(42)
    event = events_logic.draw_event(tick=10, rng=rng, corp_id="corp_a")
    assert isinstance(event.eventType, models.EventType)
    assert event.tick == 10
    assert event.affectedEntityId == "corp_a"
    assert event.affectedEntityType == "corporation"
    assert event.id != ""
    print(f"✓ draw_event() returned EventType.{event.eventType.name}")


def test_draw_event_distribution():
    """draw_event() produces all 7 event types across enough draws."""
    rng = random.Random(0)
    seen = set()
    for _ in range(500):
        ev = events_logic.draw_event(tick=0, rng=rng)
        seen.add(ev.eventType)
    assert len(seen) == 7, f"Only {len(seen)} unique types seen: {seen}"
    print("✓ All 7 EventTypes produced across 500 draws")


def test_apply_event_credits_delta():
    """apply_event_to_corporation correctly adjusts credits."""
    corp = models.CorporationData(id="c1", name="TestCorp", credits=1000.0)
    event = models.EventData(
        id="ev1",
        eventType=models.EventType.CriseEconomique,
        effect=models.EventEffect(creditsDelta=-300.0),
    )
    updated = events_logic.apply_event_to_corporation(event, corp)
    assert updated.credits == 700.0, f"Expected 700, got {updated.credits}"
    assert corp.credits == 1000.0  # original unchanged
    print("✓ apply_event_to_corporation credits delta OK")


def test_apply_event_credits_floor_zero():
    """Credits never go below 0."""
    corp = models.CorporationData(id="c1", name="TestCorp", credits=100.0)
    event = models.EventData(
        id="ev2",
        eventType=models.EventType.CriseEconomique,
        effect=models.EventEffect(creditsDelta=-999.0),
    )
    updated = events_logic.apply_event_to_corporation(event, corp)
    assert updated.credits == 0.0, f"Expected 0, got {updated.credits}"
    print("✓ Credits floor at 0 OK")


def test_apply_event_resource_delta():
    """apply_event_to_corporation adjusts resource stocks."""
    corp = models.CorporationData(
        id="c2", name="MinerCorp", credits=500.0,
        resources={"Iron": 100.0},
    )
    event = models.EventData(
        id="ev3",
        eventType=models.EventType.DecouverteMiniere,
        effect=models.EventEffect(resourceType="Iron", resourceDelta=50.0),
    )
    updated = events_logic.apply_event_to_corporation(event, corp)
    assert updated.resources.get("Iron") == 150.0
    print("✓ apply_event_to_corporation resource delta OK")


if __name__ == "__main__":
    test_event_type_enum()
    test_event_effect_defaults()
    test_event_data_defaults()
    test_draw_event_returns_event_data()
    test_draw_event_distribution()
    test_apply_event_credits_delta()
    test_apply_event_credits_floor_zero()
    test_apply_event_resource_delta()
    print("\n✅ All Phase 8 event tests passed!")
