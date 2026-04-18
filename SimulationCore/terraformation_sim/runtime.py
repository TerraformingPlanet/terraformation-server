from __future__ import annotations

import math
import threading
from uuid import uuid4

from .logic import apply_modifier_to_cell, apply_region_progress, can_apply_action, compute_goldberg_divisions, generate_interior_cells, generate_spherical_tiles, process_pending_actions, queue_action, summarize_region_cells, summarize_spherical_tiles, terraform_action_definitions, _goldberg_grid_dims
from .models import (
    AnyBodyState,
    BodyBase,
    BodyType,
    DebugCoherenceOverride,
    HexGridDebugSummary,
    HexStateModifier,
    InteriorZoneState,
    PendingTerraformAction,
    ProjectionDebugSummary,
    ProjectionState,
    RegionState,
    SimulationCellAddress,
    SimulationCellState,
    SimulationCoherenceState,
    SimulationCoordinates,
    SimulationEvent,
    SimulationEventType,
    SimulationSoilState,
    SimulationVector2State,
    SimulationWeatherState,
    SphericalBodyState,
    TerraformAction,
    TerraformActionDefinition,
    TerrainClass,
    TerrainType,
    WaterClassification,
    WorldLayer,
    WorldState,
    ZoneType,
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class InMemorySimulationRuntime:
    def __init__(self, tick_interval_seconds: float = 5.0, auto_resume: bool = False) -> None:
        self._tick_interval_seconds = max(0.1, tick_interval_seconds)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._tick_running = auto_resume
        self._tick_count = 0
        self._world_state = WorldState()
        self._region_cells: list[SimulationCellState] = []
        self._pending_actions: list[PendingTerraformAction] = []
        self._last_event = SimulationEvent(eventId=str(uuid4()), type=SimulationEventType.SnapshotCaptured, message="Runtime initialized")
        # Body registry: body_id → SphericalBodyState | InteriorZoneState
        self._bodies: dict[str, AnyBodyState] = {}
        self._active_body_id: str = ""
        self.bootstrap_demo()
        self._thread = threading.Thread(target=self._tick_loop, name="SimulationRuntime", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def health(self) -> dict:
        with self._lock:
            return {
                "status": "ok",
                "tickCount": self._tick_count,
                "tickRunning": self._tick_running,
                "activePlanetName": self._world_state.activePlanetName,
                "hasProjection": self._world_state.hasProjection,
                "hasRegion": self._world_state.hasRegion,
            }

    def bootstrap_demo(self,
                       planet_name: str = "Astra-Prime",
                       projection_override: DebugCoherenceOverride = DebugCoherenceOverride.Coast,
                       projection_water_level: float = 0.08) -> WorldState:
        with self._lock:
            projection = self._build_projection_state(planet_name, projection_override, projection_water_level)
            region = self._build_region_state(planet_name, SimulationCoordinates(latitude=0.47, longitude=0.18), self._tick_count)
            self._world_state = WorldState(
                isValid=True,
                tickCount=self._tick_count,
                tickRunning=self._tick_running,
                activePlanetName=planet_name,
                projectionOverride=projection_override,
                projectionWaterLevel=projection_water_level,
                hasProjection=True,
                projection=projection,
                hasRegion=True,
                region=region,
            )
            # Register the demo planet in the body registry
            self._register_spherical_body_locked(
                body_id=None,
                name=planet_name,
                body_type=BodyType.Planet,
                radius_km=6371.0,
                coherence_override=projection_override,
                water_level=projection_water_level,
                seed=42042,
            )
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.ProjectionLoaded,
                tickCount=self._tick_count,
                message=f"Demo world bootstrapped for {planet_name}",
                hasRegion=True,
                coordinates=region.coordinates,
            )
            return self._world_state.model_copy(deep=True)

    def world_state(self) -> WorldState:
        with self._lock:
            return self._world_state.model_copy(deep=True)

    def projection_state(self) -> ProjectionState:
        with self._lock:
            return self._world_state.projection.model_copy(deep=True)

    def region_state(self) -> RegionState:
        with self._lock:
            return self._world_state.region.model_copy(deep=True)

    def last_event(self) -> SimulationEvent:
        with self._lock:
            return self._last_event.model_copy(deep=True)

    def action_definitions(self) -> list[TerraformActionDefinition]:
        with self._lock:
            definitions = terraform_action_definitions()
            return [definitions[action].model_copy(deep=True) for action in sorted(definitions.keys(), key=int)]

    def open_region(self, latitude: float, longitude: float) -> RegionState:
        with self._lock:
            coordinates = SimulationCoordinates(latitude=_clamp01(latitude), longitude=_clamp01(longitude))
            region = self._build_region_state(self._world_state.activePlanetName or "Astra-Prime", coordinates, self._tick_count)
            self._world_state.hasRegion = True
            self._world_state.region = region
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.RegionLoaded,
                tickCount=self._tick_count,
                message="Region opened",
                hasRegion=True,
                coordinates=coordinates,
            )
            return region.model_copy(deep=True)

    def resume(self) -> WorldState:
        with self._lock:
            self._tick_running = True
            self._world_state.tickRunning = True
            self._last_event = SimulationEvent(eventId=str(uuid4()), type=SimulationEventType.TickAdvanced, tickCount=self._tick_count, message="Tick resumed")
            return self._world_state.model_copy(deep=True)

    def pause(self) -> WorldState:
        with self._lock:
            self._tick_running = False
            self._world_state.tickRunning = False
            self._last_event = SimulationEvent(eventId=str(uuid4()), type=SimulationEventType.TickAdvanced, tickCount=self._tick_count, message="Tick paused")
            return self._world_state.model_copy(deep=True)

    def advance_tick(self, steps: int = 1) -> WorldState:
        with self._lock:
            for _ in range(max(1, steps)):
                self._advance_tick_locked()
            return self._world_state.model_copy(deep=True)

    def queue_terraform_action(self, action: TerraformAction, cell: SimulationCellAddress | None = None) -> WorldState:
        with self._lock:
            if not self._region_cells:
                self._last_event = SimulationEvent(eventId=str(uuid4()), type=SimulationEventType.ActionRejected, tickCount=self._tick_count, message="No active region")
                return self._world_state.model_copy(deep=True)

            target = cell or self._region_cells[0].address
            target_cell = next((current for current in self._region_cells if current.address.q == target.q and current.address.r == target.r), None)
            if not can_apply_action(target_cell, action):
                self._last_event = SimulationEvent(
                    eventId=str(uuid4()),
                    type=SimulationEventType.ActionRejected,
                    tickCount=self._tick_count,
                    message=f"Action {action.name} rejected",
                    hasCell=True,
                    cell=target,
                )
                return self._world_state.model_copy(deep=True)

            queue_action(self._pending_actions, target, action)
            if target_cell is not None:
                self._world_state.region.hasSelectedCell = True
                self._world_state.region.selectedCell = target_cell.model_copy(deep=True)
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.ActionQueued,
                tickCount=self._tick_count,
                message=f"Action {action.name} queued",
                hasCell=True,
                cell=target,
            )
            return self._world_state.model_copy(deep=True)

    def apply_direct_cell_delta(self,
                                water_delta: float = 0.0,
                                temperature_delta: float = 0.0,
                                cell: SimulationCellAddress | None = None) -> WorldState:
        with self._lock:
            if not self._region_cells:
                return self._world_state.model_copy(deep=True)

            target = cell or self._region_cells[0].address
            for index, current in enumerate(self._region_cells):
                if current.address.q == target.q and current.address.r == target.r:
                    self._region_cells[index] = apply_modifier_to_cell(
                        current,
                        HexStateModifier(tempDelta=temperature_delta, waterDelta=water_delta),
                    )
                    self._world_state.region.hasSelectedCell = True
                    self._world_state.region.selectedCell = self._region_cells[index].model_copy(deep=True)
                    break

            self._world_state.region = apply_region_progress(self._world_state.region, self._region_cells)
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.CellUpdated,
                tickCount=self._tick_count,
                message="Cell updated directly",
                hasCell=True,
                cell=target,
            )
            return self._world_state.model_copy(deep=True)

    def _tick_loop(self) -> None:
        while not self._stop_event.wait(self._tick_interval_seconds):
            with self._lock:
                if self._tick_running:
                    self._advance_tick_locked()

    def _advance_tick_locked(self) -> None:
        self._tick_count += 1
        self._world_state.tickCount = self._tick_count
        self._world_state.tickRunning = self._tick_running

        if self._world_state.hasRegion:
            region = self._world_state.region
            self._region_cells, self._pending_actions = process_pending_actions(self._region_cells, self._pending_actions)
            if self._region_cells:
                for index, cell in enumerate(self._region_cells):
                    cell.temperature += 0.04 if index % 3 == 0 else 0.01
                    cell.waterRatio = _clamp01(cell.waterRatio + (0.004 if index % 4 == 0 else 0.001))
                    cell.flowAccumulation = min(999, cell.flowAccumulation + (1 if index == 0 else 0))
                    self._region_cells[index] = cell

            if region.hasSelectedCell and self._region_cells:
                cell = self._region_cells[0]
                cell.temperature += 0.08
                cell.waterRatio = _clamp01(cell.waterRatio + 0.003)
                cell.flowAccumulation = min(999, cell.flowAccumulation + 1)
                self._region_cells[0] = cell

            region = apply_region_progress(region, self._region_cells)
            self._world_state.region = region

        self._last_event = SimulationEvent(
            eventId=str(uuid4()),
            type=SimulationEventType.TickAdvanced,
            tickCount=self._tick_count,
            message="Tick advanced",
            hasRegion=self._world_state.hasRegion,
            coordinates=self._world_state.region.coordinates if self._world_state.hasRegion else SimulationCoordinates(),
        )

    def _build_projection_state(self,
                                planet_name: str,
                                projection_override: DebugCoherenceOverride,
                                projection_water_level: float) -> ProjectionState:
        base_water = _clamp01(0.52 + projection_water_level)
        summary = ProjectionDebugSummary(
            cols=48,
            rows=24,
            totalCells=1152,
            dryCells=312,
            coastCells=184,
            inlandWaterCells=98,
            openOceanCells=402,
            frozenWaterCells=34,
            rockTerrainCells=328,
            iceTerrainCells=52,
            toxicTerrainCells=24,
            waterTerrainCells=488,
            vegetationTerrainCells=210,
            metalTerrainCells=50,
            averageWaterRatio=base_water,
            averageTemperature=12.4,
        )
        return ProjectionState(
            isValid=True,
            planetName=planet_name,
            projectionOverride=projection_override,
            projectionWaterLevel=projection_water_level,
            summary=summary,
        )

    def _build_region_state(self, planet_name: str, coordinates: SimulationCoordinates, tick_count: int) -> RegionState:
        latitude_bias = math.cos(coordinates.latitude * math.pi)
        longitude_bias = math.sin(coordinates.longitude * math.pi)
        projected_water_ratio = _clamp01(0.45 + latitude_bias * 0.15 + longitude_bias * 0.1)
        deserticity = _clamp01(0.55 - projected_water_ratio * 0.6)
        oceanicity = _clamp01(projected_water_ratio * 0.95)
        frigidity = _clamp01(0.15 + (1.0 - abs(coordinates.latitude - 0.5) * 2.0) * 0.1)
        average_temperature = 18.0 - abs(coordinates.latitude - 0.5) * 42.0 + tick_count * 0.03
        terraformation_progress = _clamp01(0.14 + tick_count * 0.0025)

        selected_cell = SimulationCellState(
            address=SimulationCellAddress(q=3, r=-1),
            terrainName="Coastal Shelf" if projected_water_ratio > 0.48 else "Dry Basin",
            terrainType=TerrainType.Eau if projected_water_ratio > 0.5 else TerrainType.Roche,
            layer=WorldLayer.Surface,
            altitude=0.42,
            temperature=average_temperature + 1.2,
            waterRatio=_clamp01(projected_water_ratio + 0.08),
            toxinLevel=0.04,
            windVector=SimulationVector2State(x=0.8, y=0.2),
            windSpeed=0.34,
            rainShadow=False,
            hasRiver=projected_water_ratio > 0.42,
            flowAccumulation=8 + tick_count,
            terrainClass=TerrainClass.Channel if projected_water_ratio > 0.42 else TerrainClass.Basin,
            waterClassification=WaterClassification.Coast if projected_water_ratio > 0.5 else WaterClassification.InlandWater,
            hasDownstream=True,
            downstream=SimulationCellAddress(q=4, r=-1),
            hasOverflowOutlet=True,
            overflowOutlet=SimulationCellAddress(q=5, r=0),
            soil=SimulationSoilState(
                rockHardness=0.46,
                organicContent=0.32,
                porosity=0.52,
                mineralDensity=0.41,
                toxicSoil=False,
                thermalConductivity=0.28,
            ),
        )

        self._region_cells = self._build_region_cells(selected_cell, projected_water_ratio, average_temperature)
        self._pending_actions = []

        summary = HexGridDebugSummary(
            totalCells=91,
            dryCells=24,
            coastCells=14,
            inlandWaterCells=11,
            openOceanCells=16,
            frozenWaterCells=2,
            ridgeCells=10,
            basinCells=13,
            channelCells=15,
            sourceCells=4,
            riverCells=9,
            downstreamCells=18,
            overflowCells=3,
            rockTerrainCells=28,
            iceTerrainCells=3,
            toxicTerrainCells=2,
            waterTerrainCells=30,
            vegetationTerrainCells=22,
            metalTerrainCells=6,
            averageWaterRatio=projected_water_ratio,
            averageTemperature=average_temperature,
            maxFlowAccumulation=max((cell.flowAccumulation for cell in self._region_cells), default=selected_cell.flowAccumulation),
        )

        region = RegionState(
            isValid=True,
            seed=42042,
            planetName=planet_name,
            coordinates=coordinates,
            terraformationProgress=terraformation_progress,
            weather=SimulationWeatherState(
                prevailingWindDirection=SimulationVector2State(x=0.8, y=0.2),
                prevailingWindSpeed=0.34,
                precipitationRate=_clamp01(projected_water_ratio + 0.12),
                temperatureOffset=-4.0 + latitude_bias * 6.0,
                seasonalModifier=0.18,
            ),
            coherence=SimulationCoherenceState(
                dominantTerrainType=TerrainType.Eau if projected_water_ratio > 0.5 else TerrainType.Roche,
                projectedWaterRatio=projected_water_ratio,
                oceanicity=oceanicity,
                deserticity=deserticity,
                frigidity=frigidity,
                isExtremeOcean=projected_water_ratio > 0.85,
                isExtremeArid=projected_water_ratio < 0.08,
                isExtremeFrozen=average_temperature < -15.0,
            ),
            summary=summary,
            hasSelectedCell=True,
            selectedCell=selected_cell,
        )
        return apply_region_progress(region, self._region_cells)

    def _build_region_cells(self,
                            selected_cell: SimulationCellState,
                            projected_water_ratio: float,
                            average_temperature: float) -> list[SimulationCellState]:
        cells = [selected_cell.model_copy(deep=True)]
        for index in range(1, 24):
            dryness = index / 24.0
            water_ratio = _clamp01(projected_water_ratio + 0.18 - dryness * 0.28)
            temperature = average_temperature + 3.0 - dryness * 9.0
            terrain_type = TerrainType.Vegetation if water_ratio > 0.42 and temperature > 4.0 else (TerrainType.Eau if water_ratio > 0.58 else TerrainType.Roche)
            water_classification = WaterClassification.OpenOcean if water_ratio > 0.8 else (WaterClassification.Coast if water_ratio > 0.45 else WaterClassification.Dry)
            cells.append(
                SimulationCellState(
                    address=SimulationCellAddress(q=index % 6, r=-(index // 6)),
                    terrainName="Vegetated Shelf" if terrain_type == TerrainType.Vegetation else ("Water Shelf" if terrain_type == TerrainType.Eau else "Rock Shelf"),
                    terrainType=terrain_type,
                    layer=WorldLayer.Surface,
                    altitude=_clamp01(0.25 + dryness * 0.45),
                    temperature=temperature,
                    waterRatio=water_ratio,
                    toxinLevel=0.02 if index % 7 else 0.08,
                    windVector=SimulationVector2State(x=0.8, y=0.2),
                    windSpeed=0.24 + dryness * 0.18,
                    rainShadow=index % 5 == 0,
                    hasRiver=water_ratio > 0.48 and index % 3 == 0,
                    flowAccumulation=2 + index,
                    terrainClass=TerrainClass.Channel if water_ratio > 0.4 else TerrainClass.Ridge,
                    waterClassification=water_classification,
                    hasDownstream=index % 4 != 0,
                    downstream=SimulationCellAddress(q=(index + 1) % 6, r=-((index + 1) // 6)),
                    hasOverflowOutlet=index % 6 == 0,
                    overflowOutlet=SimulationCellAddress(q=(index + 2) % 6, r=-((index + 2) // 6)),
                    soil=SimulationSoilState(
                        rockHardness=_clamp01(0.3 + dryness * 0.4),
                        organicContent=_clamp01(0.5 - dryness * 0.35),
                        porosity=_clamp01(0.58 - dryness * 0.18),
                        mineralDensity=_clamp01(0.22 + dryness * 0.4),
                        toxicSoil=index % 11 == 0,
                        thermalConductivity=_clamp01(0.18 + dryness * 0.2),
                    ),
                )
            )
        return cells

    # ── Body registry ─────────────────────────────────────────────────────────

    def _register_spherical_body_locked(
        self,
        body_id: str | None,
        name: str,
        body_type: BodyType,
        radius_km: float,
        coherence_override: DebugCoherenceOverride,
        water_level: float,
        seed: int,
        parent_id: str | None = None,
    ) -> SphericalBodyState:
        """Create and store a SphericalBodyState; tiles generated lazily on first request."""
        divisions = compute_goldberg_divisions(radius_km)
        cols, rows = _goldberg_grid_dims(divisions)
        tile_count = cols * rows
        bid = body_id or str(uuid4())
        body = SphericalBodyState(
            bodyId=bid,
            bodyType=body_type,
            name=name,
            parentId=parent_id,
            seed=seed,
            radiusKm=radius_km,
            divisions=divisions,
            tileCount=tile_count,
            projectionOverride=coherence_override,
            waterLevel=water_level,
        )
        self._bodies[bid] = body
        if not self._active_body_id or body_type == BodyType.Planet:
            self._active_body_id = bid
        return body

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
                    body.divisions, body.projectionOverride, body.waterLevel, body.seed
                )
                cols, rows = _goldberg_grid_dims(body.divisions)
                body.summary = summarize_spherical_tiles(tiles, cols=cols, rows=rows)
                body.tiles = tiles
            start = page * size
            return [t.model_copy(deep=True) for t in body.tiles[start:start + size]]

    def get_body_tile(self, body_id: str, tile_id: int):
        """Return a single GoldbergTileState by tile_id."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                tiles = generate_spherical_tiles(
                    body.divisions, body.projectionOverride, body.waterLevel, body.seed
                )
                cols, rows = _goldberg_grid_dims(body.divisions)
                body.summary = summarize_spherical_tiles(tiles, cols=cols, rows=rows)
                body.tiles = tiles
            if tile_id < 0 or tile_id >= len(body.tiles):
                raise IndexError(f"tile_id {tile_id} out of range for body {body_id}")
            return body.tiles[tile_id].model_copy(deep=True)

    def apply_body_tile_delta(
        self,
        body_id: str,
        tile_id: int,
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
                    body.divisions, body.projectionOverride, body.waterLevel, body.seed
                )
            if tile_id < 0 or tile_id >= len(body.tiles):
                raise IndexError(f"tile_id {tile_id} out of range")
            tile = body.tiles[tile_id]
            tile.waterRatio = max(0.0, min(1.0, tile.waterRatio + water_delta))
            tile.temperature += temperature_delta
            from .logic import is_tile_habitable
            tile.isHabitable = is_tile_habitable(tile.terrainType, tile.temperature, tile.waterRatio)
            return tile.model_copy(deep=True)

    def apply_body_tile_action(self, body_id: str, tile_id: int, action: TerraformAction):
        """Apply an immediate terraform action modifier to a surface tile."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                body.tiles = generate_spherical_tiles(
                    body.divisions, body.projectionOverride, body.waterLevel, body.seed
                )
            if tile_id < 0 or tile_id >= len(body.tiles):
                raise IndexError(f"tile_id {tile_id} out of range")
            definitions = terraform_action_definitions()
            modifier = definitions[action].modifier
            tile = body.tiles[tile_id]
            tile.waterRatio = max(0.0, min(1.0, tile.waterRatio + modifier.waterDelta))
            tile.temperature += modifier.tempDelta
            tile.toxinLevel = max(0.0, min(1.0, tile.toxinLevel + modifier.toxinDelta))
            from .logic import is_tile_habitable
            tile.isHabitable = is_tile_habitable(tile.terrainType, tile.temperature, tile.waterRatio)
            return tile.model_copy(deep=True)

    def register_interior_zone(
        self,
        parent_body_id: str,
        zone_type: ZoneType,
        cols: int,
        rows: int,
        parent_tile_id: int | None = None,
        seed: int | None = None,
    ) -> InteriorZoneState:
        """Create an interior zone attached to a body tile and populate its hex cells."""
        with self._lock:
            parent = self._bodies.get(parent_body_id)
            if parent is None:
                raise KeyError(f"Parent body not found: {parent_body_id}")
            effective_seed = seed if seed is not None else (hash(f"{parent_body_id}{zone_type}{parent_tile_id}") & 0x7FFFFFFF)
            zone_id = str(uuid4())
            cells = generate_interior_cells(cols, rows, zone_type, effective_seed)
            summary = summarize_region_cells(cells)
            zone = InteriorZoneState(
                bodyId=zone_id,
                bodyType=BodyType.SpaceStation if zone_type in (ZoneType.Station, ZoneType.Ship) else BodyType.Planet,
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
            # Link zone to parent tile if applicable
            if parent_tile_id is not None and isinstance(parent, SphericalBodyState) and parent.tiles:
                if 0 <= parent_tile_id < len(parent.tiles):
                    parent.tiles[parent_tile_id].childZoneIds.append(zone_id)
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