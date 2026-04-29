"""
Eco-market logic — Phase 11.6.

Pure functions: no side effects, no registry access, no `self`.
All state mutations happen in runtime.py via _process_eco_market_tick_locked().
"""
from __future__ import annotations

from ..models import EcoStockListing, GoldbergTileState


# ── Constants ─────────────────────────────────────────────────────────────────

_BASE_PRICE = 1.0
_SCARCITY_EXPONENT = 0.5  # price multiplier when depleted


# ── Public functions ──────────────────────────────────────────────────────────

def compute_eco_market(
    tiles: list[GoldbergTileState],
    extractions: dict[str, float],  # speciesId → total extracted this tick
    tick: int,
) -> list[EcoStockListing]:
    """Compute eco-market listings from tile species densities.

    Args:
        tiles: All tiles on the body (with species populated)
        extractions: speciesId → total amount extracted this tick across all buildings
        tick: Current simulation tick

    Returns:
        List of EcoStockListing for each species with marketOutput
    """
    # Aggregate by species
    species_stats: dict[str, dict] = {}  # speciesId → {"total_stock": float, "max_stock": int, "resource": str}

    for tile in tiles:
        for sp in tile.species:
            if not sp.marketOutput:  # only species that produce tradable resources
                continue
            if sp.speciesId not in species_stats:
                # Find the primary resource this species produces
                resource = next(iter(sp.marketOutput.keys()))  # assume one primary output
                species_stats[sp.speciesId] = {
                    "total_stock": 0.0,
                    "max_stock": 0,  # will count eligible tiles
                    "resource": resource,
                }
            species_stats[sp.speciesId]["total_stock"] += sp.density
            species_stats[sp.speciesId]["max_stock"] += 1  # each tile with this species counts

    # Build listings
    listings = []
    for species_id, stats in species_stats.items():
        total_stock = stats["total_stock"]
        max_stock = stats["max_stock"]
        resource = stats["resource"]

        # Renewal rate: sum of growth rates across tiles (simplified: assume average growth)
        renewal_rate = 0.0
        for tile in tiles:
            for sp in tile.species:
                if sp.speciesId == species_id:
                    renewal_rate += sp.growthRate * sp.density  # growth this tick

        extraction_rate = extractions.get(species_id, 0.0)

        # Price: higher when depleted
        if max_stock > 0:
            scarcity_ratio = max_stock / max(1e-6, total_stock)  # avoid div by zero
            price = _BASE_PRICE * (scarcity_ratio ** _SCARCITY_EXPONENT)
        else:
            price = _BASE_PRICE

        listings.append(EcoStockListing(
            speciesId=species_id,
            resource=resource,
            totalStock=total_stock,
            maxStock=max_stock,
            renewalRate=renewal_rate,
            extractionRate=extraction_rate,
            price=price,
        ))

    return listings