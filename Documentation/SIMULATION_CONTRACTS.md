# Contrats de Simulation — Python ↔ C#

Ce document définit la convention de synchronisation entre les modèles Pydantic Python et les structs C# Unity.

**Fichier source Python** : `SimulationCore/terraformation_sim/models.py`
**Fichier miroir C#** : `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs`

---

## Règle de synchronisation

> **Python est autoritaire.** Le `DedicatedServer` et `SimulationCore` sont la source de vérité. Le C# est un miroir de désérialisation JSON côté client Unity.

Toute modification d'un type partagé doit être appliquée **dans les deux fichiers** simultanément :
1. Modifier `models.py` côté Python
2. Modifier `SimulationContracts.cs` côté C#
3. Vérifier que les noms de champs JSON correspondent exactement (Pydantic sérialise en camelCase — vérifier la config)

**Risque actuel** : la synchronisation est manuelle. Il n'existe pas de test de contrat automatisé.

---

## Types partagés

### Enums

| Python (`models.py`) | C# (`SimulationContracts.cs`) | Notes |
|---|---|---|
| `TerrainType` | `TerrainType` | Défini dans un fichier C# séparé (HexCell) |
| `TerrainClass` | `TerrainClass` | Idem |
| `WaterClassification` | `WaterClassification` | Idem |
| `WorldLayer` | `WorldLayer` | Idem |
| `TerraformAction` | `TerraformAction` | Idem |
| `DebugCoherenceOverride` | `DebugCoherenceOverride` | Python: `None_=0` → C#: `None=0` (mot réservé C#) |
| `SimulationCommandType` | `SimulationCommandType` | Python: `None_=0` → C#: `None=0` |
| `SimulationEventType` | `SimulationEventType` | Python: `None_=0` → C#: `None=0` |

### Structs / classes

| Python (`models.py`) | C# (`SimulationContracts.cs`) | Notes |
|---|---|---|
| `SimulationVector2State` | `struct SimulationVector2State` | `x`, `y` — C# ajoute `ToVector2()` |
| `SimulationCoordinates` | `struct SimulationCoordinates` | `latitude`, `longitude` |
| `SimulationCellAddress` | `struct SimulationCellAddress` | `q`, `r` |
| `SimulationSoilState` | `struct SimulationSoilState` | 6 champs identiques |
| `HexStateModifier` | `struct HexStateModifier` | 6 deltas |
| `TerraformActionDefinition` | `struct SimulationActionDefinition` | **Noms divergent** : Python `TerraformActionDefinition`, C# `SimulationActionDefinition` |
| `SimulationActionCatalog` | `struct SimulationActionCatalog` | `actions[]` |
| `SimulationCellState` | `struct SimulationCellState` | Voir détail ci-dessous |
| `SimulationWeatherState` | `struct SimulationWeatherState` | 5 champs identiques |
| `SimulationCoherenceState` | `struct SimulationCoherenceState` | 8 champs identiques |
| `AtmosphericState` | `struct AtmosphericState` | 6 champs identiques — voir détail ci-dessous |
| `ProjectionState` | `struct ProjectionState` | 5 champs identiques |
| `RegionState` | `struct RegionState` | 12 champs + `cells[]` (inclut `atmosphericState`) |
| `WorldState` | `struct WorldState` | 11 champs identiques |
| `ClientSnapshot` | `struct ClientSnapshot` | 10 champs identiques |
| `SimulationCommand` | `struct SimulationCommand` | 8 champs identiques |
| `SimulationEvent` | `struct SimulationEvent` | 7 champs identiques |

---

## Détail : `AtmosphericState`

Dérivé en fin de `_build_region_state()` depuis l'état des cellules par `compute_atmospheric_state(cells)` — jamais saisi manuellement.

| Champ Python | Champ C# | Type | Notes |
|---|---|---|---|
| `co2Ratio` | `co2Ratio` | `float` | Fraction CO₂ [0..1] — Terre ≈ 0.0004 |
| `o2Ratio` | `o2Ratio` | `float` | Fraction O₂ [0..1] — Terre ≈ 0.21 |
| `atmosphericPressure` | `atmosphericPressure` | `float` | kPa — Mars initial ≈ 0.6, Terre ≈ 101.3 |
| `averageTemperature` | `averageTemperature` | `float` | °C avec correction effet de serre |
| `toxinRatio` | `toxinRatio` | `float` | Moyenne toxines cellulaires [0..1] |
| `habitabilityScore` | `habitabilityScore` | `float` | Score pondéré multi-param [0..1] |

**Utilisation** :
- `TerraformHUD.SetAuthoritativeRegionState()` utilise `habitabilityScore` comme progrès principal si `> 0`
- `TerraformHUD.RefreshHexInfo()` affiche O₂%, CO₂%, pression, score dans le panel région autoritatif
- MCP tool `get_atmospheric_state(lat, lon)` retourne directement ce dict

---

## Détail : `SimulationCellState`

Type le plus complexe et le plus susceptible de diverger.

| Champ Python | Champ C# | Type | Notes |
|---|---|---|---|
| `address` | `address` | `SimulationCellAddress` | ✅ |
| `terrainName` | `terrainName` | `string` | ✅ |
| `terrainType` | `terrainType` | `TerrainType` | ✅ |
| `layer` | `layer` | `WorldLayer` | ✅ |
| `altitude` | `altitude` | `float` | ✅ |
| `temperature` | `temperature` | `float` | ✅ |
| `waterRatio` | `waterRatio` | `float` | ✅ |
| `toxinLevel` | `toxinLevel` | `float` | ✅ |
| `windVector` | `windVector` | `SimulationVector2State` | ✅ |
| `windSpeed` | `windSpeed` | `float` | ✅ |
| `rainShadow` | `rainShadow` | `bool` | ✅ |
| `hasRiver` | `hasRiver` | `bool` | ✅ |
| `flowAccumulation` | `flowAccumulation` | `int` | ✅ |
| `terrainClass` | `terrainClass` | `TerrainClass` | ✅ |
| `waterClassification` | `waterClassification` | `WaterClassification` | ✅ |
| `hasDownstream` | `hasDownstream` | `bool` | ✅ |
| `downstream` | `downstream` | `SimulationCellAddress` | ✅ |
| `hasOverflowOutlet` | `hasOverflowOutlet` | `bool` | ✅ |
| `overflowOutlet` | `overflowOutlet` | `SimulationCellAddress` | ✅ |
| `soil` | `soil` | `SimulationSoilState` | ✅ |
| *(absent)* | `latOnSphere` | `float` | ⚠️ C# uniquement — overlay globe Unity, jamais sérialisé par le serveur |
| *(absent)* | `lonOnSphere` | `float` | ⚠️ C# uniquement — idem |

---

## Divergences connues

| Divergence | Impact | Action recommandée |
|---|---|---|
| `TerraformActionDefinition` (Python) ≠ `SimulationActionDefinition` (C#) | Faible — noms différents mais structure identique | Harmoniser les noms lors du prochain refactor |
| `latOnSphere` / `lonOnSphere` présents uniquement en C# | Aucun — champs Unity-only | Documenter comme "champs overlay client", jamais exposés côté serveur |
| Synchronisation manuelle | Élevé — risque de dérive silencieuse | Ajouter un test de contrat Python (`pydantic` → JSON → désérialisation C# simulée) |

---

## Convention de nommage JSON

Pydantic par défaut sérialise les champs en leur nom Python (snake_case ou camelCase selon la config).

Dans ce projet, les modèles Pydantic utilisent **camelCase natif** (les champs sont déjà déclarés en camelCase : `terrainName`, `waterRatio`, etc.), donc la sérialisation JSON correspond directement aux noms C#.

**À ne pas faire** : utiliser `model_config = ConfigDict(alias_generator=to_camel)` dans `models.py` — cela casserait la correspondance actuelle.

---

## Checklist pour ajouter un champ partagé

1. Ajouter le champ dans `SimulationCore/terraformation_sim/models.py` (Pydantic)
2. Ajouter le champ dans `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` (C# struct)
3. Vérifier que le nom JSON correspond (tester `model.model_dump()` côté Python)
4. Si le champ est produit par `DedicatedServer`, mettre à jour `DedicatedServer/app/server.py`
5. Si le champ est consommé par Unity, mettre à jour `SimulationContractFactory.cs`
6. Mettre à jour ce document (tableau du type concerné)

---

## Fichiers concernés

| Fichier | Rôle |
|---|---|
| `SimulationCore/terraformation_sim/models.py` | Source de vérité Python |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | Miroir C# |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContractFactory.cs` | Constructeur Unity-side |
| `DedicatedServer/app/server.py` | Producteur des snapshots |
| `Mcp/server.py` | Consommateur MCP des snapshots |
