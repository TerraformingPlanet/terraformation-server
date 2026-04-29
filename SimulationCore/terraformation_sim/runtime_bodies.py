from __future__ import annotations

from uuid import uuid4

from .models import (
    AnyBodyState,
    AtmosphericComposition,
    AtmosphericGas,
    ATMOSPHERE_PRESETS,
    BodyBase,
    BodyType,
    DebugCoherenceOverride,
    GoldbergTileState,
    InteriorZoneState,
    SphericalBodyState,
    TerraformAction,
    ZoneType,
)
from .logic import (
    generate_interior_cells,
    generate_spherical_tiles,
    init_sub_hexes,
    is_tile_habitable,
    summarize_region_cells,
    summarize_spherical_tiles,
    terraform_action_definitions,
    _body_h3_resolution,
    GENERATION_VERSION,
)


class BodiesMixin:
    """Spherical body and interior-zone registry, tile access, atmosphere, and terraform actions.

    State accessed via self:
        self._lock, self._bodies, self._active_body_id, self._lod_tile_cache,
        self._tile_ownership, self._tick_count, self._repo
    """

    # ── Body registration (called by BootstrapMixin) ──────────────────────────

    def _register_spherical_body_locked(
        self,
        body_id: str | None,
        name: str,
        body_type: BodyType,
        radius_km: float,
        coherence_override: DebugCoherenceOverride,
        water_level: float,
        seed: int,
        atmosphere: AtmosphericComposition | None = None,
        atmosphere_density: float | None = None,
        parent_id: str | None = None,
    ) -> SphericalBodyState:
        """Register a new spherical body. Must be called with lock held."""
        if atmosphere is None:
            if atmosphere_density is None:
                _atmo_defaults = {
                    DebugCoherenceOverride.Ocean:  0.65,
                    DebugCoherenceOverride.Arid:   0.15,
                    DebugCoherenceOverride.Frozen: 0.30,
                    DebugCoherenceOverride.Coast:  0.70,
                    DebugCoherenceOverride.Basin:  0.50,
                    DebugCoherenceOverride.None_:  0.50,
                }
                atmosphere_density = _atmo_defaults.get(coherence_override, 0.50)
            if atmosphere_density <= 0.01:
                atmosphere = ATMOSPHERE_PRESETS["vacuum"]
            elif atmosphere_density <= 0.05:
                atmosphere = AtmosphericComposition(
                    totalPressureKpa=atmosphere_density * 101.3,
                    gases=[],
                )
            else:
                atmosphere = AtmosphericComposition(
                    totalPressureKpa=atmosphere_density * 101.3,
                    gases=[
                        AtmosphericGas(name="N2",  fraction=0.78, greenhouseCoeff=0.0, molarMass=28.0),
                        AtmosphericGas(name="CO2", fraction=0.02, greenhouseCoeff=1.0, molarMass=44.0),
                        AtmosphericGas(name="O2",  fraction=0.20, greenhouseCoeff=0.0, molarMass=32.0),
                    ],
                )
        h3_res = _body_h3_resolution(radius_km)
        tile_count = 2 + 120 * (7 ** h3_res)
        bid = body_id or str(uuid4())
        body = SphericalBodyState(
            bodyId=bid,
            bodyType=body_type,
            name=name,
            parentId=parent_id,
            seed=seed,
            radiusKm=radius_km,
            h3Resolution=h3_res,
            tileCount=tile_count,
            projectionOverride=coherence_override,
            waterLevel=water_level,
            atmosphere=atmosphere,
        )
        self._bodies[bid] = body
        if not self._active_body_id or body_type == BodyType.Planet:
            self._active_body_id = bid
        self._repo.save_body(body)
        return body

    # ── Public body API ────────────────────────────────────────────────────────

    def list_bodies(self) -> list[BodyBase]:
        """Return all registered bodies without tiles/cells."""
        with self._lock:
            return [b.model_copy(deep=True, update={"tiles": [], "cells": []}) for b in self._bodies.values()]

    def get_body(self, body_id: str) -> AnyBodyState:
        """Return a body's metadata without tiles/cells."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            return body.model_copy(deep=True, update={"tiles": [], "cells": []})

    def get_body_tiles(self, body_id: str, page: int = 0, size: int = 100) -> list:
        """Return a paginated list of GoldbergTileState for a spherical body.
        Tiles are generated on first access and cached in the body object.
        """
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
                body.summary = summarize_spherical_tiles(tiles)
                body.tiles = tiles
                self._repo.save_tiles_bulk(body.bodyId, tiles)
            start = page * size
            return [t.model_copy(deep=True) for t in body.tiles[start:start + size]]

    def get_body_tiles_lod(
        self, body_id: str, h3_resolution: int, page: int = 0, size: int = 200
    ) -> list:
        """Return tiles at a different H3 resolution (LOD). Resolution is clamped to [0, 3]."""
        h3_resolution = min(max(0, h3_resolution), 3)
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if h3_resolution == body.h3Resolution:
                return self.get_body_tiles(body_id, page=page, size=size)
            cache_key = (body_id, h3_resolution)
            cached = self._lod_tile_cache.get(cache_key)
            if cached is not None:
                start = page * size
                return [t.model_copy(deep=True) for t in cached[start:start + size]]
            override, water, seed, atmo = (
                body.projectionOverride, body.waterLevel, body.seed, body.atmosphereDensity
            )
        tiles = generate_spherical_tiles(h3_resolution, override, water, seed, atmo)
        with self._lock:
            if body_id in self._bodies:
                self._lod_tile_cache[(body_id, h3_resolution)] = tiles
        start = page * size
        return [t.model_copy(deep=True) for t in tiles[start:start + size]]

    def get_body_tile(self, body_id: str, tile_id: str):
        """Return a single GoldbergTileState by H3 tile_id string."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
                body.summary = summarize_spherical_tiles(tiles)
                body.tiles = tiles
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            # Lazy-init sub-hexes on first access
            if not tile.subHexes:
                sub_hexes = init_sub_hexes(tile)
                tile = tile.model_copy(update={"subHexes": sub_hexes})
                body.tiles = [tile if t.tileId == tile_id else t for t in body.tiles]
            return tile.model_copy(deep=True)

    def get_body_tile_neighbors(self, body_id: str, tile_id: str) -> list:
        """Return the neighboring GoldbergTileStates of a given H3 tile (up to 6)."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
                body.summary = summarize_spherical_tiles(tiles)
                body.tiles = tiles
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            neighbor_ids = set(tile.neighborIds)
            return [t.model_copy(deep=True) for t in body.tiles if t.tileId in neighbor_ids]

    def get_tile_ecology(self, body_id: str, tile_id: str) -> list:
        """Return the species list for a given tile."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
                body.summary = summarize_spherical_tiles(tiles)
                body.tiles = tiles
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            return list(tile.species)

    def get_body_tile_at(self, body_id: str, lat: float, lon: float):
        """Return the tile whose H3 cell contains the given lat/lon coordinates."""
        import h3 as _h3
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
                body.summary = summarize_spherical_tiles(tiles)
                body.tiles = tiles
            cell = _h3.latlng_to_cell(lat, lon, body.h3Resolution)
            tile = next((t for t in body.tiles if t.tileId == cell), None)
            if tile is None:
                raise KeyError(f"No tile at lat={lat}, lon={lon} on body {body_id}")
            return tile.model_copy(deep=True)

    def apply_body_tile_delta(
        self,
        body_id: str,
        tile_id: str,
        water_delta: float = 0.0,
        temperature_delta: float = 0.0,
    ):
        """Apply additive water/temperature deltas to a surface tile."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                body.tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            tile.waterRatio = max(0.0, min(1.0, tile.waterRatio + water_delta))
            tile.temperature += temperature_delta
            tile.isHabitable = is_tile_habitable(tile.terrainType, tile.temperature, tile.waterRatio)
            if not body.isModified:
                body.isModified = True
                body.generationVersion = GENERATION_VERSION
                self._repo.save_body(body)
            self._repo.update_tile_fields(
                body_id, tile_id,
                water_ratio=tile.waterRatio,
                temperature=tile.temperature,
                toxin_level=tile.toxinLevel,
            )
            return tile.model_copy(deep=True)

    def apply_body_tile_action(self, body_id: str, tile_id: str, action: TerraformAction):
        """Apply an immediate terraform action modifier to a surface tile."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                body.tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            definitions = terraform_action_definitions()
            modifier = definitions[action].modifier
            tile.waterRatio = max(0.0, min(1.0, tile.waterRatio + modifier.waterDelta))
            tile.temperature += modifier.tempDelta
            tile.toxinLevel = max(0.0, min(1.0, tile.toxinLevel + modifier.toxinDelta))
            tile.isHabitable = is_tile_habitable(tile.terrainType, tile.temperature, tile.waterRatio)
            if not body.isModified:
                body.isModified = True
                body.generationVersion = GENERATION_VERSION
                self._repo.save_body(body)
            self._repo.update_tile_fields(
                body_id, tile_id,
                water_ratio=tile.waterRatio,
                temperature=tile.temperature,
                toxin_level=tile.toxinLevel,
            )
            return tile.model_copy(deep=True)

    # ── Atmosphere API ─────────────────────────────────────────────────────────

    def get_body_atmosphere(self, body_id: str) -> dict:
        """Return the atmospheric composition and equilibrium temperature of a body."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} has no atmosphere (interior zone)")
            return {
                "atmosphere": body.atmosphere.model_copy(deep=True),
                "equilibriumTemperature": body.equilibriumTemperature,
                "luminosityLsun": body.luminosityLsun,
            }

    def patch_atmosphere(
        self, body_id: str, gas_name: str, fraction_delta: float
    ) -> AtmosphericComposition:
        """Add fraction_delta to a named gas in a body's atmosphere (clamped to [0, 1])."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} has no atmosphere")
            gas = next((g for g in body.atmosphere.gases if g.name.upper() == gas_name.upper()), None)
            if gas is None:
                raise KeyError(f"Gas '{gas_name}' not tracked in body {body_id} atmosphere")
            gas.fraction = max(0.0, min(1.0, gas.fraction + fraction_delta))
            body.isModified = True
            self._repo.save_body(body)
            return body.atmosphere.model_copy(deep=True)

    def apply_tile_atmosphere_delta(
        self,
        body_id: str,
        tile_id: str,
        co2_delta: float = 0.0,
        o2_delta: float = 0.0,
    ):
        """Set per-tick atmospheric deltas on a tile (from a building/plant action)."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                body.tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            tile.atmosphereDeltaCo2 = co2_delta
            tile.atmosphereDeltaO2  = o2_delta
            return tile.model_copy(deep=True)

    # ── Interior zones ─────────────────────────────────────────────────────────

    def register_interior_zone(
        self,
        parent_body_id: str,
        zone_type: ZoneType,
        cols: int,
        rows: int,
        parent_tile_id: str | None = None,
        seed: int | None = None,
    ) -> InteriorZoneState:
        """Create an interior zone attached to a body tile and populate its hex cells."""
        with self._lock:
            parent = self._bodies.get(parent_body_id)
            if parent is None:
                raise KeyError(f"Parent body not found: {parent_body_id}")
            effective_seed = (
                seed if seed is not None
                else (hash(f"{parent_body_id}{zone_type}{parent_tile_id}") & 0x7FFFFFFF)
            )
            zone_id = str(uuid4())
            cells = generate_interior_cells(cols, rows, zone_type, effective_seed)
            summary = summarize_region_cells(cells)
            zone = InteriorZoneState(
                bodyId=zone_id,
                bodyType=(
                    BodyType.SpaceStation
                    if zone_type in (ZoneType.Station, ZoneType.Ship)
                    else BodyType.Planet
                ),
                name=f"{zone_type.name} ({parent.name})",
                parentId=parent_body_id,
                seed=effective_seed,
                zoneType=zone_type,
                parentTileId=parent_tile_id,
                cols=cols,
                rows=rows,
                summary=summary,
                cells=cells,
            )
            self._bodies[zone_id] = zone
            if parent_tile_id is not None and isinstance(parent, SphericalBodyState) and parent.tiles:
                tile = next((t for t in parent.tiles if t.tileId == parent_tile_id), None)
                if tile is not None:
                    tile.childZoneIds.append(zone_id)
            if isinstance(parent, SphericalBodyState) and not parent.isModified:
                parent.isModified = True
                parent.generationVersion = GENERATION_VERSION
                self._repo.save_body(parent)
            self._repo.save_body(zone)
            return zone.model_copy(deep=True)

    def get_interior_zone(self, zone_id: str) -> InteriorZoneState:
        """Return an interior zone with all cells populated."""
        with self._lock:
            body = self._bodies.get(zone_id)
            if body is None:
                raise KeyError(f"Zone not found: {zone_id}")
            if not isinstance(body, InteriorZoneState):
                raise TypeError(f"Body {zone_id} is not an interior zone")
            return body.model_copy(deep=True)
