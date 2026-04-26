"""
Test for state-tile-colors endpoint (Phase Colonisation).

Tests the runtime.get_body_state_tile_colors() method and the server endpoint wiring.
"""
import pytest

from terraformation_sim.runtime import InMemorySimulationRuntime


def test_get_body_state_tile_colors():
    """Test that get_body_state_tile_colors returns populated data after bootstrap."""
    runtime = InMemorySimulationRuntime()
    runtime.bootstrap()

    # Find the Earth body_id (should be the only spherical body after bootstrap)
    earth_body_id = None
    for body_id, body in runtime._bodies.items():
        if hasattr(body, 'tiles') and body.tiles:
            earth_body_id = body_id
            break

    assert earth_body_id is not None, "Earth body not found after bootstrap"

    # Call the method
    colors = runtime.get_body_state_tile_colors(earth_body_id)

    # Should return a non-empty list
    assert isinstance(colors, list)
    assert len(colors) > 0, "No state tile colors returned"

    # Check structure of first item
    first = colors[0]
    assert isinstance(first, dict)
    assert 'tileId' in first
    assert 'stateId' in first
    assert 'stateName' in first
    assert 'profileKey' in first

    # All fields should be non-empty strings
    assert first['tileId']
    assert first['stateId']
    assert first['stateName']
    assert first['profileKey']

    # stateName should be one of the known continent states
    known_states = {
        "Fédération Européenne",
        "Alliance Asiatique",
        "République Nordique",
        "Union Sudaméricaine",
        "Confédération Africaine",
        "Coalition du Désert",
        "Confédération Pacifique",
        "Territoires Libres",
    }
    assert first['stateName'] in known_states, f"Unknown state name: {first['stateName']}"

    # profileKey should be valid
    valid_profiles = {"Standard", "RicheUtopique", "EnDeveloppement", "Pauvre", "Autoritaire"}
    assert first['profileKey'] in valid_profiles, f"Unknown profile key: {first['profileKey']}"

    # All items should have the same structure
    for item in colors:
        assert set(item.keys()) == {'tileId', 'stateId', 'stateName', 'profileKey'}
        assert all(isinstance(v, str) and v for v in item.values())


def test_get_body_state_tile_colors_unknown_body():
    """Test that unknown body_id returns empty list."""
    runtime = InMemorySimulationRuntime()
    runtime.bootstrap()

    colors = runtime.get_body_state_tile_colors("unknown-body-id")
    assert colors == []
