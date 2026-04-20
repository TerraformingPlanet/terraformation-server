"""
Market logic — Phase 7.3 Marché local v1.

Pure functions: no side effects, no registry access, no `self`.
All state mutations happen in runtime.py via _process_market_tick_locked().
"""
from __future__ import annotations

from collections import deque

import h3 as _h3

from ..models import (
    ClaimedTile,
    LocalMarketState,
    PopulationTier,
    ResourceListing,
    ResourceType,
    SocialClass,
)

# ── Constants ─────────────────────────────────────────────────────────────────

#: Resources that participate in the local market (Waste is excluded).
TRADABLE_RESOURCES: list[ResourceType] = [
    ResourceType.Minerals,
    ResourceType.Food,
    ResourceType.Energy,
    ResourceType.ResearchPoints,
    ResourceType.Iron,           # Phase 9.5
    ResourceType.Oxygen,         # Phase 9.5
    ResourceType.Water,          # Phase 9.5
    ResourceType.Tech,           # Phase 9.5
]

# Demand per person per tick, by social class and resource.
# dict[SocialClass, dict[ResourceType, float]]
_DEMAND_PER_PERSON: dict[SocialClass, dict[ResourceType, float]] = {
    SocialClass.Poor: {
        ResourceType.Food:   0.5,
        ResourceType.Energy: 0.3,
    },
    SocialClass.Middle: {
        ResourceType.Food:     1.0,
        ResourceType.Energy:   0.8,
        ResourceType.Minerals: 0.2,
    },
    SocialClass.Rich: {
        ResourceType.Food:           1.5,
        ResourceType.Energy:         1.5,
        ResourceType.Minerals:       0.5,
        ResourceType.ResearchPoints: 0.3,
    },
}

_PRICE_MIN = 0.1
_PRICE_MAX = 10.0
_PRICE_ELASTICITY = 0.2   # exponent on supply/demand ratio

# Mobility rates per tick
_POOR_TO_MIDDLE_RATE   = 0.01   # per employed worker
_MIDDLE_TO_POOR_RATE   = 0.01   # per unemployed worker
_MIDDLE_TO_RICH_RATE   = 0.005  # only when employment >= threshold
_RICH_EMPLOYMENT_THRESHOLD = 0.8


# ── Public functions ──────────────────────────────────────────────────────────

def compute_territories(
    owner_entity_id: str,
    claimed_tiles: list[ClaimedTile],
) -> list[tuple[str, list[str]]]:
    """Compute connected components (territories) for an entity's tiles via H3 adjacency.

    Returns a list of (territory_id, tile_ids) where:
        territory_id = f"{owner_entity_id}::{min(component_tile_ids)}"

    Tiles on different bodies are never adjacent.
    """
    # Group by bodyId — tiles on different planets are never adjacent
    by_body: dict[str, list[str]] = {}
    for tile in claimed_tiles:
        by_body.setdefault(tile.bodyId, []).append(tile.tileId)

    territories: list[tuple[str, list[str]]] = []
    for tile_ids in by_body.values():
        tile_set = set(tile_ids)
        visited: set[str] = set()
        for start in tile_ids:
            if start in visited:
                continue
            component: list[str] = []
            queue: deque[str] = deque([start])
            visited.add(start)
            while queue:
                current = queue.popleft()
                component.append(current)
                for neighbor in _h3.grid_disk(current, 1):
                    if neighbor in tile_set and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            territory_id = f"{owner_entity_id}::{min(component)}"
            territories.append((territory_id, component))
    return territories


def init_market_listings() -> list[ResourceListing]:
    """Return a fresh list of ResourceListing for every tradable resource (price=1.0)."""
    return [ResourceListing(resourceType=rt) for rt in TRADABLE_RESOURCES]


def auto_init_tile_population(tile: ClaimedTile) -> ClaimedTile:
    """If the tile has no population, seed it with 10 Poor workers.

    Call this in claim_tile_locked() when a ClaimedTile is first created.
    Returns a new ClaimedTile (Pydantic model is immutable-ish — use model_copy).
    """
    if tile.population:
        return tile
    seeded = [PopulationTier(socialClass=SocialClass.Poor, count=10)]
    return tile.model_copy(update={"population": seeded})


def compute_population_demand(tiles: list[ClaimedTile]) -> dict[str, float]:
    """Aggregate demand across all claimed tiles, summed across social classes.

    Returns a dict keyed by ResourceType.name (e.g. "Food", "Energy").
    """
    demand: dict[str, float] = {}
    for tile in tiles:
        for tier in tile.population:
            per_person = _DEMAND_PER_PERSON.get(tier.socialClass, {})
            for resource_type, rate in per_person.items():
                key = resource_type.name
                demand[key] = demand.get(key, 0.0) + rate * tier.count
    return demand


def compute_market_prices(
    listings: list[ResourceListing],
    supply: dict[str, float],
    demand: dict[str, float],
) -> list[ResourceListing]:
    """Recompute prices based on supply/demand ratio.

    Formula: new_price = old_price * (demand / max(supply, ε)) ** elasticity
    Price is clamped to [_PRICE_MIN, _PRICE_MAX].
    Returns a new list with updated listings.
    """
    updated: list[ResourceListing] = []
    for listing in listings:
        key = listing.resourceType.name
        s = max(supply.get(key, 0.0), 1e-3)
        d = demand.get(key, 0.0)
        ratio = d / s
        new_price = listing.price * (ratio ** _PRICE_ELASTICITY)
        new_price = max(_PRICE_MIN, min(_PRICE_MAX, new_price))
        # Phase 9.4 — velocity = fractional change
        velocity = (new_price - listing.price) / max(listing.price, 1e-3)
        # Phase 9.4 — history bounded to 10 entries
        history = list(listing.priceHistory[-9:]) + [new_price]
        updated.append(listing.model_copy(update={
            "price":  new_price,
            "supply": supply.get(key, 0.0),
            "demand": d,
            "priceVelocity": velocity,
            "priceHistory": history,
        }))
    return updated


def apply_social_mobility(tile: ClaimedTile, employment_ratio: float) -> ClaimedTile:
    """Apply one tick of social mobility to a tile's population.

    - Poor → Middle: rate * employment_ratio (workers getting richer)
    - Middle → Poor: rate * (1 - employment_ratio) (workers sliding back)
    - Middle → Rich: only when employment_ratio >= threshold

    Returns a new ClaimedTile with updated population.
    """
    tiers: dict[SocialClass, int] = {
        SocialClass.Poor:   0,
        SocialClass.Middle: 0,
        SocialClass.Rich:   0,
    }
    for tier in tile.population:
        tiers[tier.socialClass] = tiers.get(tier.socialClass, 0) + tier.count

    poor   = tiers[SocialClass.Poor]
    middle = tiers[SocialClass.Middle]
    rich   = tiers[SocialClass.Rich]

    # Poor → Middle
    uplift = int(poor * _POOR_TO_MIDDLE_RATE * employment_ratio)
    poor   -= uplift
    middle += uplift

    # Middle → Poor (unemployment pressure)
    downlift = int(middle * _MIDDLE_TO_POOR_RATE * max(0.0, 1.0 - employment_ratio))
    middle   -= downlift
    poor     += downlift

    # Middle → Rich (prosperity)
    if employment_ratio >= _RICH_EMPLOYMENT_THRESHOLD:
        enrich = int(middle * _MIDDLE_TO_RICH_RATE)
        middle -= enrich
        rich   += enrich

    new_population = [
        PopulationTier(socialClass=SocialClass.Poor,   count=max(0, poor)),
        PopulationTier(socialClass=SocialClass.Middle, count=max(0, middle)),
        PopulationTier(socialClass=SocialClass.Rich,   count=max(0, rich)),
    ]
    return tile.model_copy(update={"population": new_population})


def compute_global_market(
    local_markets: list[LocalMarketState],
    system_id: str,
    tick: int,
) -> dict:
    """Aggregate local markets into a global market state (Phase 9.5).
    
    Args:
        local_markets: List of all LocalMarketState for this system
        system_id: System ID (e.g. "sol")
        tick: Current tick
    
    Returns:
        A dictionary suitable for GlobalMarketState model creation.
        - For each ResourceType in TRADABLE_RESOURCES:
          - Aggregates supply/demand from all local markets
          - Computes weighted average price (by supply)
          - Sets priceHistory and priceVelocity to 0 (no history yet)
    """
    # Aggregate supply/demand by resource type
    aggregates: dict[int, dict[str, float]] = {}
    
    for resource_type in TRADABLE_RESOURCES:
        aggregates[resource_type.value] = {
            "supply": 0.0,
            "demand": 0.0,
            "price_times_supply": 0.0,
            "total_supply_for_avg": 0.0,
        }
    
    # Iterate through all local markets
    for local in local_markets:
        for listing in local.listings:
            rt_val = listing.resourceType.value
            if rt_val not in aggregates:
                # Skip non-tradable resources (e.g. Waste)
                continue
            
            agg = aggregates[rt_val]
            agg["supply"] += listing.supply
            agg["demand"] += listing.demand
            agg["price_times_supply"] += listing.price * listing.supply
            agg["total_supply_for_avg"] += listing.supply
    
    # Build listings for global market
    global_listings: list[ResourceListing] = []
    for resource_type in TRADABLE_RESOURCES:
        rt_val = resource_type.value
        agg = aggregates[rt_val]
        
        supply = agg["supply"]
        demand = agg["demand"]
        
        # Weighted average price
        if agg["total_supply_for_avg"] > 0:
            avg_price = agg["price_times_supply"] / agg["total_supply_for_avg"]
        else:
            avg_price = 1.0
        
        listing = ResourceListing(
            resourceType=resource_type,
            price=avg_price,
            supply=supply,
            demand=demand,
            priceVelocity=0.0,  # No history yet
            priceHistory=[],
        )
        global_listings.append(listing)
    
    return {
        "systemId": system_id,
        "listings": global_listings,
        "tick": tick,
        "marketCount": len(local_markets),
    }
