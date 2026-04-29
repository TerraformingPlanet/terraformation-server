---
name: gameplay-tick-feature
description: 'Use when implementing a new gameplay mechanic that affects the simulation tick: buildings, market, contracts, events, reputation, corporations, resources. Trigger words: new mechanic, tick loop, gameplay feature, production, market, contract, event, corporation, resource, registry, bootstrap_sol, runtime.py, logic.py, 5 layers, Phase 7, Phase 8, Phase 9.'
argument-hint: 'Describe the mechanic: e.g. "add MarketState and price tick logic", "implement EventData and EventManager", "add reputation system"'
---

# Gameplay Tick Feature — 5-Layer Implementation

## When to Use

- Implementing any new gameplay mechanic that involves persistent state + server-side logic + client display
- Phases 7.3 (Market), 7.4 (Contracts), 7.5 (Reputation), 8 (Events), 9 (Trade routes)
- Any time the tick loop (`_process_*` methods in `runtime.py`) needs a new processing step

## The 5 Layers — Always in This Order

```
Layer 1 → models.py         (Pydantic data contracts)
Layer 2 → logic/            (pure calculation functions)
Layer 3 → runtime.py        (registry + tick loop integration)
Layer 4 → server.py         (FastAPI REST endpoints)
Layer 5 → SimulationContracts.cs  (C# mirror — use simulation-contract-sync skill)
```

Do NOT skip layers. Do NOT jump to Layer 4 before Layer 3 is done.

---

## Layer 1 — `SimulationCore/terraformation_sim/models.py`

**Rules:**
- Every entity is a `BaseModel` (data) or `IntEnum` (categorical)
- All `IntEnum` classes inherit from `IntEnum` — not `str`, not `Enum`
- All optional fields have a default value — never `Optional[T]` without a default:
  ```python
  # CORRECT
  name: str = ""
  value: float | None = None
  items: list[Item] = Field(default_factory=list)
  
  # WRONG
  name: Optional[str]          # no default
  items: list[Item]            # no default_factory
  ```
- Nested models use `Field(default_factory=NestedModel)` for single instances
- Field names must be camelCase (JSON compatibility with C# Unity deserializer)

**Reference**: `BuildingType`, `ResourceType`, `BuildingData`, `CorporationData` in `models.py` — Phase 7.2 implementation.

---

## Layer 2 — `SimulationCore/terraformation_sim/logic/` or `logic.py`

**Rules:**
- All tick-time calculation functions live here — **never** put calculation logic in `runtime.py`
- Functions are **pure**: take Pydantic model instances as input, return Pydantic model instances as output
- No side effects, no `self`, no registry access
- Name pattern: `compute_xxx(state: XxxState) -> XxxState` or `process_xxx_tick(corps: list[CorporationData]) -> list[CorporationData]`

**Reference**: `compute_atmospheric_state(cells)`, `_process_building_production()` in `logic/simulation.py` — Phase 7.2 / Sprint D.

---

## Layer 3 — `SimulationCore/terraformation_sim/runtime.py`

### Thread safety — mandatory

Every read/write of runtime state goes inside a lock:
```python
def my_public_method(self, arg: str) -> XxxState:
    with self._lock:
        return self._my_internal_locked(arg)

def _my_internal_locked(self, arg: str) -> XxxState:
    # _lock is already held here
    ...
```

- Methods suffixed `_locked()` **assume** the lock is already held — never call them from outside a `with self._lock:` block
- The lock is an `RLock` (reentrant) — safe to call other public methods that also acquire it

### Registry pattern

New entity type = new dict registry:
```python
# In __init__:
self._market_orders: dict[str, MarketOrder] = {}

# In bootstrap_sol() — MANDATORY:
self._market_orders = {}   # wipe on world reset
```

**`bootstrap_sol()` wipe block** (add every new registry here):
```python
self._region_mutations = {}     # Sprint C
self._corporations = {}          # Phase 7.1
self._tile_ownership = {}        # Phase 7.1
self._buildings = {}             # Phase 7.2
self._market_orders = {}         # Phase 7.3 — ADD HERE
```

### Tick loop integration

The tick loop calls processing functions in order. Add new processors here:
```python
def _tick_locked(self) -> None:
    # existing:
    self._process_building_production()
    # add new:
    self._process_market_tick()
    self._process_event_tick()
    self._tick_count += 1
```

Each processor method:
- Is `_locked()` — lock already held
- Calls `logic/` functions for calculation
- Writes results back to registries
- Emits a `SimulationEvent` if significant (use `SimulationEventType` enum)

### Pattern lock-free (FSM / LLM corpo — Phase 11.2+)

Quand un processeur doit appeler du code potentiellement lent (FSM complex, appel LLM), utiliser le pattern snapshot :
```python
def _process_bot_tick_locked(self) -> None:
    """Spawn a background FSM thread per AI corporation. Lock must be held."""
    for corp in self._corporations.values():
        if corp.isAI:
            threading.Thread(
                target=self._run_bot_fsm_bg,
                args=(corp.id,),
                daemon=True,
            ).start()

def _run_bot_fsm_bg(self, corp_id: str) -> None:
    with self._lock:
        corp = self._corporations.get(corp_id)
        snapshot = self._build_corp_snapshot_locked(corp)  # fast read-only
    # ---- hors lock : FSM ou LLM tourne librement ----
    new_state = compute_next_fsm_state(corp, snapshot)
    actions   = compute_fsm_actions(corp, snapshot, new_state)
    # ---- re-acquire lock pour écrire ----
    with self._lock:
        corp2 = self._corporations.get(corp_id)
        if corp2:
            corp2.fsmState = new_state
            for action in actions:
                self._apply_agent_action_locked(action)
```

> Règle : le snapshot est construit sous lock (lecture rapide), le traitement tourne hors lock, les écritures se font sous lock. Même pattern pour les appels LLM (Phase 11.2 M2).

---

## Layer 4 — `DedicatedServer/app/server.py`

See `dedicated-server-endpoint` skill for the full endpoint pattern.

Quick reference:
```python
@app.get("/game/market", response_model=MarketState)
def get_market() -> MarketState:
    return runtime.get_market_state()

@app.post("/game/market/order", response_model=MarketState)
def place_order(resource: ResourceType, quantity: int, price: float) -> MarketState:
    return runtime.place_market_order(resource=resource, quantity=quantity, price=price)
```

Error codes:
- `404` — resource/entity not found
- `409` — conflict (already exists, already claimed)
- `422` — FastAPI validation error (automatic for wrong parameter types)

---

## Layer 5 — SimulationContracts.cs

Delegate to the `simulation-contract-sync` skill. Summary:
- Map every new Pydantic `BaseModel` → `[Serializable] public struct`
- Map every new `IntEnum` → `public enum : int`
- Validate with `Unity_ValidateScript`
- Update `SIMULATION_CONTRACTS.md`

---

## Validation Checklist

**OBLIGATOIRE avant de marquer la phase [x] dans ROADMAP.**
Lancer dans cet ordre exact :

```powershell
# 1. Python tests + syntaxe models.py (auto-découvre tous les test_*.py)
cd e:\terraformation
.\Tools\Invoke-PhaseValidation.ps1
```

Ensuite, via l'agent MCP, valider les fichiers C# touchés ce cycle :

```
Unity_ValidateScript('Assets/Scripts/Simulation/Contracts/SimulationContracts.cs')
Unity_ValidateScript('Assets/Scripts/UI/GameHUD.cs')              # si modifié
Unity_ValidateScript('Assets/Scripts/UI/GameHUDBuildingIcons.cs') # si modifié
```

Critères de sortie :
- [ ] `Invoke-PhaseValidation.ps1` → exit 0 (tous les tests passent)
- [ ] `Unity_ValidateScript(SimulationContracts.cs)` → 0 erreurs
- [ ] Tout C# modifié → 0 erreurs
- [ ] `get_console_errors(minimum_severity=Warning)` → aucun nouveau warning Unity
- [ ] Nouveau registry ajouté au bloc wipe de `bootstrap_sol()`
- [ ] Fonctions `logic/` sans effets de bord
- [ ] Toutes les méthodes `_locked()` jamais appelées hors d'un `with self._lock:`

## Architecture Rules (Non-Negotiable)

- **Unity is a display client only** — no gameplay logic in C# scripts
- **Server is authoritative** — all state validation in `SimulationCore` or `DedicatedServer`
- **Mirror Networking not available until Phase 10** — do not design around it
- **No Firebase** — persistence is PostgreSQL + SQLAlchemy Core (`persistence.py`)
