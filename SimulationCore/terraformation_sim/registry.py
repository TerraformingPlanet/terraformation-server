"""
Game data registries — resources and buildings loaded from JSON.

Loaded at server startup, before bootstrap_sol().
Provides data-driven access to resource/building definitions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import BaseModel


# ── Data models ───────────────────────────────────────────────────────────────

class ResourceDef(BaseModel):
    """Definition of a resource loaded from JSON."""
    id: str
    display_name: str
    category: str
    rarity: int
    tradable: bool
    storable: bool
    base_price: float
    tile_deposit: bool
    depletable: bool
    demand_per_tick: Dict[str, float]  # keys: "Poor", "Middle", "Rich"


class BuildingDef(BaseModel):
    """Definition of a building loaded from JSON."""
    id: str
    display_name: str
    type: str
    workers_required: Dict[str, int]  # keys: "Poor", "Middle", "Rich"
    deposit_required: Optional[str]   # resource id or None
    terrain_required: Optional[str] = None   # terrain type name or None (e.g. "Foret")
    primary_species: Optional[str] = None    # species targeted by ecology_impact (e.g. "forest")
    inputs_per_tick: Dict[str, float]  # resource_id -> delta (negative = consumption)
    outputs_per_tick: Dict[str, float] # resource_id -> delta (positive = production)
    effects_per_tick: Dict[str, float] # "ecology_impact", "worker_risk_pct", "deposit_depletion"


# ── Registries ────────────────────────────────────────────────────────────────

class ResourceRegistry:
    """Registry of all game resources, loaded from JSON files."""

    def __init__(self) -> None:
        self._permanent: Dict[str, ResourceDef] = {}
        self._pending: Dict[str, ResourceDef] = {}

    def load(self, permanent_path: Path, pending_path: Path) -> None:
        """Load permanent and pending resources from JSON files."""
        # Load permanent resources
        if permanent_path.exists():
            with open(permanent_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    res = ResourceDef(**item)
                    self._permanent[res.id] = res

        # Load pending resources
        if pending_path.exists():
            with open(pending_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    res = ResourceDef(**item)
                    self._pending[res.id] = res

    def get(self, resource_id: str) -> Optional[ResourceDef]:
        """Get a resource definition by ID (permanent first, then pending)."""
        return self._permanent.get(resource_id) or self._pending.get(resource_id)

    def all(self) -> List[ResourceDef]:
        """Get all permanent resources."""
        return list(self._permanent.values())

    def tradable(self) -> List[str]:
        """Get IDs of all tradable resources."""
        return [r.id for r in self._permanent.values() if r.tradable]

    def demand_for_class(self, social_class: str, resource_id: str) -> float:
        """Get demand per tick for a social class and resource."""
        res = self.get(resource_id)
        if res:
            return res.demand_per_tick.get(social_class, 0.0)
        return 0.0

    def add_pending(self, resource_def: ResourceDef) -> None:
        """Add a resource to the pending list (for LLM proposals)."""
        self._pending[resource_def.id] = resource_def

    def approve(self, resource_id: str, permanent_path: Path) -> bool:
        """Move a pending resource to permanent and save to JSON."""
        if resource_id not in self._pending:
            return False

        # Move to permanent
        res = self._pending.pop(resource_id)
        self._permanent[res.id] = res

        # Save permanent to JSON
        data = [r.model_dump() for r in self._permanent.values()]
        with open(permanent_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True

    def reject(self, resource_id: str) -> bool:
        """Remove a resource from pending."""
        return self._pending.pop(resource_id, None) is not None

    def pending(self) -> List[ResourceDef]:
        """Get all pending resources."""
        return list(self._pending.values())


class BuildingRegistry:
    """Registry of all game buildings, loaded from JSON files."""

    def __init__(self) -> None:
        self._permanent: Dict[str, BuildingDef] = {}
        self._pending: Dict[str, BuildingDef] = {}

    def load(self, permanent_path: Path, pending_path: Path) -> None:
        """Load permanent and pending buildings from JSON files."""
        # Load permanent buildings
        if permanent_path.exists():
            with open(permanent_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    bld = BuildingDef(**item)
                    self._permanent[bld.id] = bld

        # Load pending buildings
        if pending_path.exists():
            with open(pending_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    bld = BuildingDef(**item)
                    self._pending[bld.id] = bld

    def get(self, building_id: str) -> Optional[BuildingDef]:
        """Get a building definition by ID (permanent first, then pending)."""
        return self._permanent.get(building_id) or self._pending.get(building_id)

    def all(self) -> List[BuildingDef]:
        """Get all permanent buildings."""
        return list(self._permanent.values())

    def get_outputs(self, building_id: str) -> Dict[str, float]:
        """Get output deltas per tick for a building."""
        bld = self.get(building_id)
        return bld.outputs_per_tick if bld else {}

    def get_inputs(self, building_id: str) -> Dict[str, float]:
        """Get input deltas per tick for a building."""
        bld = self.get(building_id)
        return bld.inputs_per_tick if bld else {}

    def get_workers(self, building_id: str) -> Dict[str, int]:
        """Get worker requirements for a building."""
        bld = self.get(building_id)
        return bld.workers_required if bld else {}

    def get_effects(self, building_id: str) -> Dict[str, float]:
        """Get effects per tick for a building."""
        bld = self.get(building_id)
        return bld.effects_per_tick if bld else {}

    def add_pending(self, building_def: BuildingDef) -> None:
        """Add a building to the pending list (for LLM proposals)."""
        self._pending[building_def.id] = building_def

    def approve(self, building_id: str, permanent_path: Path) -> bool:
        """Move a pending building to permanent and save to JSON."""
        if building_id not in self._pending:
            return False

        # Move to permanent
        bld = self._pending.pop(building_id)
        self._permanent[bld.id] = bld

        # Save permanent to JSON
        data = [b.model_dump() for b in self._permanent.values()]
        with open(permanent_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True

    def reject(self, building_id: str) -> bool:
        """Remove a building from pending."""
        return self._pending.pop(building_id, None) is not None

    def pending(self) -> List[BuildingDef]:
        """Get all pending buildings."""
        return list(self._pending.values())


# ── Global instances — auto-load from data/ at import time ───────────────────

_DATA_DIR = Path(__file__).parent / "data"

RESOURCE_REGISTRY = ResourceRegistry()
RESOURCE_REGISTRY.load(
    _DATA_DIR / "resources.json",
    _DATA_DIR / "pending_resources.json",
)

BUILDING_REGISTRY = BuildingRegistry()
BUILDING_REGISTRY.load(
    _DATA_DIR / "buildings.json",
    _DATA_DIR / "pending_buildings.json",
)