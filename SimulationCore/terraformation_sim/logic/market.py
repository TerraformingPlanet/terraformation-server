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
    DEFAULT_GROWTH_CONFIG,
    GoldbergTileState,
    GrowthConfig,
    LocalMarketState,
    PopulationTier,
    ResourceListing,
    SocialClass,
    ResourceId,
    TerrainType,
    WaterClassification,
)

# ── Constants ─────────────────────────────────────────────────────────────────

#: Resources that participate in the local market (Waste is excluded).
# Lazy-loaded to avoid circular imports (registry → __init__ → runtime → market)
def _get_resource_registry():
    from ..registry import RESOURCE_REGISTRY
    return RESOURCE_REGISTRY

def _get_tradable_resources() -> list[str]:
    return _get_resource_registry().tradable()

TRADABLE_RESOURCES: list[str] = _get_tradable_resources()

_PRICE_MIN = 0.1
_PRICE_MAX = 50.0
_PRICE_ELASTICITY = 0.2   # exponent on supply/demand ratio

# Mobility rates per tick
_POOR_TO_MIDDLE_RATE   = 0.01   # per employed worker
_MIDDLE_TO_POOR_RATE   = 0.01   # per unemployed worker
_MIDDLE_TO_RICH_RATE   = 0.005  # only when employment >= threshold
_RICH_EMPLOYMENT_THRESHOLD = 0.8

# Income defaults and clamp ranges per social class (Phase 9.6)
_INCOME_DEFAULTS: dict[SocialClass, float] = {
    SocialClass.Poor:   1.0,
    SocialClass.Middle: 4.0,
    SocialClass.Rich:   15.0,
}
_INCOME_CLAMP: dict[SocialClass, tuple[float, float]] = {
    SocialClass.Poor:   (0.5,  2.0),
    SocialClass.Middle: (2.0,  8.0),
    SocialClass.Rich:   (8.0, 30.0),
}
_INCOME_NUDGE_RATE = 0.001  # fractional nudge per tick based on employment


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


# ── Natural population growth (tile-centric) ─────────────────────────────────

# Number of ticks between growth cycles.
# 1 tick = 1 day  →  270 ticks ≈ 9 months (human gestation period convention)
NATURAL_GROWTH_INTERVAL: int = 270


def apply_natural_growth(
    tile: GoldbergTileState,
    food_per_capita: float = 1.0,
    config: GrowthConfig = DEFAULT_GROWTH_CONFIG,
) -> GoldbergTileState:
    """Apply one natural-growth cycle to a tile’s human population.

    Called every NATURAL_GROWTH_INTERVAL ticks (270 = 9 months at 1 tick/day).
    Returns an unchanged tile if there is no population or the tile is ocean/ice.

    Args:
        tile: The surface tile to update.
        food_per_capita: [0, 1] fraction of the population’s food needs that are met.
            0.0 = famine (max starvation); 1.0 = fully fed.
        config: Growth parameters. Pass a custom GrowthConfig for talent-tree /
            event overrides. Defaults to DEFAULT_GROWTH_CONFIG.

    Returns:
        A new GoldbergTileState with updated population list (model_copy pattern).
    """
    if not tile.population:
        return tile
    # Non-terrestrial tiles never have human populations
    if tile.terrainType in (TerrainType.Eau, TerrainType.Glace):
        return tile
    if tile.waterClassification in (WaterClassification.OpenOcean, WaterClassification.FrozenWater):
        return tile

    food_clamp = max(0.0, min(1.0, food_per_capita))
    net_birth = config.growthRate * config.growthMultiplier
    net_death = (
        config.deathRate
        + config.starvationModifier * (1.0 - food_clamp)
    ) * config.deathMultiplier

    new_tiers: list[PopulationTier] = []
    births_total = 0
    for tier in tile.population:
        if tier.count <= 0:
            new_tiers.append(tier)
            continue
        deaths = max(0, round(tier.count * net_death))
        surviving = max(0, tier.count - deaths)
        births_total += max(0, round(tier.count * net_birth))
        new_tiers.append(tier.model_copy(update={"count": surviving}))

    # Births accumulate into the Poor tier (new arrivals are always poor)
    if births_total > 0:
        updated = []
        added = False
        for tier in new_tiers:
            if tier.socialClass == SocialClass.Poor:
                updated.append(tier.model_copy(update={"count": tier.count + births_total}))
                added = True
            else:
                updated.append(tier)
        if not added:
            # No Poor tier yet — create one
            updated.append(PopulationTier(
                socialClass=SocialClass.Poor,
                count=births_total,
                avgIncome=_INCOME_DEFAULTS[SocialClass.Poor],
            ))
        new_tiers = updated

    return tile.model_copy(update={"population": new_tiers})


def auto_init_tile_population(tile: ClaimedTile) -> ClaimedTile:
    """If the tile has no population, seed it with 10 Poor workers.

    Call this in claim_tile_locked() when a ClaimedTile is first created.
    Returns a new ClaimedTile (Pydantic model is immutable-ish — use model_copy).
    """
    if tile.population:
        return tile
    seeded = [PopulationTier(socialClass=SocialClass.Poor, count=10, avgIncome=_INCOME_DEFAULTS[SocialClass.Poor])]
    return tile.model_copy(update={"population": seeded})


def compute_population_demand(tiles: list[ClaimedTile]) -> dict[str, float]:
    """Aggregate demand across all claimed tiles, summed across social classes.

    Uses avgIncome as a demand multiplier per person (Phase 9.6).
    Returns a dict keyed by resource_id (e.g. "Food", "Energy").
    """
    demand: dict[str, float] = {}
    for tile in tiles:
        for tier in tile.population:
            income_mult = tier.avgIncome if tier.avgIncome > 0.0 else 1.0
            for resource_id in TRADABLE_RESOURCES:
                rate = _get_resource_registry().demand_for_class(tier.socialClass.name, resource_id)
                demand[resource_id] = demand.get(resource_id, 0.0) + rate * tier.count * income_mult
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
        key = listing.resourceType
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
    - avgIncome is nudged each tick by employment (Phase 9.6)

    Returns a new ClaimedTile with updated population.
    """
    tiers: dict[SocialClass, int] = {
        SocialClass.Poor:   0,
        SocialClass.Middle: 0,
        SocialClass.Rich:   0,
    }
    incomes: dict[SocialClass, float] = dict(_INCOME_DEFAULTS)
    for tier in tile.population:
        tiers[tier.socialClass] = tiers.get(tier.socialClass, 0) + tier.count
        if tier.count > 0 and tier.avgIncome > 0.0:
            incomes[tier.socialClass] = tier.avgIncome

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

    # Nudge avgIncome by employment ratio (Phase 9.6)
    for sc in (SocialClass.Poor, SocialClass.Middle, SocialClass.Rich):
        incomes[sc] *= (1.0 + _INCOME_NUDGE_RATE * (employment_ratio - 0.5))
        lo, hi = _INCOME_CLAMP[sc]
        incomes[sc] = max(lo, min(hi, incomes[sc]))

    new_population = [
        PopulationTier(socialClass=SocialClass.Poor,   count=max(0, poor),   avgIncome=incomes[SocialClass.Poor]),
        PopulationTier(socialClass=SocialClass.Middle, count=max(0, middle), avgIncome=incomes[SocialClass.Middle]),
        PopulationTier(socialClass=SocialClass.Rich,   count=max(0, rich),   avgIncome=incomes[SocialClass.Rich]),
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
    aggregates: dict[str, dict[str, float]] = {}
    
    for resource_id in TRADABLE_RESOURCES:
        aggregates[resource_id] = {
            "supply": 0.0,
            "demand": 0.0,
            "price_times_supply": 0.0,
            "total_supply_for_avg": 0.0,
        }
    
    # Iterate through all local markets
    for local in local_markets:
        for listing in local.listings:
            resource_id = listing.resourceType
            if resource_id not in aggregates:
                # Skip non-tradable resources (e.g. Waste)
                continue
            
            agg = aggregates[resource_id]
            agg["supply"] += listing.supply
            agg["demand"] += listing.demand
            agg["price_times_supply"] += listing.price * listing.supply
            agg["total_supply_for_avg"] += listing.supply
    
    # Build listings for global market
    global_listings: list[ResourceListing] = []
    for resource_id in TRADABLE_RESOURCES:
        agg = aggregates[resource_id]
        
        supply = agg["supply"]
        demand = agg["demand"]
        
        # Weighted average price
        if agg["total_supply_for_avg"] > 0:
            avg_price = agg["price_times_supply"] / agg["total_supply_for_avg"]
        else:
            avg_price = 1.0
        
        listing = ResourceListing(
            resourceType=resource_id,
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
