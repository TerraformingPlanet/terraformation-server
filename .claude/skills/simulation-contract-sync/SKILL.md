---
name: simulation-contract-sync
description: 'Use when adding or modifying a shared Python/C# data contract: creating a new Pydantic model in models.py that needs a C# mirror struct in SimulationContracts.cs, or keeping both sides in sync after a field change. Trigger words: Pydantic model, C# contract, SimulationContracts, mirror struct, sync contract, add model, BuildingType, MarketState, ContractData, EventData, ReputationState, SIMULATION_CONTRACTS.md.'
argument-hint: 'Describe the model to sync: e.g. "add MarketState Pydantic model and C# mirror", "sync BuildingData after adding a new field"'
---

# Simulation Contract Sync — Python ↔ C#

## When to Use

- Adding a new `BaseModel` or `IntEnum` in `SimulationCore/terraformation_sim/models.py`
- Adding fields to an existing model that is used server-side AND client-side
- Verifying that `SimulationContracts.cs` matches the current state of `models.py`
- After any change that modifies a type shared between DedicatedServer and Unity

## Files Involved

| File | Role |
|------|------|
| `SimulationCore/terraformation_sim/models.py` | Source of truth — Pydantic models |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | C# mirror structs |
| `Documentation/SIMULATION_CONTRACTS.md` | Table documenting both sides |

## Procedure

### Step 1 — Read the Python model

Read the full class definition from `models.py`. Note:
- Field names (already camelCase in Pydantic for JSON compat)
- Field types and defaults
- Enum bases (`IntEnum` → must be `int` in C#)
- Nested model references

### Step 2 — Check for name collisions in SimulationContracts.cs

Read `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` and search for existing types with the same or similar names.

**Collision rule**: if the name already exists in any Unity global namespace (e.g., `BuildingType` from Unity's own types, `AtmosphericComposition` from `CelestialBodyData.cs`), **prefix the C# mirror with `Simulation`**:
- `BuildingType` → `CorpBuildingType` (or `SimulationBuildingType`)
- `AtmosphericComposition` → `SimulationAtmosphericComposition`
- JSON deserialization depends on **field names only**, not the struct name — prefixing is safe.

### Step 3 — Apply the type mapping

| Python type | C# equivalent |
|-------------|--------------|
| `str` | `string` |
| `int` | `int` |
| `float` | `float` |
| `bool` | `bool` |
| `str \| None` (nullable) | `string` (JSON null deserializes as `null` or `""`) |
| `float \| None` (nullable) | `float` (default `0f`) |
| `int \| None` (nullable) | `int` (default `0`) |
| `list[T]` | `T[]` |
| `dict[str, T]` | serialized as JSON object — avoid in contracts; use a struct list instead |
| `BaseModel` subclass | `[Serializable] public struct StructName` |
| `IntEnum` subclass | `public enum EnumName : int` with identical integer values |
| `Field(default_factory=list)` | `T[] fieldName = new T[0]` or `Array.Empty<T>()` |
| `Field(default_factory=SubModel)` | `SubModelStruct fieldName = default` |

### Step 4 — Write the C# struct

Template for a `BaseModel`:
```csharp
[Serializable]
public struct XxxState
{
    public string fieldA;
    public int fieldB;
    public float fieldC;
    public bool fieldD;
    public SubTypeStruct fieldE;
    public SubTypeStruct[] fieldF;
}
```

Template for an `IntEnum`:
```csharp
public enum XxxType : int
{
    ValueA = 0,
    ValueB = 1,
    ValueC = 2,
}
```

Rules:
- Field names must match exactly (JSON serialization is name-based)
- `[Serializable]` on every struct
- No constructors, properties, or methods — plain data structs only
- Place enums before the structs that reference them
- Preserve declaration order to make diffs readable

### Step 5 — Validate

**OBLIGATOIRE avant de marquer la phase [x] dans ROADMAP.**

1. Appliquer la struct/enum dans `SimulationContracts.cs`
2. Appeler `Unity_ValidateScript` sur les fichiers C# modifiés — doit retourner 0 erreur :
   ```
   Unity_ValidateScript('Assets/Scripts/Simulation/Contracts/SimulationContracts.cs')
   Unity_ValidateScript('Assets/Scripts/UI/GameHUD.cs')          # si modifié
   Unity_ValidateScript('Assets/Scripts/UI/GameHUDBuildingIcons.cs')  # si modifié
   ```
3. Lancer la validation globale Python + rappel Unity :
   ```powershell
   cd e:\terraformation
   .\Tools\Invoke-PhaseValidation.ps1
   ```
4. Si erreurs C# : corriger les types ou `using` manquants, re-valider
5. Marquer `[x]` dans ROADMAP **seulement** après 0 erreur Python ET 0 erreur C#

### Step 6 — Update SIMULATION_CONTRACTS.md

Add a row to the shared contracts table:

```
| ModelName | field: Type | StructName | field: type |
```

Include both the Python side and the C# side in the same row.

## Common Mistakes

- **Missing `using System;`** in `SimulationContracts.cs` — `[Serializable]` requires it
- **`List<T>` instead of `T[]`** — use arrays; Unity JSON serializer handles arrays better
- **Nullable value types** — C# `float?` is not JSON-safe in Unity; use `float` with a default instead
- **IntEnum with `None_` member** — C# `None_ = 0` is invalid; rename to `None = 0` (or keep underscore in Python only, map to `None` in C#)
- **Forgetting to add to `bootstrap_sol()` cleanup** — if the new model type has a runtime registry in `runtime.py`, add `self._xxx = {}` to the wipe block in `bootstrap_sol()`
