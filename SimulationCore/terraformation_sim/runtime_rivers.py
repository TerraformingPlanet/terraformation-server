"""River propagation tick mixin — Phase p-hydro-2 / p-hydro-3.

Integrates source activation, river front propagation, and lake filling
into the simulation tick loop via _process_river_tick_locked().

State accessed via self:
    self._lock, self._active_body_id, self._bodies,
    self._river_arrival_ticks, self._tick_count
"""
from __future__ import annotations

from .logic.rivers import activate_sources, fill_lake_step, propagate_river_step
from .models import GoldbergTileState


class RiversMixin:
    """Tick-by-tick river propagation for spherical body tiles."""

    def _process_river_tick_locked(self) -> None:
        """Advance river propagation for the active spherical body. Assumes lock held.

        Steps each tick:
        1. activate_sources  — turns on hasRiver for springs where temperature > 0 °C
        2. propagate_river_step — advance river fronts one tile when delay elapsed
        3. fill_lake_step    — accumulate lake volume in sink tiles; overflow if full
        """
        if not self._active_body_id:
            return
        body = self._bodies.get(self._active_body_id)
        if body is None or not getattr(body, "tiles", None):
            return

        tiles: list[GoldbergTileState] = [
            GoldbergTileState.model_validate(t) if isinstance(t, dict) else t
            for t in body.tiles
        ]

        arrival_ticks: dict[str, int] = self._river_arrival_ticks.setdefault(
            self._active_body_id, {}
        )

        newly_activated = activate_sources(tiles, self._tick_count, arrival_ticks)
        newly_wet = propagate_river_step(tiles, self._tick_count, arrival_ticks)
        overflow = fill_lake_step(tiles, self._tick_count, arrival_ticks)

        if newly_activated or newly_wet or overflow:
            body.tiles = tiles
