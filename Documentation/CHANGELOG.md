# Changelog — Terraformation

Historique des phases et sprints complétés. Pour le backlog actif, voir [ROADMAP.md](ROADMAP.md).

---

## ✅ Sprint DB — Persistence complète des entités gameplay (2026-04-21)

**Problème résolu** : 9 entités gameplay (`_corporations`, `_contracts`, `_states`, `_nationalizations`, `_reputations`, `_trade_routes`, `_expeditions`, `_construction_queues`, `_markets`) étaient uniquement en mémoire — perdues au redémarrage serveur.

**persistence.py** :
- [x] 9 nouvelles tables SQLAlchemy : `corporations`, `contracts`, `game_states`, `nationalizations`, `reputations`, `trade_routes`, `expeditions`, `construction_queues`, `markets`
- [x] `CREATE UNIQUE INDEX IF NOT EXISTS uq_reputations ON reputations(source_id, target_id)` dans `_ensure_schema()`
- [x] 30 méthodes abstraites dans `StateRepository` ABC : `save/delete/clear_corporation`, `save/delete/clear_contract`, `save/delete/clear_state`, `save/delete/clear_nationalization`, `upsert_reputation/clear_reputations`, `save/delete/clear_trade_route`, `save/delete/clear_expedition`, `save/delete/clear_construction_queue`, `save/delete/clear_market`
- [x] No-ops correspondants dans `InMemoryRepository`
- [x] Helpers `_upsert()` + `_delete_by_pk()` génériques dans `PostgresRepository`
- [x] Implémentations `PostgresRepository` (upsert ON CONFLICT pour chaque entité)
- [x] 9 nouveaux champs `SavedState` : `corporations_json`, `contracts_json`, `states_json`, `nationalizations_json`, `reputations_raw`, `trade_routes_json`, `expeditions_json`, `construction_queues_json`, `markets_json`
- [x] SELECTs correspondants dans `PostgresRepository.load()`

**runtime.py — Write-through** :
- [x] `register_corporation` / `claim_tile` / `unclaim_tile` / `_complete_construction_locked` → `save_corporation`
- [x] `propose_contract` / `bid_on_contract` / `confirm_bidder` / `accept_contract` / `break_contract` → `save_contract`
- [x] `create_state` → `save_state`
- [x] `corrupt_nationalization` / `cancel_nationalization_via_contract` → `save_nationalization`
- [x] `_apply_reputation_event_locked` → `upsert_reputation`
- [x] `create_trade_route` / `suspend_trade_route` / `resume_trade_route` / `delete_trade_route` → save/delete route commerciale
- [x] `launch_expedition` → `save_expedition`
- [x] `_get_or_create_territory_queue_locked` → `save_construction_queue`
- [x] `_process_reputation_tick_locked` : nationalisations créées + complétées → `save_nationalization`
- [x] Flush toutes les 10 ticks : corps, marchés, files de construction, expéditions in-transit
- [x] `bootstrap_sol()` : 9 appels `clear_X()` supplémentaires

**runtime.py — `_hydrate_from_saved()`** :
- [x] Reconstruction des 9 collections depuis `SavedState`
- [x] Rebuild `_tile_ownership` depuis `corp.claimedTiles`
- [x] Rebuild `_buildings` depuis `corp.buildings`

**Tests** :
- [x] `test_phase_sprint_db.py` — 5 tests (T01 corp round-trip, T02 tile ownership, T03 contrat, T04 state+réputation, T05 bootstrap_sol mock clears) — **41 passed, 18 skipped (noise absent), 0 failed**

---

## ✅ Phase 12 Polish — Sprint UI (2026-04-21)

**P1 — Tick counter + solde crédits dans le TopBar** (`GameHUD.cs`) :
- [x] Champs : `_tickCreditsLabel` (TextMeshProUGUI), `_lastKnownTick = -1`, `_selectedCorpCredits = float.NaN`
- [x] `BuildTopBar()` — `_tickCreditsLabel` TMP 11pt gris, `preferredWidth=180`, inséré entre `_planetLabel` et `_toggleViewBtn`
- [x] `TickStatusDto` — classe privée sérialisable (`tickCount`, `tickRunning`) pour `JsonUtility.FromJson`
- [x] `PollTickStatus()` — coroutine polling `GET /tick/status` toutes les 10s ; met à jour `_lastKnownTick` + appelle `UpdateTickCreditsLabel()`
- [x] `UpdateTickCreditsLabel()` — affiche `Tick N` seul, ou `Tick N  |  X cr` si `_selectedCorpCredits` valide
- [x] `RefreshCorpListForTile()` — capture `wrapper.items[ownerIdx].credits` → `_selectedCorpCredits` sur tuile claimée ; reset à `float.NaN` sur tuile vide
- [x] `Start()` — `StartCoroutine(PollTickStatus())` lancé aux côtés de `PollEventFeed()`

**P2 — EventType français dans la popup** (`GameHUD.cs`) :
- [x] `LocalizeEventType(EventType t)` — méthode statique switch-expression, 9 valeurs FR (ex: `CriseEconomique` → `"Crise Économique"`)
- [x] `PollEventFeed()` — popup passe de `{ev0.eventType}` à `{LocalizeEventType(ev0.eventType)}`

---

## ✅ Phase 8 M4 + Phase 8.5 gaps — Fermeture écarts (2026-04-21)

**Phase A — Popup notification d'événement Unity** :
- [x] `GameHUD.cs` — champs `_eventPopupPanel` (GameObject), `_eventPopupLabel` (TextMeshProUGUI), `_lastSeenEventTick = -1`
- [x] `BuildEventPopupPanel()` — 380×80px, anchor top-center (pivot 0.5/1.0), fond rouge foncé (`Color(0.35, 0.05, 0.05, 0.9)`), TMP 12pt centré ; appelé depuis `BuildCanvas()`
- [x] `ShowEventPopup(string text, float duration = 7f)` — coroutine : active panel → WaitForSeconds → désactive
- [x] `PollEventFeed()` enrichi — détection `newestTick > _lastSeenEventTick` + baseline guard (`>= 0`) → `StartCoroutine(ShowEventPopup("⚡ EventType — nom"))` ; initialise `_lastSeenEventTick` au premier poll sans afficher de popup

**Phase B — Endpoints REST + MCP agent context/run** :
- [x] `DedicatedServer/app/server.py` — `GET /game/agent/context/{state_id}` → snapshot dict (404 si state inconnu)
- [x] `DedicatedServer/app/server.py` — `POST /game/agent/run/{state_id}` → `AgentAction` (déclenche cycle LLM synchrone, 404 si state inconnu)
- [x] Import `AgentAction` ajouté dans `server.py`
- [x] `Mcp/server.py` — `get_agent_context(state_id)` wraps `GET /game/agent/context/{state_id}`
- [x] `Mcp/server.py` — `run_agent_for_state(state_id)` wraps `POST /game/agent/run/{state_id}` (section `# Phase 8.5`)
- [x] `runtime.py` — aucune modification requise (`get_agent_context` + `run_agent_for_state` existaient déjà)

---

## ✅ Phase 11.2 M1 — FSM BotCorporation (2026-04-25)

**Complété** :
- [x] `models.py` — `CorpProfile` (Economiste/Expansionniste/Militariste), `BotFSMState` (Idle/Expanding/Building/Trading/Raiding)
- [x] `models.py` — `CorporationData` étendu : `profile`, `fsmState`, `fsmThresholds`
- [x] `models.py` — `AgentActionType` étendu : `ClaimTile=10`, `ConstructBuilding=11`, `UpdateFsmThresholds=12`, `ReorderConstructionQueue=13`
- [x] `logic/corp_fsm.py` — `CorpSimSnapshot` dataclass + `CORP_FSM_DEFAULTS` + 3 fonctions de transition FSM pures + `compute_next_fsm_state` + `compute_fsm_actions`
- [x] `runtime.py` — `_build_corp_snapshot_locked()` (snapshot lock-free, cap 10 tuiles adj)
- [x] `runtime.py` — `_run_bot_fsm_bg()` : snapshot sous lock → FSM hors lock → apply sous lock (même pattern que state agent)
- [x] `runtime.py` — `_process_bot_tick_locked()` : spawne un thread bot par corp IA, appelé depuis `_advance_tick_locked()`
- [x] `runtime.py` — `run_world_agent_cycle()` câble les corps IA (threads FSM)
- [x] `runtime.py` — `trigger_agent_for_entity()` câble les corps IA (plus de no-op)
- [x] `runtime.py` — `_apply_agent_action_locked()` étendu : `ClaimTile`, `ConstructBuilding`, `UpdateFsmThresholds`, `ReorderConstructionQueue`
- [x] `runtime.py` — `register_corporation()` accepte `profile: CorpProfile`
- [x] `server.py` — `_CreateCorporationRequest` + `profile`, `POST /game/corporations` passe `profile` au runtime
- [x] `server.py` — `POST /game/corporations/{id}/buildings` déclenche `trigger_agent_for_entity(state_id, "factory_request")` (complète Phase 11.1 M2)
- [x] `SimulationContracts.cs` — `CorpProfile`, `BotFSMState`, champs `CorporationData.profile/fsmState`, `AgentActionType` 10-13
- [x] 15 tests `test_phase112_corp_fsm.py` (15 passed, 5 skipped/no-noise) — 123 total suite

---

## ✅ Phase 11.1 — Agent Monde centralisé (2026-04-24)

**Complété** :
- [x] `runtime.py` — `run_world_agent_cycle(reason)` : scan global États + Corps IA, spawne un thread daemon par entité
- [x] `runtime.py` — `trigger_agent_for_entity(entity_id, reason)` : réveil ponctuel, `KeyError` sur ID inconnu/non-IA
- [x] `runtime.py` — `_get_ai_state_ids_near_tile_locked(body_id, tile_id)` : H3 `grid_disk` k=1 pour détecter états voisins
- [x] `runtime.py` — `_advance_tick_locked()` remplace l'ancien inline loop par `run_world_agent_cycle` dans un seul thread
- [x] `WORLD_AGENT_TICK_INTERVAL` env var (défaut 10, rétro-compatible `AGENT_TICK_INTERVAL`)
- [x] `server.py` — `POST /game/agent/world/run` + `POST /game/agent/trigger/{entity_id}`
- [x] `server.py` — M2 triggers : `claim_hex → border_claim`, `propose_contract → contract_offer`, `break_contract → contract_breach`
- [x] `Mcp/server.py` — `run_world_agent_cycle()` + `trigger_agent_for_entity()` MCP tools
- [x] 10 tests dans `tests/test_phase111_world_agent.py` (10 skipped localement, exécutables en Docker)
- [ ] M2 partiel : trigger `factory_request` (buildings sur tuile d'État) reporté Phase 11.2

---

## ✅ Phase 10.5 — Construction multi-tick & File de territoire (2026-04-23)

**Complété** :
- [x] `models.py` — `ConstructionItem`, `ConstructionStatus`, `TerritoryQueue`, `BUILDING_CONSTRUCTION_COST`, `EB_FORMAL_CAPACITY`, `EB_FORTUNE_CAPACITY`, `EB_FORTUNE_WOOD_COST`
- [x] `runtime.py` — `construct_building()` renvoie un `ConstructionItem` (n'instancie plus immédiatement)
- [x] `_process_construction_tick_locked()` — avance les files, overflow, complète via `_complete_construction_locked()`
- [x] `_check_eb_de_fortune_locked()` — EB de fortune auto si population + Wood, consomme Wood
- [x] `_get_or_create_territory_queue_locked()`, `_compute_territory_capacity_locked()` — MVP territoire = une tuile
- [x] `cancel_construction_item()` + `list_construction_queues()`
- [x] `bootstrap_sol()` wipe des queues
- [x] `DedicatedServer/app/server.py` — `GET /game/corporations/{id}/construction-queue`, `DELETE /game/corporations/{id}/construction-queue/{item_id}`
- [x] `SimulationContracts.cs` — `ConstructionStatus`, `ConstructionItem`, `TerritoryQueue`, `TerritoryQueueList`
- [x] `test_phase105_construction.py` — 6 tests modèles (toujours run) + 10 tests runtime (skip si noise absent)

---

## ✅ Phase 10 — Multijoueur Réseau (2026-04-21)

**Complété** :
- [x] Authentification joueur JWT (HS256, python-jose, bcrypt) — `/auth/register`, `/auth/login`, `/auth/link-corp`
- [x] Table `players` PostgreSQL + `InMemoryRepository` stubs
- [x] WebSocket push FastAPI `GET /game/ws/events?token=JWT` — broadcast tick aux clients connectés
- [x] `runtime.py` — `set_ws_broadcast_callback()`, callback tick avancé
- [x] `startup` hook FastAPI — boucle asyncio capturée, `_sync_broadcast` thread-safe via `run_coroutine_threadsafe`
- [x] `PlayerSession.cs` (singleton DontDestroyOnLoad) + `LoginPanel.cs` Unity
- [x] `SimulationWebSocketClient.cs` — NativeWebSocket (OpenUPM 1.1.4), reconnexion auto 2 s
- [x] `TickManager.cs` patché — mode serveur WS quand client présent
- [x] `GameHUD.cs` patché — events via WS push, polling HTTP en fallback
- [x] Colonisation caravane — `ExpeditionUnit` Land → arrivée → `ClaimedTile` créée avec pop de base (`_process_expedition_tick_locked`)
- [x] `test_phase10_caravane.py` — 3 tests (colonise, ne vole pas, space n'active pas)
- [x] ARCHITECTURE.md mis à jour (Mirror → WebSocket FastAPI + NativeWebSocket)

---

## ✅ Phase 8.5 M7 — Benchmark multi-modèles LLM (2026-04-21)

**Complété** :
- [x] `conftest.py` — fixture `benchmark_model` parametrée (`LLM_BENCHMARK_MODELS`), `bench_recorder`, `_BenchmarkStore` session-scoped, hook `pytest_terminal_summary` (tableau ✅/❌ + latence)
- [x] `test_phase85_agent_benchmark.py` — 10 scénarios × N modèles :
  - 5 scénarios décision d'état : `json_parse`, `tools_call`, `stable_noop`, `nationalist_react`, `capitalist_crisis`
  - 5 scénarios sélection outil MCP gameplay : `mcp_advance_tick`, `mcp_world_inspect`, `mcp_irrigate_cell`, `mcp_open_region`, `mcp_coherence_check`
- [x] `.env` — `LLM_BENCHMARK_MODELS=gemma4,Qwen3.6,deepseek-coder-16b`
- [x] Mark `@pytest.mark.llm_benchmark` enregistré dans `pytest_configure`
- [x] Skills et ROADMAP mis à jour

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

**Complété** : M4 popup UI HUD (2026-04-21 — voir entrée "Phase 8 M4 + Phase 8.5 gaps") + Phase 8.5 intégration agent LLM (endpoints context/run livrés)

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
