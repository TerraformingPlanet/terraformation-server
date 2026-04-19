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
    "GENERATION_VERSION",
    "generate_spherical_tiles",
    "is_tile_habitable",
    "summarize_spherical_hydrology",
    "summarize_spherical_tiles",
    # interior + orbital
    "compute_body_position_at_tick",
    "generate_interior_cells",
]
