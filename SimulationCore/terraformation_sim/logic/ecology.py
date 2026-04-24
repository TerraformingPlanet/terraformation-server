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

    Growth occurs when all conditions are met; decline (×2 rate) when outside tolerances.
    """
    viable = (
        sp.minTemp <= temperature <= sp.maxTemp
        and sp.minO2 <= o2_ratio <= sp.maxO2
        and vegetation_cover >= sp.minVegetation
    )
    if viable:
        new_density = min(1.0, sp.density + sp.growthRate * (1.0 - sp.density))
    else:
        new_density = max(0.0, sp.density - sp.growthRate * 2.0)
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
    elif terrain_type == TerrainType.Eau:
        candidates = ["algae"]
    elif terrain_type == TerrainType.Glace:
        candidates = ["cyanobacteria"]
    else:
        return []
    return [
        SPECIES_REGISTRY[sid].model_copy(update={"density": 0.1})
        for sid in candidates
        if sid in SPECIES_REGISTRY
    ]
