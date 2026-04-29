from __future__ import annotations

import math
from uuid import uuid4

from .models import (
    BodyType,
    DebugCoherenceOverride,
    GalacticPosition,
    OrbitalParameters,
    RouteStatus,
    SolarSystemState,
    SpaceTravel,
    SphericalBodyState,
    StellarRoute,
    TICKS_PER_LIGHT_YEAR,
    TravelStatus,
)
from .logic import compute_body_position_at_tick


class GalaxyMixin:
    """Galaxy layer: solar systems, stellar routes, space travel, and body positions.

    State accessed via self:
        self._lock, self._bodies, self._solar_systems, self._stellar_routes,
        self._space_travels, self._tick_count, self._corporations, self._repo
    """

    # ── Internal helpers ────────────────────────────────────────────────────────

    def _bootstrap_galaxy_locked(self) -> None:
        """Create Kepler-442 home system and distant Sol system. Lock must be held."""
        if self._solar_systems:
            return

        def _make_system(name: str, x: float, y: float, z: float) -> SolarSystemState:
            sid = str(uuid4())
            system = SolarSystemState(
                systemId=sid, name=name,
                position=GalacticPosition(x=x, y=y, z=z),
            )
            self._solar_systems[sid] = system
            self._repo.save_solar_system(system)
            return system

        def _add_star(
            system: SolarSystemState, name: str, radius_km: float,
            spectral: str, seed: int, orbital: OrbitalParameters | None = None,
        ) -> SphericalBodyState:
            body = self._register_spherical_body_locked(
                body_id=None, name=name, body_type=BodyType.Star,
                radius_km=radius_km, coherence_override=DebugCoherenceOverride.None_,
                water_level=0.0, seed=seed,
            )
            body.spectralType = spectral
            body.systemId = system.systemId
            body.orbitalParams = orbital
            if system.rootBodyId == "":
                system.rootBodyId = body.bodyId
            system.bodyIds.append(body.bodyId)
            self._repo.save_body(body)
            self._repo.save_solar_system(system)
            return body

        def _add_body(
            system: SolarSystemState, name: str, body_type: BodyType,
            radius_km: float, water_level: float, seed: int,
            orbital: OrbitalParameters, parent_id: str | None = None,
            spectral: str = "",
        ) -> SphericalBodyState:
            body = self._register_spherical_body_locked(
                body_id=None, name=name, body_type=body_type,
                radius_km=radius_km,
                coherence_override=(
                    DebugCoherenceOverride.Ocean if water_level > 0.5
                    else DebugCoherenceOverride.Arid if water_level < 0.05
                    else DebugCoherenceOverride.Coast
                ),
                water_level=water_level, seed=seed, parent_id=parent_id,
            )
            body.systemId = system.systemId
            body.orbitalParams = orbital
            body.spectralType = spectral
            system.bodyIds.append(body.bodyId)
            self._repo.save_body(body)
            self._repo.save_solar_system(system)
            return body

        # ── Kepler-442 (player home system) ──────────────────────────
        kepler = _make_system("Kepler-442", 0.0, 0.0, 0.0)
        kepler_star = _add_star(kepler, "Kepler-442", 513000.0, "K", 3001)

        active_planet = next(
            (b for b in self._bodies.values()
             if isinstance(b, SphericalBodyState) and b.bodyType == BodyType.Planet),
            None,
        )
        if active_planet is not None:
            active_planet.systemId = kepler.systemId
            active_planet.orbitalParams = OrbitalParameters(
                semiMajorAxisAU=0.409, eccentricity=0.0, periodTicks=112,
            )
            active_planet.parentId = kepler_star.bodyId
            kepler.bodyIds.append(active_planet.bodyId)
            self._repo.save_body(active_planet)
            self._repo.save_solar_system(kepler)

        # ── Sol (hidden exploration target) ──────────────────────────
        sol = _make_system("Sol", 1200.0, 0.0, 0.0)
        sol.isDiscovered = False
        self._repo.save_solar_system(sol)
        sun = _add_star(sol, "Sun", 695700.0, "G2V", 1001)
        _add_body(
            sol, "Earth", BodyType.Planet, 6371.0, 0.71, 1004,
            OrbitalParameters(semiMajorAxisAU=1.0, eccentricity=0.017, periodTicks=365),
            sun.bodyId,
        )

        # ── Hidden route Kepler-442 → Sol ─────────────────────────────
        self._create_stellar_route_locked(
            from_system_id=kepler.systemId,
            to_system_id=sol.systemId,
            travel_time_modifier=1.0,
            description="Signal interstellaire capté par les sondes de Kepler-442b.",
        )

    def _create_stellar_route_locked(
        self,
        from_system_id: str,
        to_system_id: str,
        travel_time_modifier: float = 1.0,
        description: str = "",
        status: RouteStatus = RouteStatus.Hidden,
    ) -> StellarRoute:
        """Create a stellar route; distance calculated from system positions. Lock must be held."""
        src = self._solar_systems.get(from_system_id)
        dst = self._solar_systems.get(to_system_id)
        if src is None:
            raise KeyError(f"System not found: {from_system_id}")
        if dst is None:
            raise KeyError(f"System not found: {to_system_id}")
        dx = src.position.x - dst.position.x
        dy = src.position.y - dst.position.y
        dz = src.position.z - dst.position.z
        dist_ly = math.sqrt(dx * dx + dy * dy + dz * dz)
        route = StellarRoute(
            routeId=str(uuid4()),
            fromSystemId=from_system_id,
            toSystemId=to_system_id,
            distanceLy=round(dist_ly, 4),
            travelTimeModifier=travel_time_modifier,
            status=status,
            description=description,
        )
        self._stellar_routes[route.routeId] = route
        self._repo.save_stellar_route(route)
        return route

    # ── Solar systems ──────────────────────────────────────────────────────────

    def wipe_galaxy(self) -> dict:
        """Wipe all galaxy data and re-bootstrap. For testing / world-reset."""
        with self._lock:
            deleted_bodies = sum(
                1 for b in self._bodies.values()
                if isinstance(b, SphericalBodyState) and b.systemId
            )
            deleted_systems = len(self._solar_systems)
            deleted_routes = len(self._stellar_routes)
            deleted_travels = len(self._space_travels)

        self.bootstrap()

        with self._lock:
            return {
                "deleted": {
                    "bodies": deleted_bodies,
                    "systems": deleted_systems,
                    "routes": deleted_routes,
                    "travels": deleted_travels,
                },
                "created": {
                    "systems": len(self._solar_systems),
                    "bodies": sum(
                        1 for b in self._bodies.values()
                        if isinstance(b, SphericalBodyState) and b.systemId
                    ),
                    "routes": len(self._stellar_routes),
                },
            }

    def create_solar_system(
        self,
        name: str,
        x: float,
        y: float,
        z: float,
        description: str = "",
    ) -> SolarSystemState:
        with self._lock:
            system = SolarSystemState(
                systemId=str(uuid4()),
                name=name,
                position=GalacticPosition(x=x, y=y, z=z),
                description=description,
            )
            self._solar_systems[system.systemId] = system
            self._repo.save_solar_system(system)
            return system.model_copy(deep=True)

    def get_solar_system(self, system_id: str) -> SolarSystemState:
        with self._lock:
            system = self._solar_systems.get(system_id)
            if system is None:
                raise KeyError(f"System not found: {system_id}")
            return system.model_copy(deep=True)

    def list_solar_systems(self) -> list[SolarSystemState]:
        with self._lock:
            return [s.model_copy(deep=True) for s in self._solar_systems.values()]

    def add_body_to_system(
        self,
        system_id: str,
        body_type: BodyType,
        name: str,
        radius_km: float,
        water_level: float = 0.0,
        seed: int = 0,
        parent_body_id: str | None = None,
        orbital_semi_major_axis_au: float = 1.0,
        orbital_eccentricity: float = 0.0,
        orbital_inclination_deg: float = 0.0,
        orbital_initial_phase_deg: float = 0.0,
        orbital_period_ticks: int = 365,
        spectral_type: str = "",
        is_system_root: bool = False,
    ) -> SphericalBodyState:
        with self._lock:
            system = self._solar_systems.get(system_id)
            if system is None:
                raise KeyError(f"System not found: {system_id}")
            coherence = (
                DebugCoherenceOverride.Ocean if water_level > 0.5
                else DebugCoherenceOverride.Arid if water_level < 0.05
                else DebugCoherenceOverride.Coast
            )
            effective_seed = seed or (hash(f"{system_id}{name}") & 0x7FFFFFFF)
            body = self._register_spherical_body_locked(
                body_id=None, name=name, body_type=body_type,
                radius_km=radius_km, coherence_override=coherence,
                water_level=water_level, seed=effective_seed,
                parent_id=parent_body_id,
            )
            body.systemId = system_id
            body.spectralType = spectral_type
            if not is_system_root:
                body.orbitalParams = OrbitalParameters(
                    semiMajorAxisAU=orbital_semi_major_axis_au,
                    eccentricity=orbital_eccentricity,
                    inclinationDeg=orbital_inclination_deg,
                    initialPhaseDeg=orbital_initial_phase_deg,
                    periodTicks=orbital_period_ticks,
                )
            if is_system_root or system.rootBodyId == "":
                system.rootBodyId = body.bodyId
            system.bodyIds.append(body.bodyId)
            self._repo.save_body(body)
            self._repo.save_solar_system(system)
            return body.model_copy(deep=True, update={"tiles": [], "cells": []})

    def remove_body_from_system(self, system_id: str, body_id: str) -> None:
        with self._lock:
            system = self._solar_systems.get(system_id)
            if system is None:
                raise KeyError(f"System not found: {system_id}")
            if body_id not in self._bodies:
                raise KeyError(f"Body not found: {body_id}")
            system.bodyIds = [b for b in system.bodyIds if b != body_id]
            if system.rootBodyId == body_id:
                system.rootBodyId = system.bodyIds[0] if system.bodyIds else ""
            del self._bodies[body_id]
            self._repo.save_solar_system(system)

    def get_body_position_at_tick(self, body_id: str, tick: int | None = None) -> dict:
        with self._lock:
            effective_tick = tick if tick is not None else self._tick_count
            return compute_body_position_at_tick(body_id, effective_tick, self._bodies)

    # ── Stellar routes ─────────────────────────────────────────────────────────

    def create_stellar_route(
        self,
        from_system_id: str,
        to_system_id: str,
        travel_time_modifier: float = 1.0,
        description: str = "",
        status: RouteStatus = RouteStatus.Hidden,
    ) -> StellarRoute:
        with self._lock:
            return self._create_stellar_route_locked(
                from_system_id, to_system_id, travel_time_modifier, description, status,
            )

    def list_stellar_routes(self, known_only: bool = False) -> list[StellarRoute]:
        with self._lock:
            return [
                r.model_copy(deep=True) for r in self._stellar_routes.values()
                if not known_only or r.status == RouteStatus.Known
            ]

    def get_stellar_route(self, route_id: str) -> StellarRoute:
        with self._lock:
            route = self._stellar_routes.get(route_id)
            if route is None:
                raise KeyError(f"Route not found: {route_id}")
            return route.model_copy(deep=True)

    def reveal_stellar_route(self, route_id: str) -> StellarRoute:
        with self._lock:
            route = self._stellar_routes.get(route_id)
            if route is None:
                raise KeyError(f"Route not found: {route_id}")
            route.status = RouteStatus.Known
            self._repo.save_stellar_route(route)
            return route.model_copy(deep=True)

    def delete_stellar_route(self, route_id: str) -> None:
        with self._lock:
            if route_id not in self._stellar_routes:
                raise KeyError(f"Route not found: {route_id}")
            del self._stellar_routes[route_id]
            self._repo.delete_stellar_route(route_id)

    # ── Space travel ───────────────────────────────────────────────────────────

    def initiate_travel(
        self,
        from_system_id: str,
        to_system_id: str,
        route_id: str,
        faction_id: str = "",
    ) -> SpaceTravel:
        with self._lock:
            route = self._stellar_routes.get(route_id)
            if route is None:
                raise KeyError(f"Route not found: {route_id}")
            if route.status != RouteStatus.Known:
                raise ValueError(f"Route {route_id} is not known — must be revealed first")
            pair = {route.fromSystemId, route.toSystemId}
            if from_system_id not in pair or to_system_id not in pair:
                raise ValueError("Route does not connect the requested systems")
            if faction_id:
                source_system = self._solar_systems.get(from_system_id)
                source_body_ids: set[str] = set(source_system.bodyIds) if source_system else set()
                corp = self._corporations.get(faction_id)
                has_spaceport = corp is not None and any(
                    b.buildingType == "Spaceport" and b.bodyId in source_body_ids
                    for b in (corp.buildings or [])
                )
                if not has_spaceport:
                    raise ValueError("A Spaceport is required in the source system")
            ticks_needed = max(1, round(route.distanceLy * TICKS_PER_LIGHT_YEAR * route.travelTimeModifier))
            travel = SpaceTravel(
                travelId=str(uuid4()),
                factionId=faction_id,
                fromSystemId=from_system_id,
                toSystemId=to_system_id,
                routeId=route_id,
                distanceLy=route.distanceLy,
                departedAtTick=self._tick_count,
                arrivalTick=self._tick_count + ticks_needed,
                status=TravelStatus.InTransit,
            )
            self._space_travels[travel.travelId] = travel
            self._repo.save_space_travel(travel)
            return travel.model_copy(deep=True)

    def get_travel(self, travel_id: str) -> SpaceTravel:
        with self._lock:
            travel = self._space_travels.get(travel_id)
            if travel is None:
                raise KeyError(f"Travel not found: {travel_id}")
            return travel.model_copy(deep=True)

    def list_active_travels(self) -> list[SpaceTravel]:
        with self._lock:
            return [t.model_copy(deep=True) for t in self._space_travels.values()
                    if t.status == TravelStatus.InTransit]

    def cancel_travel(self, travel_id: str) -> SpaceTravel:
        with self._lock:
            travel = self._space_travels.get(travel_id)
            if travel is None:
                raise KeyError(f"Travel not found: {travel_id}")
            if travel.status != TravelStatus.InTransit:
                raise ValueError(f"Travel {travel_id} is not in-transit (status={travel.status.name})")
            travel.status = TravelStatus.Cancelled
            self._repo.save_space_travel(travel)
            return travel.model_copy(deep=True)

    def galaxy_overview(self) -> dict:
        with self._lock:
            return {
                "systemCount": len(self._solar_systems),
                "knownRouteCount": sum(
                    1 for r in self._stellar_routes.values() if r.status == RouteStatus.Known
                ),
                "hiddenRouteCount": sum(
                    1 for r in self._stellar_routes.values() if r.status == RouteStatus.Hidden
                ),
                "activeTravelCount": sum(
                    1 for t in self._space_travels.values() if t.status == TravelStatus.InTransit
                ),
            }
