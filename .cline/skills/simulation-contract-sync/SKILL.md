---
name: simulation-contract-sync
description: Use when adding or modifying a shared Python/C# data contract: creating a new Pydantic model in models.py that needs a C# mirror struct in SimulationContracts.cs, or keeping both sides in sync after a field change. Trigger words: Pydantic model, C# contract, SimulationContracts, mirror struct, sync contract, add model, BuildingType, MarketState, ContractData, EventData, ReputationState, SIMULATION_CONTRACTS.md, models.py.
---

# Simulation Contract Sync — Python ↔ C#

## When to Use

- Ajout d'un nouveau `BaseModel` ou `IntEnum` dans `SimulationCore/terraformation_sim/models.py`
- Ajout de champs sur un modèle existant utilisé côté serveur ET côté client
- Vérifier que `SimulationContracts.cs` correspond à l'état actuel de `models.py`
- Après tout changement qui modifie un type partagé entre DedicatedServer et Unity

## Fichiers impliqués

| Fichier | Rôle |
|---------|------|
| `SimulationCore/terraformation_sim/models.py` | Source de vérité — modèles Pydantic |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | Miroirs C# |
| `Documentation/SIMULATION_CONTRACTS.md` | Table documentant les deux côtés |

## Procédure

### Étape 1 — Lire le modèle Python

```python
# Lire la classe dans models.py via read_file ou Unity_Grep / grep côté Python
```

Noter :
- Noms de champs (camelCase dans Pydantic pour compat JSON)
- Types et valeurs par défaut
- Bases Enum (`IntEnum` → doit être `int` en C#)
- Références à d'autres modèles imbriqués

### Étape 2 — Vérifier les collisions de noms dans SimulationContracts.cs

```
Unity_ManageScript(action=read, name=SimulationContracts)
```

**Règle de collision** : si le nom existe déjà dans un namespace Unity global, **préfixer le miroir C# avec `Simulation`** ou un préfixe métier :
- `BuildingType` → `CorpBuildingType`
- `AtmosphericComposition` → `SimulationAtmosphericComposition`
- La désérialisation JSON dépend des **noms de champs** seulement, pas du nom de struct — le préfixage est safe.

### Étape 3 — Mapping des types

| Python | C# |
|--------|-----|
| `str` | `string` |
| `int` | `int` |
| `float` | `float` |
| `bool` | `bool` |
| `str \| None` | `string` (null JSON → null ou "") |
| `float \| None` | `float` (défaut `0f`) |
| `int \| None` | `int` (défaut `0`) |
| `list[T]` | `T[]` |
| `dict[str, T]` | éviter dans les contracts — utiliser une struct list |
| `BaseModel` | `[Serializable] public struct XxxState` |
| `IntEnum` | `public enum XxxType : int` avec valeurs entières identiques |
| `Field(default_factory=list)` | `T[] field = new T[0]` |

### Étape 4 — Écrire la struct C#

Template `BaseModel` :
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

Template `IntEnum` :
```csharp
public enum XxxType : int
{
    None = 0,
    ValueA = 1,
    ValueB = 2,
}
```

Règles :
- Les noms de champs **doivent correspondre exactement** (sérialisation JSON basée sur les noms)
- `[Serializable]` sur chaque struct
- Pas de constructeurs, propriétés, ni méthodes — plain data structs uniquement
- Placer les enums avant les structs qui y font référence

### Étape 5 — Valider (OBLIGATOIRE avant de cocher la phase)

```
Unity_ValidateScript('Assets/Scripts/Simulation/Contracts/SimulationContracts')
Unity_ValidateScript('Assets/Scripts/UI/GameHUD')           # si modifié
```

En cas d'erreur C# :
- Ajouter `using System;` si `[Serializable]` n'est pas reconnu
- Remplacer `List<T>` par `T[]`
- Remplacer `float?` par `float` (nullable value types non safe pour le sérialiseur Unity JSON)

### Étape 6 — Mettre à jour SIMULATION_CONTRACTS.md

Ajouter une ligne :
```
| ModelName | field: Type | StructName | field: type |
```

## Erreurs fréquentes

- **`using System;` manquant** — `[Serializable]` l'exige
- **`List<T>` au lieu de `T[]`** — utiliser des arrays
- **Types nullable `float?`** — non safe, utiliser `float` avec défaut
- **`IntEnum` avec membre `None_`** — C# ne supporte pas `None_` → renommer en `None`
- **Oublier `bootstrap_sol()` cleanup** — si le nouveau modèle a un registre runtime dans `runtime.py`, ajouter `self._xxx = {}` dans le bloc wipe de `bootstrap_sol()`
