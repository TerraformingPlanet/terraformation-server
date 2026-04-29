# Contracts Index — Python ↔ C# (2026-04-29)

Source de vérité complète : `Documentation/SIMULATION_CONTRACTS.md`
Ce fichier = index rapide pour identification et navigation.

## Fichiers à modifier simultanément

| Côté | Fichier |
|------|---------|
| Python | `SimulationCore/terraformation_sim/models.py` |
| C# | `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` |
| Doc | `Documentation/SIMULATION_CONTRACTS.md` |

## Enums (IntEnum Python → enum : int C#)

| Python | C# | Notes |
|--------|----|-------|
| `TerrainType` | `TerrainType` | fichier HexCell |
| `TerrainClass` | `TerrainClass` | fichier HexCell |
| `TerraformAction` | `TerraformAction` | |
| `DebugCoherenceOverride` | `DebugCoherenceOverride` | `None_=0` → `None=0` |
| `SimulationCommandType` | `SimulationCommandType` | |
| `SimulationEventType` | `SimulationEventType` | |
| `TradeRouteType` | `TradeRouteType` | `Land/Maritime/Orbital` |
| `TradeRouteActivityStatus` | `TradeRouteActivityStatus` | |
| `ExpeditionStatus` | `ExpeditionStatus` | |
| `TravelStatus` | `TravelStatus` | |
| `AgentActionType` | `AgentActionType` | Phase 8.5 |
| `CorpProfile` | `CorpProfile` | Phase 11.2 |
| `BotFSMState` | `BotFSMState` | Phase 11.2 |
| `SocialClass` | `SocialClass` | `Poor/Middle/Rich` |
| `ResourceType` | `CorpResourceType` | **Préfixé** (collision Unity) |
| `ContractStatus` | `ContractStatus` | `Proposed/Active/Completed/Cancelled/Failed` |
| `ContractVisibility` | `ContractVisibility` | |
| `NationalizationStatus` | `NationalizationStatus` | Phase 7.5 |
| `CorpBuildingType` | `CorpBuildingType` | **Préfixé** (collision Unity) |
| `ConstructionStatus` | `ConstructionStatus` | `Pending=0, InProgress=1, Completed=2, Cancelled=3` |
| `SubHexFeatureType` | `SubHexFeatureType` | Phase Sub-hex |

## Structs / Modèles principaux

| Python | C# | Champs clés |
|--------|----|-------------|
| `SimulationVector2State` | `struct SimulationVector2State` | `x, y` |
| `SimulationCoordinates` | `struct SimulationCoordinates` | `latitude, longitude` |
| `SimulationCellState` | `struct SimulationCellState` | état complet d'une cellule H3 |
| `AtmosphericState` | `struct AtmosphericState` | 6 champs |
| `AtmosphericGas` | `struct SimulationAtmosphericGas` | **Préfixé** |
| `AtmosphericComposition` | `struct SimulationAtmosphericComposition` | **Préfixé** |
| `BodyListEntry` | `struct SimulationBodyListEntry` | **Préfixé** |
| `ProjectionState` | `struct ProjectionState` | 5 champs |
| `RegionState` | `struct RegionState` | 12 champs + `cells[]` |
| `WorldState` | `struct WorldState` | 11 champs |
| `ClientSnapshot` | `struct ClientSnapshot` | 10 champs |
| `CorporationData` | `struct CorporationData` | `id, name, credits, claimedTiles[], score, isAI, colorR/G/B` |
| `ClaimedTile` | `struct ClaimedTile` | `bodyId, tileId, population[]` |
| `PopulationTier` | `struct PopulationTier` | `socialClass, count, avgIncome` |
| `ResourceListing` | `struct ResourceListing` | `resourceType, price, supply, demand` |
| `LocalMarketState` | `struct LocalMarketState` | `corpId, listings[], taxRate, tickComputed` |
| `GlobalMarketState` | `struct GlobalMarketState` | `systemId, listings[], tick, marketCount` |
| `BuildingData` | `struct CorpBuilding` | **Préfixé** — `id, buildingType, tileId, corpId, level...` |
| `ContractData` | `struct ContractData` | `id, type, proposerId, targetId, status, terms...` |
| `NationalizationData` | `struct NationalizationData` | Phase 7.5 |
| `ReputationEntry` | `struct ReputationEntry` | `entityId, value, tier` |
| `TileBioMarketState` | `struct TileBioMarketState` | ring buffer 8 ticks — Phase 11.6b |
| `SubHexFeatureDef` | `struct SubHexFeatureDef` | `featureType, slotIndex, label` — Phase Sub-hex |
| `ConstructionItem` | `struct ConstructionItem` | `id, buildingType, tileId, corpId, status, ticksElapsed, ticksRequired, isEBDeFortune` |
| `TerritoryQueueState` | `struct TerritoryQueueState` | `corpId, tileId, activeItem, pendingItems[], isEBDeFortune, constructionCapacity` |
| `TradeRoute` | `struct TradeRoute` | Phase 9.1 |
| `ExpeditionUnit` | `struct ExpeditionUnit` | Phase 9.1 |
| `SpaceTravel` | `struct SpaceTravel` | Phase 9 |
| `AgentAction` | `struct AgentAction` | Phase 8.5 |
| `AgentMemory` | `struct AgentMemory` | Phase 8.5 |

## Règle de préfixage C#

Quand un nom Python collerait avec un type Unity global, préfixer en C# :
- `Simulation` → `SimulationAtmosphericGas`, `SimulationBodyListEntry`
- `Corp` → `CorpBuildingType`, `CorpBuilding`, `CorpResourceType`
- La désérialisation JSON ne dépend que des **noms de champs**, pas du nom de struct → le préfixage est safe

## Mapping de types

| Python | C# |
|--------|----|
| `str` | `string` |
| `int` | `int` |
| `float` | `float` |
| `bool` | `bool` |
| `list[T]` | `T[]` |
| `dict[str, T]` | `T[]` + wrapper ou `List<KeyValuePair>` |
| `IntEnum` | `enum NomEnum : int` |
| `Optional[T]` = `T \| None` | `T` avec valeur par défaut |

## Wrapper JSON Unity (désérialisation de listes)

`JsonUtility` ne supporte pas les tableaux JSON racines. Toujours wrapper :
```csharp
[System.Serializable]
private class MonTypeListDto { public MonType[] items; }
// Usage : JsonUtility.FromJson<MonTypeListDto>("{\"items\":" + json + "}")
```
