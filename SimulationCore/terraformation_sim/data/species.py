"""Species registry — static game data for Phase 11.5 ecology system.

Each entry defines a species' environmental tolerances and per-tick resource output.
Import SpeciesData from models to avoid circular imports (models ← data ← logic).

Growth rates are stored as annual fractions (growthRateAnnual).
At 1 tick = 1 day: per_tick_rate = growthRateAnnual / 365
Examples:
  fish   : 25%/year  → 0.000685/tick  (MSY standard)
  forest : 4%/year   → 0.000110/tick  (IGN reboisement)
  grass  : 80%/year  → 0.00219/tick   (annuelles)

Each species has a nominal comfort zone (full growth) and a viable outer zone
(stressed growth ×0.2). Outside the viable zone → decline.
"""
from __future__ import annotations

from terraformation_sim.models import SpeciesData

SPECIES_REGISTRY: dict[str, SpeciesData] = {
    "cyanobacteria": SpeciesData(
        speciesId="cyanobacteria",
        # Viable: -40..70°C, O2: 0..0.05 — pioneers, extreme tolerance
        minTemp=-40.0, maxTemp=70.0,
        nominalTempMin=-40.0, nominalTempMax=70.0,  # full range nominal: robust pioneer
        minO2=0.0, maxO2=0.05,
        nominalO2Min=0.0, nominalO2Max=0.05,
        growthRateAnnual=0.80,  # 80%/year — microbes, fast
        marketOutput={"O2": 0.002, "Biomass": 0.001},
        minVegetation=0.0,
    ),
    "algae": SpeciesData(
        speciesId="algae",
        # Viable: -5..35°C, O2: 0..1.0
        minTemp=-5.0, maxTemp=35.0,
        nominalTempMin=-5.0, nominalTempMax=35.0,   # full range nominal: robust
        minO2=0.0, maxO2=1.0,
        nominalO2Min=0.0, nominalO2Max=1.0,
        growthRateAnnual=1.00,  # 100%/year — algae proliferates rapidly
        marketOutput={"O2": 0.002, "Biomass": 0.001},
        minVegetation=0.0,
    ),
    "grass": SpeciesData(
        speciesId="grass",
        # Viable: -5..50°C, nominal: 5..35°C
        minTemp=-5.0, maxTemp=50.0,
        nominalTempMin=5.0, nominalTempMax=35.0,
        minO2=0.10, maxO2=1.0,
        nominalO2Min=0.15, nominalO2Max=1.0,
        growthRateAnnual=0.80,  # 80%/year — annual plants
        marketOutput={},
        minVegetation=0.0,
    ),
    "forest": SpeciesData(
        speciesId="forest",
        # Viable: 5..40°C, nominal: 10..25°C (temperate forest optimum)
        minTemp=5.0, maxTemp=40.0,
        nominalTempMin=10.0, nominalTempMax=25.0,
        minO2=0.15, maxO2=1.0,
        nominalO2Min=0.18, nominalO2Max=1.0,
        growthRateAnnual=0.04,  # 4%/year — slow growth, ~37 years to mature (IGN data)
        marketOutput={"Wood": 0.01},
        minVegetation=0.0,
    ),
    "fish": SpeciesData(
        speciesId="fish",
        # Viable: -5..30°C, nominal: 5..20°C
        minTemp=-5.0, maxTemp=30.0,
        nominalTempMin=5.0, nominalTempMax=20.0,
        minO2=0.05, maxO2=1.0,
        nominalO2Min=0.10, nominalO2Max=1.0,
        growthRateAnnual=0.25,  # 25%/year — MSY standard for commercial fisheries
        marketOutput={"Fish": 0.004},
        minVegetation=0.0,
    ),
    "herbivore": SpeciesData(
        speciesId="herbivore",
        # Viable: 0..45°C, nominal: 8..30°C
        minTemp=0.0, maxTemp=45.0,
        nominalTempMin=8.0, nominalTempMax=30.0,
        minO2=0.10, maxO2=1.0,
        nominalO2Min=0.15, nominalO2Max=1.0,
        growthRateAnnual=0.15,  # 15%/year — large mammals, slow
        marketOutput={"Meat": 0.005},
        minVegetation=0.2,
    ),
    "insect": SpeciesData(
        speciesId="insect",
        # Viable: 5..50°C, nominal: 15..35°C
        minTemp=5.0, maxTemp=50.0,
        nominalTempMin=15.0, nominalTempMax=35.0,
        minO2=0.12, maxO2=1.0,
        nominalO2Min=0.15, nominalO2Max=1.0,
        growthRateAnnual=0.60,  # 60%/year — insects, moderate
        marketOutput={},
        minVegetation=0.1,
    ),
}

PLANT_SPECIES: set[str] = {"cyanobacteria", "algae", "grass", "forest"}
ANIMAL_SPECIES: set[str] = {"herbivore", "insect"}
