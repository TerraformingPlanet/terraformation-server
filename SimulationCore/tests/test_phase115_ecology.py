"""
test_phase115_ecology.py — Phase 11.5 : Biodiversité par espèce.

Tests couverts :
    [logic pure — no runtime, no noise, always run]
    T01  SpeciesData default density is 0.0
    T02  SPECIES_REGISTRY has 6 species
    T03  PLANT_SPECIES contains the 4 plant species
    T04  compute_species_growth grows density when conditions met
    T05  compute_species_growth declines density when temperature out of range
    T06  compute_species_growth declines when O2 too low
    T07  compute_species_growth requires minVegetation for animals
    T08  compute_species_growth caps density at 1.0
    T09  compute_tile_ecology returns same count as input species
    T10  aggregate_ecology_output sums resource outputs weighted by density
    T11  seed_species_for_tile returns [] for Roche terrain
    T12  seed_species_for_tile returns algae for Eau terrain
    T13  seed_species_for_tile returns grass+forest+insect+herbivore for Vegetation
    T14  seed_species_for_tile returns cyanobacteria for Glace terrain
    T15  GoldbergTileState has species field (no vegetationDensity)
    T16  SphericalBodyState has ecologyResources field

    [runtime — skipped si noise absent]
    T17  _process_ecology_tick_locked runs without error on body with tiles
    T18  _process_ecology_tick_locked updates ecologyResources on body

Pas de Docker, pas de réseau. Durée < 3 s.
"""
import sys
import importlib.util
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    full_name = f"terraformation_sim.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(full_name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _stub_package(full_name: str, path: Path) -> None:
    if full_name not in sys.modules:
        pkg = types.ModuleType(full_name)
        pkg.__path__ = [str(path)]  # type: ignore[attr-defined]
        pkg.__package__ = full_name
        sys.modules[full_name] = pkg


_stub_package("terraformation_sim", _SIM)
_stub_package("terraformation_sim.data", _SIM / "data")
# Load logic package properly (stub would be empty, breaking runtime imports)
if "terraformation_sim.logic" not in sys.modules:
    if str(_SIM.parent) not in sys.path:
        sys.path.insert(0, str(_SIM.parent))
    import terraformation_sim.logic as _logic_pkg  # noqa: F401

_models = _load("models", "models.py")
_species_data = _load("data.species", "data/species.py")
_ecology = _load("logic.ecology", "logic/ecology.py")

import pytest

SpeciesData         = _models.SpeciesData
GoldbergTileState   = _models.GoldbergTileState
SphericalBodyState  = _models.SphericalBodyState
TerrainType         = _models.TerrainType
WaterClassification = _models.WaterClassification

SPECIES_REGISTRY    = _species_data.SPECIES_REGISTRY
PLANT_SPECIES       = _species_data.PLANT_SPECIES

compute_species_growth   = _ecology.compute_species_growth
compute_tile_ecology     = _ecology.compute_tile_ecology
aggregate_ecology_output = _ecology.aggregate_ecology_output
seed_species_for_tile    = _ecology.seed_species_for_tile


# ---------------------------------------------------------------------------
# Skip guard (runtime tests only)
# ---------------------------------------------------------------------------

try:
    from noise import snoise3 as _  # noqa: F401
    _HAS_NOISE = True
except ImportError:
    _HAS_NOISE = False

_skip_no_noise = pytest.mark.skipif(not _HAS_NOISE, reason="noise C extension absent")


# ---------------------------------------------------------------------------
# T01 — SpeciesData default density
# ---------------------------------------------------------------------------

def test_T01_species_data_default_density():
    sp = SpeciesData(speciesId="test")
    assert sp.density == 0.0


# ---------------------------------------------------------------------------
# T02 — SPECIES_REGISTRY has 6 species
# ---------------------------------------------------------------------------

def test_T02_registry_has_six_species():
    assert len(SPECIES_REGISTRY) == 6


# ---------------------------------------------------------------------------
# T03 — PLANT_SPECIES contains 4 plant species
# ---------------------------------------------------------------------------

def test_T03_plant_species_set():
    assert PLANT_SPECIES == {"cyanobacteria", "algae", "grass", "forest"}


# ---------------------------------------------------------------------------
# T04 — compute_species_growth grows when conditions met
# ---------------------------------------------------------------------------

def test_T04_growth_when_viable():
    sp = SpeciesData(speciesId="grass", density=0.5, minTemp=-5.0, maxTemp=50.0,
                     minO2=0.10, maxO2=1.0, growthRate=0.03, minVegetation=0.0)
    result = compute_species_growth(sp, temperature=20.0, o2_ratio=0.21, vegetation_cover=0.5)
    assert result.density > 0.5


# ---------------------------------------------------------------------------
# T05 — compute_species_growth declines when temperature out of range
# ---------------------------------------------------------------------------

def test_T05_decline_when_temp_out_of_range():
    sp = SpeciesData(speciesId="grass", density=0.5, minTemp=-5.0, maxTemp=50.0,
                     minO2=0.10, maxO2=1.0, growthRate=0.03, minVegetation=0.0)
    result = compute_species_growth(sp, temperature=80.0, o2_ratio=0.21, vegetation_cover=0.5)
    assert result.density < 0.5


# ---------------------------------------------------------------------------
# T06 — compute_species_growth declines when O2 too low
# ---------------------------------------------------------------------------

def test_T06_decline_when_o2_too_low():
    sp = SpeciesData(speciesId="grass", density=0.5, minTemp=-5.0, maxTemp=50.0,
                     minO2=0.10, maxO2=1.0, growthRate=0.03, minVegetation=0.0)
    result = compute_species_growth(sp, temperature=20.0, o2_ratio=0.01, vegetation_cover=0.5)
    assert result.density < 0.5


# ---------------------------------------------------------------------------
# T07 — compute_species_growth requires minVegetation for animals
# ---------------------------------------------------------------------------

def test_T07_animal_requires_vegetation():
    sp = SpeciesData(speciesId="herbivore", density=0.5, minTemp=0.0, maxTemp=45.0,
                     minO2=0.10, maxO2=1.0, growthRate=0.02, minVegetation=0.2)
    # No vegetation → decline
    result = compute_species_growth(sp, temperature=20.0, o2_ratio=0.21, vegetation_cover=0.0)
    assert result.density < 0.5
    # Sufficient vegetation → growth
    result2 = compute_species_growth(sp, temperature=20.0, o2_ratio=0.21, vegetation_cover=0.5)
    assert result2.density > 0.5


# ---------------------------------------------------------------------------
# T08 — compute_species_growth caps density at 1.0
# ---------------------------------------------------------------------------

def test_T08_density_capped_at_one():
    sp = SpeciesData(speciesId="grass", density=0.99, minTemp=-5.0, maxTemp=50.0,
                     minO2=0.10, maxO2=1.0, growthRate=0.5, minVegetation=0.0)
    result = compute_species_growth(sp, temperature=20.0, o2_ratio=0.21, vegetation_cover=0.5)
    assert result.density <= 1.0


# ---------------------------------------------------------------------------
# T09 — compute_tile_ecology returns same count as input species
# ---------------------------------------------------------------------------

def test_T09_tile_ecology_same_count():
    sp1 = SpeciesData(speciesId="grass", density=0.3, minTemp=-5.0, maxTemp=50.0,
                      minO2=0.10, maxO2=1.0, growthRate=0.03, minVegetation=0.0)
    sp2 = SpeciesData(speciesId="herbivore", density=0.1, minTemp=0.0, maxTemp=45.0,
                      minO2=0.10, maxO2=1.0, growthRate=0.02, minVegetation=0.2)
    tile = GoldbergTileState(tileId="test", temperature=20.0, species=[sp1, sp2])
    result = compute_tile_ecology(tile, o2_ratio=0.21)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# T10 — aggregate_ecology_output sums resource outputs weighted by density
# ---------------------------------------------------------------------------

def test_T10_aggregate_ecology_output():
    sp = SpeciesData(speciesId="forest", density=0.5, marketOutput={"Wood": 0.01})
    tile = GoldbergTileState(tileId="t1", species=[sp])
    output = aggregate_ecology_output([tile])
    assert "Wood" in output
    assert abs(output["Wood"] - 0.005) < 1e-9  # 0.01 * 0.5


# ---------------------------------------------------------------------------
# T11 — seed_species_for_tile returns [] for Roche
# ---------------------------------------------------------------------------

def test_T11_seed_roche_returns_empty():
    result = seed_species_for_tile(TerrainType.Roche, WaterClassification.Dry)
    assert result == []


# ---------------------------------------------------------------------------
# T12 — seed_species_for_tile returns algae for Eau
# ---------------------------------------------------------------------------

def test_T12_seed_eau_returns_algae():
    result = seed_species_for_tile(TerrainType.Eau, WaterClassification.OpenOcean)
    assert len(result) == 1
    assert result[0].speciesId == "algae"
    assert result[0].density == 0.1


# ---------------------------------------------------------------------------
# T13 — seed_species_for_tile returns 4 species for Vegetation
# ---------------------------------------------------------------------------

def test_T13_seed_vegetation_returns_four():
    result = seed_species_for_tile(TerrainType.Vegetation, WaterClassification.Dry)
    ids = {sp.speciesId for sp in result}
    assert ids == {"grass", "forest", "insect", "herbivore"}
    assert all(sp.density == 0.1 for sp in result)


# ---------------------------------------------------------------------------
# T14 — seed_species_for_tile returns cyanobacteria for Glace
# ---------------------------------------------------------------------------

def test_T14_seed_glace_returns_cyanobacteria():
    result = seed_species_for_tile(TerrainType.Glace, WaterClassification.Dry)
    assert len(result) == 1
    assert result[0].speciesId == "cyanobacteria"


# ---------------------------------------------------------------------------
# T15 — GoldbergTileState has species field, no vegetationDensity
# ---------------------------------------------------------------------------

def test_T15_tile_has_species_not_vegetation_density():
    tile = GoldbergTileState(tileId="t1")
    assert hasattr(tile, "species")
    assert isinstance(tile.species, list)
    assert not hasattr(tile, "vegetationDensity")
    assert not hasattr(tile, "wildlifeDensity")


# ---------------------------------------------------------------------------
# T16 — SphericalBodyState has ecologyResources field
# ---------------------------------------------------------------------------

def test_T16_body_has_ecology_resources():
    body = SphericalBodyState(bodyId="b1")
    assert hasattr(body, "ecologyResources")
    assert isinstance(body.ecologyResources, dict)


# ---------------------------------------------------------------------------
# T17 — _process_ecology_tick_locked runs without error
# ---------------------------------------------------------------------------

@_skip_no_noise
def test_T17_process_ecology_tick_no_error():
    from terraformation_sim.runtime import InMemorySimulationRuntime as SimulationRuntime
    rt = SimulationRuntime.__new__(SimulationRuntime)
    from terraformation_sim.models import SphericalBodyState, GoldbergTileState, SpeciesData
    import threading
    rt._lock = threading.RLock()
    sp = SpeciesData(speciesId="grass", density=0.3, minTemp=-5.0, maxTemp=50.0,
                     minO2=0.0, maxO2=1.0, growthRate=0.03, minVegetation=0.0)
    body = SphericalBodyState(bodyId="b1")
    body.tiles = [GoldbergTileState(tileId="t1", temperature=20.0, species=[sp])]
    rt._bodies = {"b1": body}
    with rt._lock:
        rt._process_ecology_tick_locked()
    updated = rt._bodies["b1"]
    assert updated.tiles[0].species[0].density > 0.3


# ---------------------------------------------------------------------------
# T18 — _process_ecology_tick_locked updates ecologyResources
# ---------------------------------------------------------------------------

@_skip_no_noise
def test_T18_process_ecology_updates_resources():
    from terraformation_sim.runtime import InMemorySimulationRuntime as SimulationRuntime
    from terraformation_sim.models import SphericalBodyState, GoldbergTileState, SpeciesData
    import threading
    rt = SimulationRuntime.__new__(SimulationRuntime)
    rt._lock = threading.RLock()
    sp = SpeciesData(speciesId="forest", density=0.5, minTemp=5.0, maxTemp=40.0,
                     minO2=0.0, maxO2=1.0, growthRate=0.02, minVegetation=0.0,
                     marketOutput={"Wood": 0.01})
    body = SphericalBodyState(bodyId="b2")
    body.tiles = [GoldbergTileState(tileId="t2", temperature=20.0, species=[sp])]
    rt._bodies = {"b2": body}
    with rt._lock:
        rt._process_ecology_tick_locked()
    assert "Wood" in rt._bodies["b2"].ecologyResources
