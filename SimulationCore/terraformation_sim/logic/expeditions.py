"""
Expedition & Trade Route logic — Phase 9.2 Runtime Expeditions.

Pure functions: no side effects, no registry access, no `self`.
All state mutations happen in runtime.py via _process_*_tick_locked().
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import h3 as _h3

if TYPE_CHECKING:
    from ..models import BuildingData, LocalMarketState, TradeRoute

from ..models import (
    BuildingType,
    LocalMarketState,
    ResourceListing,
    TradeRoute,
    TradeRouteActivityStatus,
    TradeRouteType,
)

# ── Expedition Configuration ──────────────────────────────────────────────────
# All constants grouped here for easy migration to config file later.

_EXPEDITION_CONFIG = {
    "ORBITAL_TICKS": 10,
    "LAND_TICKS_PER_HOP": 5,
    "MARITIME_TICKS_PER_HOP": 3,
    "LAND_MIN_TICKS": 5,
    "MARITIME_MIN_TICKS": 5,
    "FAIL_PROB": 0.02,
    "DELAY_TICKS": 2,
    "DELAY_PROB": 0.05,
    "KNOWLEDGE_TRANSFER_TICKS": 50,
    "PORT_MALUS": 0.5,
    "PRICE_STEP": 0.1,
    "ROUTE_TYPE_ATTENUATION": {
        "Land": 0.7,
        "Maritime": 0.8,
        "Orbital": 0.9,
    },
}

# ── Route type to building type mapping ──────────────────────────────────────

_ROUTE_TYPE_TO_BUILDING: dict[TradeRouteType, BuildingType] = {
    TradeRouteType.Land: BuildingType.Road,
    TradeRouteType.Maritime: BuildingType.SeaPort,
    TradeRouteType.Orbital: BuildingType.Spaceport,
}


# ── Public functions ──────────────────────────────────────────────────────────


def compute_expedition_path(
    from_tile: str, to_tile: str, route_type: TradeRouteType
) -> list[str]:
    """
    Compute the tile path for an expedition.

    Args:
        from_tile: Starting tile ID (H3)
        to_tile: Destination tile ID (H3)
        route_type: TradeRouteType.Land, Maritime, or Orbital

    Returns:
        List of tile IDs representing the path (includes from_tile and to_tile)
    """
    if route_type == TradeRouteType.Orbital:
        # Orbital routes are direct (no BFS required)
        return [from_tile, to_tile]

    # Land and Maritime routes use H3 path finding
    try:
        path = _h3.grid_path_cells(from_tile, to_tile)
        if path:
            return list(path)
    except Exception:
        # Fallback if path finding fails (e.g., tiles on different bodies)
        pass

    # Fallback: direct connection
    return [from_tile, to_tile]


def compute_expedition_total_ticks(path: list[str], route_type: TradeRouteType) -> int:
    """
    Compute the total number of ticks for an expedition to complete.

    Args:
        path: List of tile IDs in the route
        route_type: TradeRouteType enum

    Returns:
        Number of ticks until arrival
    """
    cfg = _EXPEDITION_CONFIG

    if route_type == TradeRouteType.Orbital:
        return cfg["ORBITAL_TICKS"]
    elif route_type == TradeRouteType.Land:
        ticks = max(cfg["LAND_MIN_TICKS"], len(path) * cfg["LAND_TICKS_PER_HOP"])
        return ticks
    elif route_type == TradeRouteType.Maritime:
        ticks = max(
            cfg["MARITIME_MIN_TICKS"], len(path) * cfg["MARITIME_TICKS_PER_HOP"]
        )
        return ticks
    else:
        return cfg["ORBITAL_TICKS"]  # Default fallback


def compute_route_efficiency(
    route: TradeRoute, all_buildings: list[BuildingData]
) -> tuple[float, float, float]:
    """
    Recalculate route efficiency based on port status.

    Args:
        route: TradeRoute instance
        all_buildings: All buildings in the simulation

    Returns:
        Tuple of (portMalusFrom, portMalusTo, currentEfficiency)
        where efficiency = baseEfficiency * (1 - malusFrom) * (1 - malusTo)
    """
    cfg = _EXPEDITION_CONFIG
    required_building_type = _ROUTE_TYPE_TO_BUILDING.get(
        route.routeType, BuildingType.Spaceport
    )

    # Check if port building exists on fromTile
    port_from_exists = any(
        b.tileId == route.fromTileId and b.buildingType == required_building_type
        for b in all_buildings
    )
    port_malus_from = 0.0 if port_from_exists else cfg["PORT_MALUS"]

    # Check if port building exists on toTile
    port_to_exists = any(
        b.tileId == route.toTileId and b.buildingType == required_building_type
        for b in all_buildings
    )
    port_malus_to = 0.0 if port_to_exists else cfg["PORT_MALUS"]

    # Compute current efficiency
    current_efficiency = route.baseEfficiency * (1.0 - port_malus_from) * (
        1.0 - port_malus_to
    )

    return port_malus_from, port_malus_to, current_efficiency


def propagate_prices(
    market_from: LocalMarketState,
    market_to: LocalMarketState,
    attenuation: float,
) -> tuple[LocalMarketState, LocalMarketState]:
    """
    Propagate prices between two connected markets via trade route.

    Price convergence: new_price = price + attenuation * (other_price - price) * step
    where step = PRICE_STEP (0.1).

    Args:
        market_from: Source market
        market_to: Destination market
        attenuation: Attenuation factor [0..1] based on route type and efficiency

    Returns:
        Tuple of updated (market_from, market_to)
    """
    cfg = _EXPEDITION_CONFIG
    step = cfg["PRICE_STEP"]

    # Build mapping of resource to listing for fast lookup
    from_listings = {lst.resourceType: lst for lst in market_from.listings}
    to_listings = {lst.resourceType: lst for lst in market_to.listings}

    # Update listings in from market
    new_from_listings: list[ResourceListing] = []
    for listing in market_from.listings:
        if listing.resourceType in to_listings:
            to_listing = to_listings[listing.resourceType]
            price_delta = attenuation * (to_listing.price - listing.price) * step
            new_price = listing.price + price_delta
            new_listing = listing.model_copy(update={"price": max(0.1, new_price)})
            new_from_listings.append(new_listing)
        else:
            new_from_listings.append(listing)

    # Update listings in to market
    new_to_listings: list[ResourceListing] = []
    for listing in market_to.listings:
        if listing.resourceType in from_listings:
            from_listing = from_listings[listing.resourceType]
            price_delta = attenuation * (from_listing.price - listing.price) * step
            new_price = listing.price + price_delta
            new_listing = listing.model_copy(update={"price": max(0.1, new_price)})
            new_to_listings.append(new_listing)
        else:
            new_to_listings.append(listing)

    # Return updated markets
    updated_from = market_from.model_copy(update={"listings": new_from_listings})
    updated_to = market_to.model_copy(update={"listings": new_to_listings})

    return updated_from, updated_to
