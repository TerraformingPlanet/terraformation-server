"""
logic/ — SimulationCore logic package.

Public API is identical to the former logic.py module.
Callers (runtime.py, __init__.py, tests) use `from .logic import X` unchanged.
"""
from __future__ import annotations

from .stellar import (
    aggregate_tile_deltas,
    compute_equilibrium_temperature,
    compute_greenhouse_temp,
    compute_planetary_irradiance,
    compute_tile_albedo,
    compute_tile_irradiance,
    spectral_type_to_luminosity,
)
from .simulation import (
    apply_modifier_to_cell,
    apply_region_progress,
    can_apply_action,
    cell_habitability_score,
    compute_atmospheric_state,
    compute_habitability_progress,
    is_cell_habitable,
    process_pending_actions,
    queue_action,
    summarize_region_cells,
    terraform_action_definitions,
)
from .generation import (
    _body_h3_resolution,
    _hydrate_tiles_from_db,
    GENERATION_VERSION,
    generate_spherical_tiles,
    is_tile_habitable,
    summarize_spherical_hydrology,
    summarize_spherical_tiles,
)
from .interior import (
    compute_body_position_at_tick,
    generate_interior_cells,
)
from .colonization import (
    assign_tile_to_continent,
    build_territories_from_tiles,
    is_terrestrial_tile,
    seed_tile_population,
    tile_population_factor,
    TERRAIN_POP_MULTIPLIERS,
    WATER_POP_MULTIPLIERS,
)
from .rivers import (
    activate_sources,
    fill_lake_step,
    propagate_river_step,
    propagation_delay_ticks,
)
from .market import (
    apply_natural_growth,
    NATURAL_GROWTH_INTERVAL,
)
from .subhex import (
    init_sub_hexes,
    find_free_slot,
    free_slot_count,
    occupied_slot_count,
    SLOT_RANGES,
)

__all__ = [
    # stellar
    "aggregate_tile_deltas",
    "compute_equilibrium_temperature",
    "compute_greenhouse_temp",
    "compute_planetary_irradiance",
    "compute_tile_albedo",
    "compute_tile_irradiance",
    "spectral_type_to_luminosity",
    # simulation
    "apply_modifier_to_cell",
    "apply_region_progress",
    "can_apply_action",
    "cell_habitability_score",
    "compute_atmospheric_state",
    "compute_habitability_progress",
    "is_cell_habitable",
    "process_pending_actions",
    "queue_action",
    "summarize_region_cells",
    "terraform_action_definitions",
    # generation
    "_body_h3_resolution",
    "_hydrate_tiles_from_db",
    "GENERATION_VERSION",
    "generate_spherical_tiles",
    "is_tile_habitable",
    "summarize_spherical_hydrology",
    "summarize_spherical_tiles",
    # interior + orbital
    "compute_body_position_at_tick",
    "generate_interior_cells",
    # colonization
    "assign_tile_to_continent",
    "build_territories_from_tiles",
    "is_terrestrial_tile",
    "seed_tile_population",
    "tile_population_factor",
    "TERRAIN_POP_MULTIPLIERS",
    "WATER_POP_MULTIPLIERS",
    # rivers
    "activate_sources",
    "fill_lake_step",
    "propagate_river_step",
    "propagation_delay_ticks",
    # natural growth
    "apply_natural_growth",
    "NATURAL_GROWTH_INTERVAL",
    # sub-hex slots
    "init_sub_hexes",
    "find_free_slot",
    "free_slot_count",
    "occupied_slot_count",
    "SLOT_RANGES",
]
