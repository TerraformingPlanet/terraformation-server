# Changelog — Terraformation

Historique des phases et sprints complétés. Pour le backlog actif, voir [ROADMAP.md](ROADMAP.md).

---

## ✅ Phase 8 — Système d'Événements (M1–M3) (2026-04-21)

**Complété** :
- [x] `EventType` IntEnum (7 types : RencontreAlienne, TempeteSolaire, DecouverteMiniere, CriseEconomique, SabotageCorpo, Rebellion, MigrationPopulation)
- [x] `EventEffect` BaseModel (resourceType, resourceDelta, creditsDelta, reputationDelta, populationDelta)
- [x] `EventData` BaseModel (id, eventType, name, description, tick, affectedEntityId, affectedEntityType, effect, isResolved)
- [x] `logic/events.py` : `GAME_EVENT_CONFIGS` (7 entrées pondérées), `draw_event()`, `apply_event_to_corporation()`
- [x] `runtime.py` : `_game_events` registry + wipe dans `bootstrap_sol()`, `_process_event_tick_locked()` (p=5%/tick), `list_game_events(limit=20)`
- [x] `GET /game/events?limit=N` endpoint FastAPI
- [x] MCP tool `list_game_events(limit=20)`
- [x] Miroirs C# : `GameEventType`, `GameEventEffect`, `GameEventData`, `GameEventList` dans `SimulationContracts.cs` (0 erreur validé)
- [x] 8/8 tests Python — `SimulationCore/tests/test_phase8_events.py`

**En attente** : M4 popup UI HUD + Phase 8.5 intégration agent LLM

---

## ✅ Phase 9.5 — Ressources tradables & MarketManager global (2026-04-20)

**Complété** :
- [x] `ResourceType` étendu : `Iron=5`, `Oxygen=6`, `Water=7`, `Tech=8`
- [x] `CorpResourceType` C# mirror étendu dans `SimulationContracts.cs`
- [x] `TRADABLE_RESOURCES` mis à jour dans `logic/market.py`
- [x] `GlobalMarketState` BaseModel (`systemId`, `listings`, `tick`, `marketCount`)
- [x] `compute_global_market()` fonction pure (moyenne pondérée par supply)
- [x] `get_global_market()` méthode runtime thread-safe
- [x] `GET /game/market/global/{system_id}` endpoint FastAPI
- [x] MCP tool `get_global_market(system_id="sol")`
- [x] `GlobalMarketState` struct C# + `GlobalMarketStateWrapper` dans `SimulationContracts.cs`
- [x] `GameHUD.cs` : 3 switch statements étendus (Iron/Oxygen/Water/Tech)
- [x] `test_phase95_resources.py` (4/4) + `test_phase95_global_market.py` (4/4)

---

## ✅ Phase 7.5 — États, Réputation, Nationalisation, Scoreboard (2026-04-20)

**Complété** :
- [x] `StateType` (Capitalist=0, Nationalist=1) + `StateData` (id, name, stateType, tileIds, bureaucracy, corruptionRate, toleranceThreshold)
- [x] `ReputationEventReason` (ContractCompleted…CorruptionDetected) + `ReputationEvent` (sourceId, targetId, deltaGlobal, deltaBilateral, reason, tick)
- [x] `NationalizationProcess` (id, stateId, corpId, tileId, startTick, completionTick, cancelled)
- [x] `ScoreboardEntry` (corpId, corpName, credits, tileCount, globalReputation, score)
- [x] `CorporationData.globalReputation: float = 0.0` — champ ajouté
- [x] Miroirs C# : `CorpStateType`, `CorpReputationEventReason`, `SimStateData`, `NationalizationProcess`, `ScoreboardEntry` dans `SimulationContracts.cs`
- [x] 9 endpoints FastAPI : `/game/states`, `/game/states/{id}`, `/game/reputation`, `/game/nationalizations`, `/game/nationalizations/{id}/corrupt`, `/game/scoreboard`
- [x] 8 tools MCP : `create_state`, `list_states`, `get_state`, `get_reputation`, `list_reputations`, `list_nationalizations`, `corrupt_nationalization`, `get_scoreboard`
- [x] Unity HUD : scoreboard strip + panneau de nationalisation dans `GameHUD.cs`

**Résumé** :
> States & Reputation layer complet — les États peuvent nationaliser les tuiles des corpos avec un processus progressif (délai = bureaucratie + corruption). Les corpos peuvent tenter de corrompre le processus. Le scoreboard classe toutes les corpos par score composite. 8 couches d'interaction État ↔ Corporation.

---

## ✅ Phase 7.2 — HUD Bâtiments : Icônes UI Font Awesome (2026-04-20)

**Complété** :
- [x] `GameHUDBuildingIcons.cs` — table centralisée `CorpBuildingType -> displayName + unicode Font Awesome + fallback + teinte`
- [x] `GameHUD.cs` — preview d'icône dans la zone "Construire un bâtiment" du RightPanel
- [x] `GameHUD.cs` — liste des bâtiments de la tuile rendue en lignes `icône + libellé + état (tick, staff)`
- [x] `Assets/Resources/Fonts/Font Awesome 7 Free-Solid-900.otf` — police locale importée pour l'UI bâtiments
- [x] `GameHUD.cs` — création dynamique de `TMP_FontAsset` + préchargement des glyphes requis
- [x] Fallback sûr si la police n'est pas chargée : lettres visibles au lieu de glyphes manquants

**Décision** :
> Font Awesome est utilisé comme source d'icônes UI pour le HUD bâtiments uniquement. Les types gameplay (`CorpBuildingType`, `CorpBuilding`, `BuildingData`) restent indépendants de cette représentation visuelle.

---

## ✅ Phase 7.1 — Ownership Borders & Claim/Unclaim UI (2026-04-19)

**Commits** : `2664364`, `40da8c4`, `fad0973`, `ec65103`, `03e6a49`, `898f274`

**Complété** :
- [x] `GetBoundaryLoops()` réécrit (algorithme Goldberg edge-map)
- [x] `OwnershipBorderRenderer.cs` — dessine les LineRenderers de bordures colorées par corpo sur le globe
- [x] `GameHUD.cs` (~650 lignes) — HUD unifié code-driven : TopBar, LeftPanel (progression terraformation), RightPanel (inspecteur tuile + Claim/Unclaim + création corpo), DebugDrawer (F10)
- [x] `TerraformHUD.cs` — events `OnProgressUpdated` + `OnRegionStateChanged`
- [x] `ViewManager.GoBackOneLevel()` public
- [x] Nettoyage ancien Canvas UI (ProgressSlider, SelectedHexPanel désactivés)
- [x] Fix bug guard `OnH3TileResolved` (FindObjectsInactive + suppression check PlanetSubView)
- [x] Fix clic globe → utilise centroïde face survolée (hover) pour cohérence H3
- [x] Détection propriétaire tuile dans RightPanel (badge coloré + nom corpo)
- [x] `CorporationData` + `ClaimedTile` côté Python `SimulationCore` + contrat C# miroir
- [x] `CorporationRegistry` in-memory dans `InMemorySimulationRuntime` (`_corporations`, `_tile_ownership`)
- [x] `POST /game/corporations/{id}/claim-hex?body_id=&tile_id=` — claim un hex libre (409 si déjà pris)
- [x] `bootstrap_sol()` vide `_corporations` et `_tile_ownership`

**Résultat validé en Play Mode** :
> Clic tuile → RightPanel avec Claim/Unclaim ✓ | Tuile claimée → nom + badge couleur corpo ✓ | Bordures rouges ownership visibles sur globe ✓ | Hover et clic cohérents ✓

---

## ✅ Phase 6.75 — Split Simulation / Client / MCP (2026-04-19)

**Complété** :
- [x] `get_projection_summary`, `get_local_summary`, `get_client_snapshot` migrent vers `DedicatedServer` via `_server_get()` — fonctionnent sans Unity
- [x] `get_view_state` marqué définitivement **debug-client only** (bridge Unity port 48621) — le serveur n'a pas connaissance de la vue active Unity
- [x] `MCP_TOOLS_ARCHITECTURE.md` mis à jour : deux familles clarifiées (`debug-client` / `simulation-server`) avec tableau complet des tools et endpoints
- [x] `Tools/mcp/server.py` conservé comme shim legacy, hors scope de migration active

**Résultat** :
> Le monde tourne sans la scène Unity. Unity peut afficher des snapshots serveur. Le MCP est une couche d'outillage distincte du bridge Unity, avec une seule exception permanente (`get_view_state`).

---

## ✅ Phase 0 — Setup & Fondations

- Installation Unity 6 LTS, VS Code, extensions C#
- Projet 3D URP créé dans `E:\terraformation\Game`
- Git configuré
- `CameraController` custom : pan + zoom, nouveau Input System

**Cible atteinte** : scène vide avec caméra mobile

---

## ✅ Phase 1 — Grille Hexagonale (3D Mesh Procédural)

- `HexMetrics.cs` (flat-top, outerRadius=10)
- `HexCell.cs` (coordonnées axiales + TerrainData)
- `HexMesh.cs` (mesh unique, vertex colors)
- `HexGrid.cs` refactorisé (tableau HexCell[], plus de prefabs)
- Raycast 3D sur mesh, tooltip survol
- Shader URP `Terraformation/HexVertexColor`

**Commit** : (premier commit grille)
**Cible atteinte** : grille hexagonale colorée par biome, clic → infos hex

---

## ✅ Phase 2 — Génération Procédurale

**Commit** : `aae1e2d`

- `CelestialBodyData` (ScriptableObject) avec couches `WorldLayer`
- `MapGenParameters` : seed, taille, densité de bruit
- `MapGenerator` : bruit de Perlin fractal (fBm, 2 passes)
- Asset `Kepler-442b.asset` avec 5 couches
- Génération d'une carte de 91 hexagones

**Cible atteinte** : carte générée procéduralement depuis un ScriptableObject

---

## ✅ Phase 3 — Architecture Système Solaire (4 niveaux)

**Commit** : `3dfe365`

- `StarData`, `OrbitalParameters`, `SolarSystemData`, `MapRegion`, `PlanetaryWeatherState`
- `CelestialBodyData` étendu : `PlanetaryPhysics`, `AtmosphericComposition`, `GeologicalProfile`
- `MapGenerator` refactorisé : API `Populate(cells, MapRegion)`
- `HexPhysicalState` + `SoilProfile` ajoutés à `HexCell`

**Cible atteinte** : modèle objet 4 niveaux — SolarSystem → Body → Region → Hex

---

## ✅ Phase 4 — Pipeline IHexSystem

**Commit** : `40f652a`

- `IHexSystem` (interface) + `GenerationContext`
- Pipeline : `HeightSystem`, `TemperatureSystem`, `WaterSystem`, `WindSystem`, `SoilSystem`, `BiomeSystem`, `RiverSystem`, `ValidationSystem`
- `MapGenerator` devient pur orchestrateur du pipeline

**Cible atteinte** : génération modulaire et testable

---

## ✅ Phase 5 — Système de Vues 3 Niveaux

**Commit** : `88c4a6e`

- `CameraController` : `OnZoomedToMin/Max`, mode orbit, `SetMode()`
- `ViewManager` : machine d'état `SolarSystem → Planet → Local`
- `PlanetaryHexGrid` : grille Mercator globale basse résolution
- `PlanetTextureGenerator` : `Texture2D` 512×256 depuis biomes
- `PlanetSphere` : sphère URP + raycast UV → lat/lon → `LoadRegion()`
- `SolarSystemView` : sphères + LineRenderer, clic → `OpenPlanet()`

**Cible atteinte** : navigation solaire → planète → grille hex locale, sans écran de chargement

---

## ✅ Phase 5.5 — Sphère Goldberg Hybride (Vue Planétaire)

**Date** : 17/04/2026

Remplacement de la projection Mercator plate par une sphère de Goldberg Polyèdre interactive.

**Fichiers créés** :
- Lib Hexasphere portée dans `Game/Assets/Scripts/World/Hexasphere/`
- `GoldbergSphereGenerator.cs`, `GoldbergFaceColorizer.cs`, `PlanetSphereGoldberg.cs`
- `GoldbergAtmosphere.cs` + shader `PlanetAtmosphere.shader`

**Fichiers archivés** : `PlanetSphere.cs`, `PlanetTextureGenerator.cs` (remplacés)

**Cible atteinte** : sphère hexagonale 3D rotative, hover highlight, halo atmosphérique coloré

---

## ✅ Phase 5.6 — Projection Plan Tangent Local Dynamique

**Date** : 17/04/2026

Remplacement de la vue Mercator flat (toggle Vue 2) par un plan tangent centré sur la dernière tuile cliquée.

**Fichiers créés** : `LocalProjection.cs`, `PlanetTangentMesh.cs`, `PlanetTangentView.cs`, `PlanetTangentInput.cs`

**Cible atteinte** : plan tangent sans distorsion Mercator, transition animée sphère → plan, re-centrage dynamique

---

## ✅ Phase 6 — Terraformation (Gameplay)

**Commits** : `1482112` (code) · `48753cf` (scène câblée)

- `TickManager` : tick configurable, pause/resume
- `TerraformAction` (enum) + `TerraformActionData` (ScriptableObject)
- `TerraformSystem` : applique une action sur un hex, rejoue `BiomeSystem`
- `TerraformProgressTracker` : score global de terraformation
- HUD : barre de progression
- Scène `Game.unity` entièrement câblée

**Cible atteinte** : hex qui change de biome visible suite à une action joueur

---

## ✅ Phase 6.9 — Refactoring Hiérarchie Cosmos & Entités Politiques

**Date** : 17/04/2026

- Remplacement du monolithe `CelestialBodyData` par une vraie hiérarchie : `CelestialBody` → `OrbitalBody` → `Planet`, `Moon`, `Asteroid`, `GasGiant`, `StarBody`, `GalaxyData`
- `PoliticalEntity` (abstract), `Corporation`, `NationState` — runtime `[Serializable]`
- `ResourceType` enum + `ResourceStack`, `BuildingData` (ScriptableObject), `BuildingInstance`
- `HexOwnership` struct sur `HexCell`
- `Project` abstrait + 5 sous-types

**Décisions** :
- Cosmos = ScriptableObjects éditables en Inspector
- Corporation/NationState = classes runtime JSON-transportables (pas ScriptableObject)
- `GasGiant.isLandable` toujours `false`

**Cible atteinte** : hiérarchie propre et extensible ; squelettes économie/corporation/projets en place

---

## ✅ Phase 6.75 — Split Simulation / Client / MCP (tâches complétées)

Extraction progressive de la simulation hors Unity.

**Réalisé** :
- Seams Unity : `ITickSource`, `IHexCellStore`, `IGridRefreshSink`
- `TerraformSimulationSession` + `TerraformHabitabilityEvaluator` extraits
- Contrats définis : `WorldState`, `RegionState`, `ProjectionState`, `SimulationCommand`, `SimulationEvent`, `ClientSnapshot`
- Structure monorepo cible atteinte : `Game/`, `Mcp/`, `DedicatedServer/`, `SimulationCore/`
- `SimulationCore/terraformation_sim/` : `models.py` (Pydantic), `logic.py`, `runtime.py` — consommés par `DedicatedServer`
- `DedicatedServer` : 14 routes HTTP, `InMemorySimulationRuntime`, tick loop, action queue
- 9 tools MCP serveur opérationnels : `get_projection_state`, `get_region_state`, `get_world_state`, `get_last_simulation_event`, `get_server_action_definitions`, `advance_simulation_tick`, `open_server_region`, `queue_server_terraform_action`, `apply_server_cell_delta`
- Stack Docker unifiée : compose canonique racine, wrappers dans `Mcp/` et `DedicatedServer/`
- `TerraformSystem.preferServerCommands` : délégation au serveur avec fallback local
- `RegionState.cells[]` : 24 cellules complètes validées
- `TerraformSystem.ApplyAuthoritativeRegionState` : synchro grille locale depuis le serveur
- `TerraformProgressTracker` en mode autoritaire depuis `RegionState.terraformationProgress`

**En cours (voir ROADMAP.md)** : isolation du bridge Unity pour les tools visuels uniquement

---

## ✅ Sprint 0 — Outillage AI, Debug et MCP (complété)

- Workflow AI/debug documenté (`AI_DEBUG_WORKFLOW.md`)
- Checklist de validation presets documentée (`TEST_PRESETS_CHECKLIST.md`)
- `RuntimeDebugHttpServer.cs` + `RuntimeDebugFacade.cs` — bridge HTTP Unity port 48621
- Serveur MCP FastMCP (Python) conteneurisé, porté par `Mcp/`
- 7 tools MCP exposés : `get_view_state`, `get_projection_summary`, `get_local_summary`, `get_console_errors`, `take_screenshot`, `launch_preset`, `open_region`
- VS Code MCP configuré (`.vscode/mcp.json`, transport HTTP)
- Handshake MCP validé le 17/04/2026
- Bug `Host` header Windows HTTP.sys corrigé (forcer `Host: 127.0.0.1:48621` dans httpx)

---

## ✅ Sprint A — Stabilisation Debug + Hydrologie Locale v2 (partiellement complété)

**Complété** :
- `DebugHydrologyPanel` : interactions fiables, refresh immédiat
- Actions locales (`Apply To Cell`, `Regenerate Local`) mettent à jour l'état visuel et le HUD
- Débordement de bassin avec exutoire dynamique
- Stabilisation des bassins voisins qui fusionnent
- Réduction des faux positifs `Coast`
- Checklist manuelle minimale construite

**Restant (voir ROADMAP.md)** : vérification en Play Mode des 5 cas de référence
