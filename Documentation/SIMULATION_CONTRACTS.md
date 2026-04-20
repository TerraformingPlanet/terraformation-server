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
| `AtmosphericGas` | `struct SimulationAtmosphericGas` | Préfixé côté C# pour éviter une collision avec les types Unity monde |
| `AtmosphericComposition` | `struct SimulationAtmosphericComposition` | Préfixé côté C# pour éviter une collision avec `World/CelestialBodyData.cs` |
| `GlobalWindPattern` | `struct SimulationGlobalWindPattern` | Préfixé côté C# pour éviter une collision potentielle avec les types monde |
| `BodyListEntry` | `struct SimulationBodyListEntry` | Préfixé côté C# pour éviter une collision future avec les types monde/UI |
| `ProjectionState` | `struct ProjectionState` | 5 champs identiques |
| `RegionState` | `struct RegionState` | 12 champs + `cells[]` (inclut `atmosphericState`) |
| `WorldState` | `struct WorldState` | 11 champs identiques |
| `ClientSnapshot` | `struct ClientSnapshot` | 10 champs identiques |
| `SimulationCommand` | `struct SimulationCommand` | 8 champs identiques |
| `SimulationEvent` | `struct SimulationEvent` | 7 champs identiques |
| `ClaimedTile` | `struct ClaimedTile` | `bodyId`, `tileId` — Phase 7.1 |
| `CorporationData` | `struct CorporationData` | `id`, `name`, `credits`, `claimedTiles[]`, `score`, `isAI` — Phase 7.1 |
| `SocialClass` | `enum SocialClass : int` | `Poor=0`, `Middle=1`, `Rich=2` — Phase 7.3 |
| `PopulationTier` | `struct PopulationTier` | `socialClass`, `count` — Phase 7.3 |
| `ResourceListing` | `struct ResourceListing` | `resourceType`, `price`, `supply`, `demand` — Phase 7.3 |
| `LocalMarketState` | `struct LocalMarketState` | `corpId`, `listings[]`, `taxRate`, `tickComputed` — Phase 7.3 |

---

## Phase 7.3 — Marché local

### SocialClass (IntEnum / enum : int)
| Python | C# | Value |
|--------|----|-------|
| Poor   | Poor   | 0 |
| Middle | Middle | 1 |
| Rich   | Rich   | 2 |

### ResourceType (IntEnum / CorpResourceType enum : int)
| Python | C# | Value | Description |
|--------|----|----|---|
| Minerals | Minerals | 0 | Minerais bruts |
| Food | Food | 1 | Nourriture |
| Energy | Energy | 2 | Énergie électrique |
| ResearchPoints | ResearchPoints | 3 | Points de recherche |
| Waste | Waste | 4 | Déchets industriels |
| Iron | Iron | 5 | Minerai de fer — Phase 9.5 |
| Oxygen | Oxygen | 6 | Oxygène atmosphérique — Phase 9.5 |
| Water | Water | 7 | Eau disponible — Phase 9.5 |
| Tech | Tech | 8 | Points technologiques — Phase 9.5 |

> Note : `CorpResourceType` préfixe évite collision avec `ResourceType` existant dans Unity.

### PopulationTier (BaseModel / struct)
| Champ | Type Python | Type C# |
|-------|-------------|---------|
| socialClass | SocialClass | SocialClass |
| count | int | int |

### ResourceListing (BaseModel / struct)
| Champ | Type Python | Type C# |
|-------|-------------|---------|
| resourceType | ResourceType | CorpResourceType |
| price | float | float |
| supply | float | float |
| demand | float | float |

> Note : `CorpResourceType` préfixe évite collision avec `ResourceType` existant dans Unity.

### LocalMarketState (BaseModel / struct)
| Champ | Type Python | Type C# |
|-------|-------------|---------|
| corpId | str | string |
| listings | list[ResourceListing] | ResourceListing[] |
| taxRate | float | float |
| tickComputed | int | int |

### GlobalMarketState (BaseModel / struct) — Phase 9.5
| Champ | Type Python | Type C# |
|-------|-------------|---------|
| systemId | str | string |
| listings | list[ResourceListing] | ResourceListing[] |
| tick | int | int |
| marketCount | int | int |

> Note : Aggregated market state for a system. Wrapper class `GlobalMarketStateWrapper` for JSON deserialization.

### ClaimedTile — champ ajouté
| Champ | Type Python | Type C# |
|-------|-------------|---------|
| population | list[PopulationTier] | PopulationTier[] |

---
## Phase 7.4 — Contracts (ContractStatus, ContractVisibility, ContractData)

### ContractStatus (IntEnum)
| Value | Name      |
|-------|-----------|
| 0     | Proposed  |
| 1     | Active    |
| 2     | Completed |
| 3     | Broken    |
| 4     | Expired   |

### ContractVisibility (IntEnum)
| Value | Name    |
|-------|---------|
| 0     | Public  |
| 1     | Private |

### ContractData
| Python field        | C# field            | Type   | Notes                                          |
|---------------------|---------------------|--------|------------------------------------------------|
| id                  | id                  | string | UUID                                           |
| status              | status              | int    | ContractStatus / CorpContractStatus            |
| visibility          | visibility          | int    | ContractVisibility / CorpContractVisibility    |
| proposerId          | proposerId          | string |                                                |
| targetId            | targetId            | string | Private only                                   |
| acceptorId          | acceptorId          | string | Set when Active                                |
| candidates          | candidates          | string[] | Public bidders list                          |
| resourceType        | resourceType        | int    | ResourceType / CorpResourceType                |
| resourceAmount      | resourceAmount      | float  | Total to deliver                               |
| deliveredAmount     | deliveredAmount     | float  | Auto-incremented each tick                     |
| rewardCredits       | rewardCredits       | float  | Paid proposer→acceptor on completion           |
| penaltyCredits      | penaltyCredits      | float  | Deducted from breacher (debt allowed)          |
| knowledgeBonus      | knowledgeBonus      | float  | Added to acceptor ResearchPoints on completion |
| durationTicks       | durationTicks       | int    | 0 = unlimited                                  |
| startTick           | startTick           | int    |                                                |
| expiresAtTick       | expiresAtTick       | int    | 0 = no expiry                                  |
| biddingWindowTicks  | biddingWindowTicks  | int    | Public only                                    |
| biddingCloseTick    | biddingCloseTick    | int    | Tick at which bidding window closes            |
| tickCreated         | tickCreated         | int    |                                                |

**C# types**: `CorpContractStatus`, `CorpContractVisibility`, `CorpContractData` in `SimulationContracts.cs`

---
## Phase 7.5 — États, Réputation, Nationalisation, Scoreboard

### StateType (IntEnum / enum : int)
| Python | C# (`CorpStateType`) | Value |
|--------|----------------------|-------|
| Capitalist | Capitalist | 0 |
| Nationalist | Nationalist | 1 |

### StateData (BaseModel / struct `SimStateData`)
| Python field | C# field | Type | Notes |
|---|---|---|---|
| id | id | string | UUID |
| name | name | string | |
| stateType | stateType | int | StateType / CorpStateType |
| tileIds | tileIds | string[] | Hexes contrôlés |
| bureaucracy | bureaucracy | float | Délai nationalisation [0..1] |
| corruptionRate | corruptionRate | float | Passif exploitable [0..1] |
| toleranceThreshold | toleranceThreshold | float | Seuil déclenchement nationalisation |

**C# type** : `SimStateData` in `SimulationContracts.cs`

### ReputationEventReason (IntEnum / enum : int)
| Python | C# (`CorpReputationEventReason`) | Value |
|--------|----------------------------------|-------|
| ContractCompleted | ContractCompleted | 0 |
| ContractBroken | ContractBroken | 1 |
| TileStolen | TileStolen | 2 |
| BribeOffered | BribeOffered | 3 |
| CorruptionDetected | CorruptionDetected | 4 |

### ReputationEvent (BaseModel / struct)
| Python field | C# field | Type | Notes |
|---|---|---|---|
| sourceId | sourceId | string | UUID corpo ou état émetteur |
| targetId | targetId | string | UUID corpo ou état destinataire |
| deltaGlobal | deltaGlobal | float | |
| deltaBilateral | deltaBilateral | float | |
| reason | reason | int | ReputationEventReason / CorpReputationEventReason |
| tick | tick | int | |

**C# type** : `ReputationEvent` in `SimulationContracts.cs`

### NationalizationProcess (BaseModel / struct)
| Python field | C# field | Type | Notes |
|---|---|---|---|
| id | id | string | UUID |
| stateId | stateId | string | |
| corpId | corpId | string | |
| tileId | tileId | string | H3 tileId |
| startTick | startTick | int | |
| completionTick | completionTick | int | startTick + bureaucracy delay |
| cancelled | cancelled | bool | Vrai si corpo a réussi à bloquer |

**C# type** : `NationalizationProcess` in `SimulationContracts.cs`

### ScoreboardEntry (BaseModel / struct)
| Python field | C# field | Type | Notes |
|---|---|---|---|
| corpId | corpId | string | |
| corpName | corpName | string | |
| credits | credits | float | |
| tileCount | tileCount | int | |
| globalReputation | globalReputation | float | |
| score | score | float | Score composite |

**C# type** : `ScoreboardEntry` in `SimulationContracts.cs`

### CorporationData — champ ajouté
| Champ | Type Python | Type C# | Notes |
|-------|-------------|---------|-------|
| globalReputation | float | float | Valeur par défaut 0.0 — Phase 7.5 |

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
| `AtmosphericGas` / `AtmosphericComposition` / `GlobalWindPattern` / `BodyListEntry` sont préfixés `Simulation*` en C# | Aucun — la désérialisation JSON dépend des noms de champs, pas du nom du struct | Préserver ce préfixe pour éviter une collision avec les types monde Unity |
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
