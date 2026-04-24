"""Species registry — static game data for Phase 11.5 ecology system.

Each entry defines a species' environmental tolerances and per-tick resource output.
Import SpeciesData from models to avoid circular imports (models ← data ← logic).
"""
from __future__ import annotations

from terraformation_sim.models import SpeciesData

SPECIES_REGISTRY: dict[str, SpeciesData] = {
    "cyanobacteria": SpeciesData(
        speciesId="cyanobacteria",
        minTemp=-40.0, maxTemp=70.0,
        minO2=0.0, maxO2=0.05,
        growthRate=0.04,
        marketOutput={"O2": 0.001},
        minVegetation=0.0,
    ),
    "algae": SpeciesData(
        speciesId="algae",
        minTemp=-5.0, maxTemp=35.0,
        minO2=0.0, maxO2=1.0,
        growthRate=0.03,
        marketOutput={"O2": 0.002, "Biomass": 0.001},
        minVegetation=0.0,
    ),
    "grass": SpeciesData(
        speciesId="grass",
        minTemp=-5.0, maxTemp=50.0,
        minO2=0.10, maxO2=1.0,
        growthRate=0.03,
        marketOutput={},
        minVegetation=0.0,
    ),
    "forest": SpeciesData(
        speciesId="forest",
        minTemp=5.0, maxTemp=40.0,
        minO2=0.15, maxO2=1.0,
        growthRate=0.02,
        marketOutput={"Wood": 0.01},
        minVegetation=0.0,
    ),
    "herbivore": SpeciesData(
        speciesId="herbivore",
        minTemp=0.0, maxTemp=45.0,
        minO2=0.10, maxO2=1.0,
        growthRate=0.02,
        marketOutput={"Meat": 0.005},
        minVegetation=0.2,
    ),
    "insect": SpeciesData(
        speciesId="insect",
        minTemp=5.0, maxTemp=50.0,
        minO2=0.12, maxO2=1.0,
        growthRate=0.03,
        marketOutput={},
        minVegetation=0.1,
    ),
}

PLANT_SPECIES: set[str] = {"cyanobacteria", "algae", "grass", "forest"}
ANIMAL_SPECIES: set[str] = {"herbivore", "insect"}
