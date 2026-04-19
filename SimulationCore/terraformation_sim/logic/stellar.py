from __future__ import annotations

import math

from ..models import (
    AtmosphericComposition,
    SphericalBodyState,
    TerrainType,
    WaterClassification,
)

# ── Greenhouse constants (GameBalanced preset — from Per Aspera SDK ClimateConfig) ──
_CO2_EFF: float = 1.5
_H2O_EFF: float = 4.0
_MAX_WARMING_K: float = 80.0


def _greenhouse_delta(co2_ratio: float, h2o_factor: float = 0.01) -> float:
    """Extra temperature (Kelvin) from greenhouse effect. Logarithmic, capped."""
    co2_effect = _CO2_EFF * math.log(1.0 + co2_ratio * 100.0) * 5.0
    h2o_effect = _H2O_EFF * h2o_factor
    return min(co2_effect + h2o_effect, _MAX_WARMING_K)


# ── Stellar physics ───────────────────────────────────────────────────────────

# Base luminosity (L☉) and reference radius (km) per spectral class.
# Values are approximate mid-class averages; radius correction refines them.
_SPECTRAL_BASE_LUMINOSITY: dict[str, float] = {
    "O": 100_000.0, "B": 100.0, "A": 5.0, "F": 2.0, "G": 1.0, "K": 0.3, "M": 0.08,
}
_SPECTRAL_BASE_RADIUS_KM: dict[str, float] = {
    "O": 3_500_000.0, "B": 1_500_000.0, "A": 1_200_000.0, "F": 900_000.0,
    "G": 695_700.0,   "K": 550_000.0,   "M": 350_000.0,
}

_STEFAN_BOLTZMANN: float = 5.67e-8  # W m⁻² K⁻⁴
_SOL_LUMINOSITY_W: float = 3.828e26  # W — IAU 2015 nominal
_AU_IN_METRES:    float = 1.496e11   # m per AU
_DEFAULT_PLANET_ALBEDO: float = 0.30


def spectral_type_to_luminosity(spectral_type: str, radius_km: float) -> float:
    """Derive stellar luminosity (L☉) from spectral class + radius.
    Uses a radius² correction relative to the class median.
    Returns 0.0 for empty / non-stellar spectral types.
    """
    if not spectral_type:
        return 0.0
    cls = spectral_type[0].upper()
    base_L = _SPECTRAL_BASE_LUMINOSITY.get(cls, 1.0)
    base_R = _SPECTRAL_BASE_RADIUS_KM.get(cls, 695_700.0)
    if base_R <= 0:
        return 0.0
    return base_L * (radius_km / base_R) ** 2


def compute_planetary_irradiance(luminosity_lsun: float, semi_major_au: float) -> float:
    """Mean solar irradiance at a planet's distance from its star (W/m²).
    Returns 0.0 for luminosity≤0 or semi_major_au≤0.
    """
    if luminosity_lsun <= 0.0 or semi_major_au <= 0.0:
        return 0.0
    L_W   = _SOL_LUMINOSITY_W * luminosity_lsun
    dist_m = semi_major_au * _AU_IN_METRES
    return L_W / (4.0 * math.pi * dist_m ** 2)


def compute_greenhouse_temp(atmosphere: AtmosphericComposition) -> float:
    """Greenhouse warming (ΔK) from the planet's atmospheric composition.
    CH₄ is folded in as CO₂-equivalent using a simplified GWP scaling.
    """
    co2 = atmosphere.fraction_of("CO2")
    h2o = atmosphere.fraction_of("H2O")
    ch4 = atmosphere.fraction_of("CH4")
    effective_co2 = co2 + ch4 * 0.005  # CH4 GWP-scaled contribution
    return _greenhouse_delta(effective_co2, h2o_factor=h2o)


def compute_equilibrium_temperature(
    irradiance_wm2: float,
    atmosphere: AtmosphericComposition,
    planet_albedo: float = _DEFAULT_PLANET_ALBEDO,
) -> float:
    """Planetary mean surface temperature (°C).
    Uses the Stefan-Boltzmann zero-dim energy balance plus greenhouse warming.
    Returns absolute zero (−273.15 °C) for irradiance≤0.
    """
    if irradiance_wm2 <= 0.0:
        return -273.15
    T_eff_K = ((irradiance_wm2 * (1.0 - planet_albedo)) / (4.0 * _STEFAN_BOLTZMANN)) ** 0.25
    greenhouse_K = compute_greenhouse_temp(atmosphere)
    return T_eff_K - 273.15 + greenhouse_K * 0.1


def compute_tile_irradiance(lat_deg: float, planet_irradiance_wm2: float) -> float:
    """Effective W/m² at a tile given its latitude (cosine weighting)."""
    cos_factor = max(0.0, math.cos(math.radians(lat_deg)))
    return planet_irradiance_wm2 * cos_factor


def compute_tile_albedo(terrain_type: TerrainType, water_class: WaterClassification) -> float:
    """Surface albedo for a single tile, used for per-tile temperature correction."""
    if water_class == WaterClassification.FrozenWater or terrain_type == TerrainType.Glace:
        return 0.85
    if water_class == WaterClassification.OpenOcean:
        return 0.06
    if water_class in (WaterClassification.InlandWater, WaterClassification.Coast):
        return 0.08
    if terrain_type == TerrainType.Vegetation:
        return 0.12
    if terrain_type == TerrainType.Metal:
        return 0.30
    if terrain_type == TerrainType.AtmosphereToxique:
        return 0.20
    return 0.25  # Roche default


def aggregate_tile_deltas(body: SphericalBodyState) -> None:
    """Fold per-tile CO₂/O₂ deltas into the planet's AtmosphericComposition.
    Should be called once per advance_tick() for each colonised body.
    Deltas are volume-fraction per tile; they are averaged across all tiles
    and then added to the global gas fractions.
    """
    if not body.tiles:
        return
    n = len(body.tiles)
    total_co2_delta = sum(t.atmosphereDeltaCo2 for t in body.tiles)
    total_o2_delta  = sum(t.atmosphereDeltaO2  for t in body.tiles)
    co2_delta_avg = total_co2_delta / n
    o2_delta_avg  = total_o2_delta  / n
    if co2_delta_avg:
        new_co2 = max(0.0, min(1.0, body.atmosphere.fraction_of("CO2") + co2_delta_avg))
        body.atmosphere.set_fraction("CO2", new_co2)
    if o2_delta_avg:
        new_o2 = max(0.0, min(1.0, body.atmosphere.fraction_of("O2") + o2_delta_avg))
        body.atmosphere.set_fraction("O2", new_o2)
