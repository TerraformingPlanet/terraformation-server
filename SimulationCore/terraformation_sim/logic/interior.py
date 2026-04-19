from __future__ import annotations

import math

from ..models import (
    AnyBodyState,
    OrbitalParameters,
    SimulationCellAddress,
    SimulationCellState,
    SimulationSoilState,
    SimulationVector2State,
    TerrainClass,
    TerrainType,
    WaterClassification,
    WorldLayer,
    ZoneType,
)
from .generation import _tile_noise


# ── Interior zone cell generation ─────────────────────────────────────────────

def generate_interior_cells(cols: int, rows: int, zone_type: ZoneType, seed: int) -> list[SimulationCellState]:
    """Generate the hex cell grid for an interior zone (cave, building, ship…).
    Reuses SimulationCellState — same contract as RegionState.cells.
    """
    cells: list[SimulationCellState] = []
    layer = _zone_layer(zone_type)

    for row in range(rows):
        for col in range(cols):
            n0 = _tile_noise(col, row, seed, 0)
            n1 = _tile_noise(col, row, seed, 1)
            n2 = _tile_noise(col, row, seed, 2)

            terrain_type, water_class, t_class, water_ratio, temperature, toxin_level = _interior_terrain(
                zone_type, n0, n1, n2
            )
            cells.append(SimulationCellState(
                address=SimulationCellAddress(q=col, r=row),
                terrainName=_terrain_name(terrain_type, zone_type),
                terrainType=terrain_type,
                layer=layer,
                altitude=n0 * 0.4,
                temperature=temperature,
                waterRatio=water_ratio,
                toxinLevel=toxin_level,
                windVector=SimulationVector2State(x=0.0, y=0.0),
                windSpeed=0.0,
                rainShadow=True,
                hasRiver=False,
                flowAccumulation=0,
                terrainClass=t_class,
                waterClassification=water_class,
                soil=SimulationSoilState(
                    rockHardness=n0 * 0.8 + 0.1,
                    organicContent=0.0 if zone_type in (ZoneType.Ship, ZoneType.Station, ZoneType.Building) else n1 * 0.1,
                    porosity=n1 * 0.3,
                    mineralDensity=n2 * 0.5 + 0.1,
                    toxicSoil=toxin_level > 0.1,
                    thermalConductivity=0.4,
                ),
            ))
    return cells


def _zone_layer(zone_type: ZoneType) -> WorldLayer:
    if zone_type in (ZoneType.Cave, ZoneType.NaturalCavern, ZoneType.Underground):
        return WorldLayer.Underground
    if zone_type in (ZoneType.Ship, ZoneType.Station):
        return WorldLayer.Space
    return WorldLayer.Surface  # Building


def _interior_terrain(
    zone_type: ZoneType, n0: float, n1: float, n2: float
) -> tuple[TerrainType, WaterClassification, TerrainClass, float, float, float]:
    """Return (terrain_type, water_class, terrain_class, water_ratio, temperature, toxin_level)."""
    if zone_type in (ZoneType.Ship, ZoneType.Station):
        terrain_type = TerrainType.Metal if n0 > 0.15 else TerrainType.Roche
        water_ratio = max(0.0, n1 * 0.05 - 0.02)
        temperature = 18.0 + (n2 - 0.5) * 4.0
        toxin_level = 0.0
        water_class = WaterClassification.Dry
        t_class = TerrainClass.Slope
    elif zone_type == ZoneType.Building:
        terrain_type = TerrainType.Metal if n0 > 0.30 else TerrainType.Roche
        water_ratio = max(0.0, n1 * 0.08 - 0.03)
        temperature = 16.0 + (n2 - 0.5) * 6.0
        toxin_level = 0.0
        water_class = WaterClassification.Dry
        t_class = TerrainClass.Slope
    elif zone_type in (ZoneType.Cave, ZoneType.NaturalCavern):
        terrain_type = TerrainType.Roche if n0 > 0.35 else (TerrainType.Glace if n2 < 0.15 else TerrainType.Roche)
        water_ratio = max(0.0, n1 * 0.35 - 0.05)
        temperature = -5.0 + n2 * 15.0
        toxin_level = max(0.0, n0 * 0.12 - 0.06)
        water_class = WaterClassification.InlandWater if water_ratio > 0.3 else WaterClassification.Dry
        t_class = TerrainClass.Basin if n0 > 0.6 else TerrainClass.Slope
    else:  # Underground
        terrain_type = TerrainType.Roche if n0 > 0.2 else TerrainType.Metal
        water_ratio = max(0.0, n1 * 0.20 - 0.05)
        temperature = 8.0 + n2 * 12.0
        toxin_level = max(0.0, n0 * 0.08 - 0.04)
        water_class = WaterClassification.Dry
        t_class = TerrainClass.Ridge if n2 > 0.7 else TerrainClass.Slope

    return terrain_type, water_class, t_class, water_ratio, temperature, toxin_level


def _terrain_name(terrain_type: TerrainType, zone_type: ZoneType) -> str:
    prefix = {
        ZoneType.Cave: "Cave", ZoneType.NaturalCavern: "Cavern",
        ZoneType.Building: "Block", ZoneType.Underground: "Deep",
        ZoneType.Ship: "Hull", ZoneType.Station: "Deck",
    }.get(zone_type, "")
    suffix = {
        TerrainType.Roche: "Rock", TerrainType.Glace: "Ice",
        TerrainType.AtmosphereToxique: "Toxic", TerrainType.Eau: "Water",
        TerrainType.Vegetation: "Growth", TerrainType.Metal: "Metal",
    }.get(terrain_type, "Unknown")
    return f"{prefix} {suffix}".strip()


# ── Orbital mechanics ─────────────────────────────────────────────────────────

def compute_body_position_at_tick(
    body_id: str,
    tick: int,
    bodies: dict[str, AnyBodyState],
) -> dict[str, float]:
    """Return the position of a body relative to its system root in Astronomical Units.
    Recursively resolves parentId chains. Root body (orbitalParams=None) is at (0, 0, 0).
    Result dict: {"x": float, "y": float, "z": float} in AU.
    """
    body = bodies.get(body_id)
    if body is None:
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    params: OrbitalParameters | None = body.orbitalParams  # type: ignore[attr-defined]

    if params is None:
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    parent_pos = compute_body_position_at_tick(body.parentId, tick, bodies) if body.parentId else {"x": 0.0, "y": 0.0, "z": 0.0}

    # Kepler position: use simplified circular/elliptical in the ecliptic plane
    # true_anomaly ≈ mean_anomaly (low-eccentricity approximation, good for gameplay)
    mean_angle_deg = params.initialPhaseDeg + 360.0 * (tick / max(1, params.periodTicks))
    angle_rad = math.radians(mean_angle_deg)
    # Semi-latus rectum: r = a(1 - e²) / (1 + e*cosθ)
    a = params.semiMajorAxisAU
    e = params.eccentricity
    r = a * (1.0 - e * e) / (1.0 + e * math.cos(angle_rad))

    # Apply inclination around the X axis
    inc_rad = math.radians(params.inclinationDeg)
    x_orb = r * math.cos(angle_rad)
    y_orb = r * math.sin(angle_rad) * math.cos(inc_rad)
    z_orb = r * math.sin(angle_rad) * math.sin(inc_rad)

    return {
        "x": parent_pos["x"] + x_orb,
        "y": parent_pos["y"] + y_orb,
        "z": parent_pos["z"] + z_orb,
    }
