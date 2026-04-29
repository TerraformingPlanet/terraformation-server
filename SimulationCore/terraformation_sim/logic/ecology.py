"""Ecology logic — pure functions for species growth and tile ecology.

Phase 11.5: species-based biodiversity replacing scalar vegetationDensity/wildlifeDensity.
All functions are stateless and take/return Pydantic models.
"""
from __future__ import annotations

from terraformation_sim.models import (
    GoldbergTileState,
    SpeciesData,
    SphericalBodyState,
    TerrainType,
    WaterClassification,
)
from terraformation_sim.data.species import PLANT_SPECIES, SPECIES_REGISTRY


def compute_species_growth(
    sp: SpeciesData,
    temperature: float,
    o2_ratio: float,
    vegetation_cover: float,
) -> SpeciesData:
    """Return a new SpeciesData with density advanced by one tick.

    3-tier growth model (1 tick = 1 day):
    - Nominal zone  → full growth rate (×1.0)
    - Viable zone   → stressed growth  (×0.2)
    - Outside viable → decline         (×2.0 per tick, negative)
    """
    per_tick = sp.growthRateAnnual / 365.0

    viable = (
        sp.minTemp <= temperature <= sp.maxTemp
        and sp.minO2 <= o2_ratio <= sp.maxO2
        and vegetation_cover >= sp.minVegetation
    )
    in_nominal = (
        sp.nominalTempMin <= temperature <= sp.nominalTempMax
        and sp.nominalO2Min <= o2_ratio <= sp.nominalO2Max
        and vegetation_cover >= sp.minVegetation
    )

    if in_nominal:
        # Full growth — logistic saturation
        new_density = min(1.0, sp.density + per_tick * (1.0 - sp.density))
    elif viable:
        # Stressed growth — 20% of nominal rate
        new_density = min(1.0, sp.density + per_tick * 0.2 * (1.0 - sp.density))
    else:
        # Decline — 2× the per-tick rate
        new_density = max(0.0, sp.density - per_tick * 2.0)

    return sp.model_copy(update={"density": new_density})


def compute_tile_ecology(tile: GoldbergTileState, o2_ratio: float) -> list[SpeciesData]:
    """Advance all species on a single tile by one tick.

    Returns a new list of SpeciesData (tile is not mutated).
    """
    vegetation_cover = sum(
        sp.density for sp in tile.species if sp.speciesId in PLANT_SPECIES
    )
    return [
        compute_species_growth(sp, tile.temperature, o2_ratio, vegetation_cover)
        for sp in tile.species
    ]


def aggregate_ecology_output(tiles: list[GoldbergTileState]) -> dict[str, float]:
    """Sum all species marketOutput across tiles, weighted by density.

    Returns a resource → total output dict for the body this tick.
    """
    totals: dict[str, float] = {}
    for tile in tiles:
        for sp in tile.species:
            for resource, base_amount in sp.marketOutput.items():
                totals[resource] = totals.get(resource, 0.0) + base_amount * sp.density
    return totals


def compute_terrain_transition(
    tile: GoldbergTileState,
    new_species: list[SpeciesData],
) -> TerrainType:
    """Return the new TerrainType after ecology growth, handling Vegetation↔Forêt transition.

    Thresholds (forest density):
    - Vegetation → Forêt  : forest density ≥ 0.65 (mature canopy established)
    - Forêt → Vegetation  : forest density < 0.15 (forest collapsed)
    """
    forest_density = next(
        (sp.density for sp in new_species if sp.speciesId == "forest"), 0.0
    )
    if tile.terrainType == TerrainType.Vegetation and forest_density >= 0.65:
        return TerrainType.Foret
    if tile.terrainType == TerrainType.Foret and forest_density < 0.15:
        return TerrainType.Vegetation
    return tile.terrainType


def seed_species_for_tile(
    terrain_type: TerrainType,
    water_classification: WaterClassification,
) -> list[SpeciesData]:
    """Return the initial species list for a tile at generation time.

    Only tiles with biologically relevant terrain get species; others get [].
    Starting density is 0.1 (sparse initial population).
    """
    if terrain_type == TerrainType.Vegetation:
        candidates = ["grass", "forest", "insect", "herbivore"]
    elif terrain_type == TerrainType.Foret:
        # Forest tiles: denser forest species + full ecosystem
        candidates = ["forest", "grass", "insect", "herbivore"]
    elif terrain_type == TerrainType.Eau:
        candidates = ["algae", "fish"]
    elif terrain_type == TerrainType.Glace:
        candidates = ["cyanobacteria"]
    else:
        return []
    # Foret tiles start with higher forest density (0.5 vs 0.1 for others)
    def _initial_density(sid: str) -> float:
        if terrain_type == TerrainType.Foret and sid == "forest":
            return 0.5
        return 0.1
    return [
        SPECIES_REGISTRY[sid].model_copy(update={"density": _initial_density(sid)})
        for sid in candidates
        if sid in SPECIES_REGISTRY
    ]
