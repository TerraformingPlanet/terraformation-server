"""
Assertion script — p8-events
Validates the gameplay events system (Phase 8).
"""
import pytest

# ── imports nécessaires à la phase ────────────────────────────────────────────
from terraformation_sim.models import EventData, EventType, EventEffect


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_event():
    """Provide a sample EventData for testing."""
    return EventData(
        id="test-event-1",
        eventType=EventType.Rebellion,
        name="Test Rebellion",
        description="A test rebellion event",
        tick=100,
        affectedEntityId="state-1",
        affectedEntityType="state",
        effect=EventEffect(
            resourceType="Food",
            resourceDelta=-10.0,
            creditsDelta=0.0,
            reputationDelta=-0.1,
            populationDelta=-5.0
        ),
        isResolved=False
    )


# ── tests des critères de sortie ──────────────────────────────────────────────

def test_event_data_model(sample_event):
    """Test EventData model creation and validation."""
    assert sample_event.id == "test-event-1"
    assert sample_event.eventType == EventType.Rebellion
    assert sample_event.name == "Test Rebellion"
    assert sample_event.tick == 100
    assert sample_event.affectedEntityId == "state-1"
    assert sample_event.affectedEntityType == "state"
    assert sample_event.effect.resourceDelta == -10.0
    assert sample_event.effect.reputationDelta == -0.1
    assert not sample_event.isResolved


def test_event_types_enum():
    """Test EventType enum values."""
    assert EventType.RencontreAlienne == 0
    assert EventType.TempeteSolaire == 1
    assert EventType.DecouverteMiniere == 2
    assert EventType.CriseEconomique == 3
    assert EventType.SabotageCorpo == 4
    assert EventType.Rebellion == 5
    assert EventType.MigrationPopulation == 6
    assert EventType.DecouverteMegastructure == 7
    assert EventType.EmpireGalactique == 8


def test_event_effect_model():
    """Test EventEffect model."""
    effect = EventEffect(
        resourceType="Energy",
        resourceDelta=50.0,
        creditsDelta=1000.0,
        reputationDelta=0.05,
        populationDelta=0.0
    )
    assert effect.resourceType == "Energy"
    assert effect.resourceDelta == 50.0
    assert effect.creditsDelta == 1000.0
    assert effect.reputationDelta == 0.05
    assert effect.populationDelta == 0.0


def test_event_resolution():
    """Test event resolution flag."""
    event = EventData(
        id="test-event-2",
        eventType=EventType.DecouverteMiniere,
        name="Test Discovery",
        description="A test discovery",
        tick=200,
        affectedEntityId="corp-1",
        affectedEntityType="corporation",
        effect=EventEffect(),
        isResolved=False
    )
    assert not event.isResolved
    event.isResolved = True
    assert event.isResolved