# Roadmap — Terraformation & Colonisation Spatiale (Backlog Actif)

Chaque phase a une cible claire. **Ne pas passer à la suivante avant d'avoir atteint la cible.**

> Pour l'historique des phases complétées (Phase 0 → 6.9, Sprint 0), voir [CHANGELOG.md](CHANGELOG.md).

---

## Navigation — agents IA

> **Avant d'implémenter une tâche de ce backlog, lis dans cet ordre :**
>
> | Étape | Document | Ce qu'on y cherche |
> |-------|----------|--------------------|
> | 1 | Ce fichier (ROADMAP) | Tâche exacte + critères de sortie (tableau récapitulatif en bas) |
> | 2 | [Description_du_jeu.md §lié](description_jeu/Description_du_jeu.md) | Design intent : pourquoi la mécanique existe, comment elle se comporte |
> | 3 | [ARCHITECTURE.md](ARCHITECTURE.md) | Contraintes de stack, couches autorisées, décisions techniques prises |
> | 4 | [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md) | Où placer les fichiers, conventions de nommage |
>
> **Références conditionnelles :**
> - Tâche touche un contrat Python ↔ C# → [SIMULATION_CONTRACTS.md](SIMULATION_CONTRACTS.md)
> - Tâche touche un tool MCP → [MCP_TOOLS_ARCHITECTURE.md](MCP_TOOLS_ARCHITECTURE.md)
> - Tâche de debug visuel Unity → [AI_DEBUG_WORKFLOW.md](AI_DEBUG_WORKFLOW.md)
>
> Ne jamais proposer une implémentation avant d'avoir lu les critères de sortie de la tâche.

---

## Terminé : Phase 6.9 — Migration H3 Client Unity (vues planétaires)

**Complété** :
- [x] `GoldbergFaceColorizer.cs` — suppression de `Colorize(faces, GridData)` ; seule `ColorizeFromServerTiles()` subsiste
- [x] `PlanetFlatMesh.cs` — ajout `TriangulateH3(GoldbergTileState[], colorByType)` ; Mercator conservé uniquement pour vue locale
- [x] `PlanetFlatView.cs` — migration complète vers H3 : `LoadPlanetFromH3()`, `GetH3Tile()`, `IsLoaded` via `_h3Tiles`
- [x] `PlanetFlatInput.cs` — hover/clic via `GetH3Tile()` → `ShowH3TileInfo()`
- [x] `PlanetTangentView.cs` — suppression param `GridData`, ajout `RefreshColorsFromH3()`
- [x] `PlanetSphereGoldberg.cs` — suppression `_planetGrid`, `CachedSphere.Grid`, `Colorize(Mercator)` ; event `OnH3TilesReady` fire après fetch serveur ; stubs `GetProjectedCell` / `TryBuildProjectionSummary`
- [x] `ViewManager.cs` — abonnement `OnH3TilesReady` → `LoadPlanetFromH3` + `RefreshColorsFromH3` ; suppression `PlanetaryHexGrid.ActiveGrid` de `ShowProjectedPlanet` ; `OpenRegion` simplifié
- [x] `FlatDebugOverlay.cs` — désabonnement Mercator, labels désactivés (avertissement console)
- [x] `TerraformHUD.cs` — `ShowH3TileInfo(GoldbergTileState)` pour affichage HUD globe/flat
- [x] `SimulationContracts.cs` — structs `GoldbergTileState` et `SimulationBodyListEntry`

**Résultat** :
> `PlanetaryHexGrid` ne pilote plus aucune vue planétaire. Globe, FlatView et TangentView sont colorisés exclusivement depuis les tuiles H3 autoritatives du `DedicatedServer`. `PlanetaryHexGrid` reste utilisé uniquement pour la génération de la vue locale hexagonale et ses constantes de résolution.

---

## Terminé : Phase 6.8 — Migration H3 (Uber H3 hexagonal hiérarchique)

**Complété** :
- [x] `SimulationCore/terraformation_sim/models.py` — `GoldbergTileState.tileId: str`, `neighborIds: list[str]`, `boundaryLatLons`, `h3Resolution`, `GENERATION_VERSION = "v2"`
- [x] `SimulationCore/terraformation_sim/logic.py` — génération H3 (`uncompact_cells`, `grid_disk`, `cell_to_boundary`), résolutions 0/1/2 selon rayon
- [x] `SimulationCore/terraformation_sim/persistence.py` — `tile_id: str`, colonne `String(20)`
- [x] `SimulationCore/terraformation_sim/runtime.py` — `h3Resolution`, lookup par tileId string, `/neighbors`, `/at`
- [x] `DedicatedServer/app/server.py` — endpoints `/tiles/at` et `/tiles/{tile_id}/neighbors`, tile_id str
- [x] `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` — `tileId: string`, `neighborIds: string[]`
- [x] `Mcp/server.py` — `tile_id: str`, outils `get_body_tile_at`, `get_body_tile_neighbors`
- [x] Docker build + validation (5882 tuiles H3 res=2, genVersion=v2, neighbors, /at, delta)

---

## Terminé : Phase 6.9 — bootstrap-sol (système solaire complet)

**Complété** :
- [x] `SimulationCore/terraformation_sim/runtime.py` — `bootstrap_sol()` + `_bootstrap_sol_galaxy_locked()` : wipe état existant puis crée Sol complet
- [x] `DedicatedServer/app/server.py` — `POST /commands/bootstrap-sol`
- [x] Validation : 16 corps générés (Soleil, 8 planètes, 5 lunes, Kepler-442 star + Kepler-442b), résolutions H3 correctes (Luna/Io/Europa res=1=842 tiles, reste res=2=5882 tiles)

**Corps générés** :

| Corps | Type | Radius (km) | H3 | Override | Water |
|---|---|---|---|---|---|
| Sun | Star | 695 700 | res=2 | — | — |
| Mercury | Planet | 2 440 | res=2 | Arid | 0.00 |
| Venus | Planet | 6 051 | res=2 | Arid | 0.00 |
| **Earth** | Planet | 6 371 | res=2 | Coast | **0.71** |
| Mars | Planet | 3 390 | res=2 | Arid | 0.02 |
| Jupiter | Planet | 69 911 | res=2 | None_ | 0.00 |
| Saturn | Planet | 58 232 | res=2 | None_ | 0.00 |
| Uranus | Planet | 25 362 | res=2 | Frozen | 0.00 |
| Neptune | Planet | 24 622 | res=2 | Frozen | 0.00 |
| Luna | Moon | 1 737 | res=1 | Arid | 0.01 |
| Io | Moon | 1 821 | res=1 | Arid | 0.00 |
| Europa | Moon | 1 560 | res=1 | Ocean | 0.70 |
| Ganymede | Moon | 2 634 | res=2 | Frozen | 0.30 |
| Titan | Moon | 2 575 | res=2 | Arid | 0.10 |
| Kepler-442 | Star | 513 000 | res=2 | — | — |
| Kepler-442b | Planet | 7 600 | res=2 | Ocean | 0.55 |

---

## ✅ Terminé : Phase 6.5 — Relief & Hydrologie Locale (terminé 2026-04-19)

> Design de référence : [GDD.md §8](GDD.md) — Relief & Hydrologie

**Complété** :
- [x] `MapRegion.ComputeCoherence()` + `CoherenceValidationSystem` enrichis (Sprint B)
- [x] Connectivité hydrologique H3 côté serveur : composantes eau, exutoires, cuvettes, côtes (Sprint B / logic/)
- [x] Heuristique locale côte/océan remplacée par connectivité H3 serveur
- [x] Cas de référence vérifiés en Play Mode : océan ✅ côte ✅ bassin ✅ désert ✅ pôle ✅ (Sprint A)

**Écart différé** : débordement de bassin dynamique (exutoire runtime) — différé Phase 7+

**Résultat** : les montagnes drainent, les cuvettes se remplissent, côtes distinguées des lacs, pôles cohérents avec la projection.

---

## ✅ Sprint A — Stabilisation Debug + Hydrologie Locale v2 (terminé)

> Design de référence : [GDD.md §8](GDD.md) — Relief & Hydrologie | [AI_DEBUG_WORKFLOW.md](AI_DEBUG_WORKFLOW.md)

**Complété** :
- [x] Vérifier en Play Mode les 5 cas de référence (océan ouvert, côte, bassin, désert drainant, pôle gelé)
- [x] Les bassins fermés, côtes et lacs sont lisibles via projection H3 (generation-stats) sur les 5 presets
- [x] Seuils hydrologiques documentés dans `run_generation_quality_suite` + `_evaluate_generation_quality`
- [x] Smoke tests reworkés en architecture H3-native deux tracks (commit `4065789`) :
  - Track 1 (DedicatedServer) : generation-stats quality suite + temperature checks
  - Track 2 (Unity bridge) : launch + `unity-projection-override` + projection H3 + console
  - Supprimé : `open-region`, HexGrid local (PlanetaryHexGrid pré-H3), `time.sleep`

**Résultats Play Mode 2026-04-19** : Ocean ✅ Coast ✅ Arid ✅ Frozen ✅ Basin ✅ — zéro failure, zéro warning

---

## ✅ Sprint B — Cohérence Macro → Micro + Projection Hydrologique (terminé 2026-04-19)

> Design de référence : [GDD.md §8](GDD.md) — Relief & Hydrologie (cohérence macro→micro)

**Complété** :
- [x] `MapRegion.CoherenceConstraint` enrichi : 3 nouveaux champs `rugosity`, `accumulationIndex`, `reliefContrast`
- [x] `MapRegion.ComputeCoherence()` — calcule les 3 signaux de relief depuis les données projection existantes
- [x] `CoherenceValidationSystem` — 2 passes progressives avant les corrections extrêmes : `ApplyRugosityBias` + `ApplyAccumulationBias`
- [x] Connectivité hydrologique H3 v8 livrée dans `logic/` (composantes eau, exutoires, cuvettes, côtes)
- [x] `DedicatedServer/app/server.py` expose un bloc `hydrology` dans `/debug/generation-stats`
- [x] Suite qualité génération : **14/14 PASS** après enrichissement — zéro régression

---

## ✅ Sprint C — Persistance Régionale + Synchro Local → Projection (terminé 2026-04-19)

> Design de référence : [GDD.md §7](GDD.md) — Tuiles & Terrain (base technique pour Phase 7) | [SIMULATION_CONTRACTS.md](SIMULATION_CONTRACTS.md)

**Complété** :
- [x] `runtime.py` — `_region_mutations` cache en mémoire : `dict[region_key, dict[(q,r), (water_delta, temp_delta)]]`
- [x] `open_region()` — rejoue les mutations persistées sur les cellules après génération
- [x] `apply_direct_cell_delta()` — accumule les deltas dans `_region_mutations` par clé région
- [x] `bootstrap_sol()` — vide `_region_mutations` au reset
- [x] Unity : `ViewManager.SynchronizeRegionStateFromServer()` rappelle déjà `/commands/open-region` à chaque ouverture locale → recoit l'état persisté automatiquement
- [x] Socle technique prêt pour Phase 7 (claim territoire, bâtiments)

**Validé 2026-04-19** : waterRatio cell (3,-1) : 0.5977 → +0.3 delta → re-open : 0.8977 ✔️

**Écart connu (différé)** :
- Mutations non persistées sur disque (PostgresRepository) — survie session mémoire seulement ; persistance DB = Phase 7+

---

## ✅ Sprint E — Physique Stellaire & Modèle Atmosphérique Physique (terminé 2026-04-19)

> Design de référence : [GDD.md §5](GDD.md) — Les trois moteurs du jeu (moteur écologique) | [SIMULATION_CONTRACTS.md](SIMULATION_CONTRACTS.md)

**Complété** :
- [x] `models.py` — `AtmosphericGas`, `AtmosphericComposition`, `ATMOSPHERE_PRESETS` (earth/mars/venus/vacuum), `GlobalWindPattern`
- [x] `models.py` — `SphericalBodyState` enrichi : `atmosphere: AtmosphericComposition`, `equilibriumTemperature`, `globalWindPattern`, `luminosityLsun` ; propriété calculée `atmosphereDensity`
- [x] `models.py` — `GoldbergTileState` enrichi : 7 nouveaux champs physiques (`altitude`, `albedo`, `solarIrradiance`, `vegetationDensity`, `wildlifeDensity`, `atmosphereDeltaCo2`, `atmosphereDeltaO2`)
- [x] `logic.py` — chaîne thermique stellaire : `spectral_type_to_luminosity`, `compute_planetary_irradiance`, `compute_greenhouse_temp`, `compute_equilibrium_temperature`, `compute_tile_irradiance`, `compute_tile_albedo`, `aggregate_tile_deltas`
- [x] `logic.py` — `generate_spherical_tiles()` peuple `altitude`, `albedo`, `vegetationDensity` à la génération
- [x] `runtime.py` — boucle stellaire 2 passes (étoiles d'abord, puis planètes/lunes) pour `luminosityLsun` + `equilibriumTemperature` corrects
- [x] `runtime.py` — `get_body_atmosphere`, `patch_atmosphere`, `apply_tile_atmosphere_delta` ; `_register_spherical_body_locked` accepte `atmosphere: AtmosphericComposition | None`
- [x] `runtime.py` — `wipe_galaxy` délègue à `bootstrap_sol()` (fix : appelait l'ancien `_bootstrap_galaxy_locked`)
- [x] `DedicatedServer/app/server.py` — 3 endpoints : `GET /bodies/{id}/atmosphere`, `PATCH /bodies/{id}/atmosphere`, `POST /bodies/{id}/tiles/{tile_id}/atmosphere-delta`
- [x] `SimulationContracts.cs` — structs `AtmosphericGas`, `AtmosphericComposition`, `GlobalWindPattern` ; `GoldbergTileState` enrichi ; fix `Math.Min` (pas de `using UnityEngine`)
- [x] `Mcp/server.py` — `get_atmospheric_state(body_id)`, `patch_atmosphere(body_id, gas, fraction_delta)`, helper `_server_patch`

**Résultats validés** (Docker, 2026-04-19) :
- Sun: `L=1.0 L☉` | Earth: `Teq=−18.5°C`, 101.3 kPa (N₂/O₂/CO₂/CH₄/H₂O) | Kepler-442b: `Teq=13.5°C`
- Moons utilisent la distance AU de leur planète parente (fix: Io ne vaut plus 4000°C)
- Suite de qualité génération : **14/14 PASS** sur les 5 presets — zéro régression

**Écart connu (différé)** :
- `solarIrradiance` reste 0.0 sur toutes les tuiles à la génération — passe de recalcul post-bootstrap non encore implémentée ; `equilibriumTemperature` sur le corps est correct

---

## ✅ Sprint D — AtmosphericState : progression terraformation mesurable (terminé 2026-04-19)

> Design de référence : [GDD.md §5](GDD.md) — Les trois moteurs du jeu (moteur écologique) | [SIMULATION_CONTRACTS.md](SIMULATION_CONTRACTS.md)

**Complété** :
- [x] `AtmosphericState` Pydantic + C# : `co2Ratio`, `o2Ratio`, `atmosphericPressure`, `averageTemperature`, `toxinRatio`, `habitabilityScore`
- [x] `atmosphericState: AtmosphericState` dans `RegionState` (Python + C#)
- [x] `logic/simulation.py` — `compute_atmospheric_state(cells)` + `cell_habitability_score(cell)`
- [x] `runtime.py` — `region.atmosphericState` peuplé après `open_region()`
- [x] `/commands/open-region` retourne `atmosphericState` non vide (habitabilityScore = 0.9549 sur Terre)
- [x] `TerraformHUD.cs` — affiche O₂%, CO₂%, pression, temp, habitabilityScore
- [x] Slider utilise `habitabilityScore` en priorité via `SetAuthoritativeRegionState()`
- [x] MCP `get_atmospheric_state(body_id, latitude, longitude)` — dual-mode body/region

**Validé 2026-04-19** : `habitabilityScore = 0.9549` | `o2Ratio = 0.21` | `pressure = 18.187 kPa` | `avgTemp = 15.39°C`

---

## Sprints MCP — Responsabilité GitHub Copilot

> Design de référence : [MCP_TOOLS_ARCHITECTURE.md](MCP_TOOLS_ARCHITECTURE.md) — Architecture des tools, endpoints, état par tool

**GitHub Copilot est propriétaire du MCP et de l'API du jeu.**
Référence complète : [MCP_TOOLS_ARCHITECTURE.md](MCP_TOOLS_ARCHITECTURE.md)

### ✅ Sprint MCP-1 — Outils de cellule et validation (terminé 2026-04-19)

**Complété** :
- [x] `GET /debug/cell?q=&r=` → `get_cell_detail(q, r)` — état complet d'un hex par coordonnées axiales
- [x] `GET /debug/hydrology` → `get_hydrology_stats()` — distribution hydrologique de la région active
- [x] `GET /debug/validate` → `run_validation()` — validation de cohérence sans Unity (3 règles : ocean-low-water, frozen-too-warm, dry-high-water)
- [x] `runtime.py` : `get_region_cell`, `get_region_hydrology`, `get_region_validation` (thread-safe)
- [x] `Mcp/server.py` : 3 tools exposés dans la famille `simulation-server`
- [x] Documenté dans [MCP_TOOLS_ARCHITECTURE.md](MCP_TOOLS_ARCHITECTURE.md)

**Validé 2026-04-19** : cell(3,-1) waterRatio=0.598 | hydrology 24 cells | validate 2/24 issues détectées (dry-high-water réel)

### Sprint MCP-2 — Boucle de test automatisée (Sprint C → Phase 7)

**Implémenté** :
- [x] `set_projection(preset_name)` — switch serveur-only vers un preset nommé (coherence + water_level), sans Unity
- [x] `run_region_validation_suite(latitude, longitude)` — pipeline 5 presets : set-projection → open-region → hydrology + validate + atmospheric state + sample cell (0,0)
- [x] `Tools/Test-RegionValidation.ps1` — script CI : 5 presets, health check, table résultats, exit 0/1
- [x] Seuil `dry-high-water` corrigé de `> 0.40` à `> 0.45` (aligné sur la limite réelle de classification `Dry`)
- [x] Documenté dans [MCP_TOOLS_ARCHITECTURE.md](MCP_TOOLS_ARCHITECTURE.md)

**Validé 2026-04-19** : 5/5 presets PASS | Coast/Ocean/Arid/Frozen/Basin 24 cells chacun | 0 issue | pipeline server-only complet

### Sprint MCP-3 — API Gameplay (Phase 7 → 9)

**✅ terminé 2026-04-19**

- [x] `get_tick_state()` → `GET /tick/status`
- [x] `get_planet_overview(body_id)` → composite `/bodies/{id}` + tile distribution
- [x] `get_corporations_list()` → `GET /game/corporations`
- [x] `get_corporation_state(corporation_id)` → `GET /game/corporations/{id}`
- [x] `create_corporation(name, is_ai)` → `POST /game/corporations` (admin MCP)
- [x] Règle respectée : les writes gameplay (claim) passent par Mirror, jamais par cette API
- [x] `get_market_state` — différé Phase 7.3 (marché dynamique inexistant)
- [ ] `get_active_events` — différé Phase 7.4 (contrats/événements inexistants)

---

## Ordre d'exécution conseillé

- [x] Ne pas démarrer la Phase 7 avant la fin du Sprint C et du Sprint D ✅ (2026-04-19)
- [x] Considérer la Phase 6.5 comme terminée seulement quand les critères de sortie des sprints A et B sont validés ✅ (2026-04-19)
- [x] Utiliser le Sprint C comme sas de stabilisation avant `Corporation`, `Events` et `Economy` ✅ (2026-04-19)

> **→ Phase 7 débloquée.**

---

## Phase 7 — Gameplay Corporation v1

**Prérequis** : Sprint C (persistance régionale) + Sprint D (AtmosphericState) terminés. Phase 6.9 (hiérarchie Cosmos) ✅

> Design de référence : [Description_du_jeu.md §10-15](description_jeu/Description_du_jeu.md) — Corporations, États, Marchés, Contrats, Contrôle de tuiles

### Phase 7.1 — Propriété de tuile

**✅ terminé 2026-04-19**

- [x] Créer `CorporationData` + `ClaimedTile` côté Python `SimulationCore` + contrat C# miroir
- [x] `CorporationRegistry` in-memory dans `InMemorySimulationRuntime` (`_corporations`, `_tile_ownership`)
- [x] `POST /game/corporations` — créer une corpo (admin/MCP)
- [x] `GET /game/corporations` — lister toutes les corpos
- [x] `GET /game/corporations/{id}` — détail d'une corpo
- [x] `POST /game/corporations/{id}/claim-hex?body_id=&tile_id=` — claim un hex libre (409 si déjà pris)
- [x] `bootstrap_sol()` vide `_corporations` et `_tile_ownership`
- [x] `GetBoundaryLoops()` rewrite (Goldberg edge-map) + `OwnershipBorderRenderer.cs` — LineRenderers colorés par corpo sur globe
- [x] `GameHUD.cs` (~650 lignes) — HUD code-driven unifié : TopBar, LeftPanel (progression), RightPanel (inspecteur tuile + Claim/Unclaim + badge corpo)
- [x] `TerraformHUD.cs` — events `OnProgressUpdated` + `OnRegionStateChanged` ; `ViewManager.GoBackOneLevel()` public
- [x] Fix bug `OnH3TileResolved` (FindObjectsInactive + suppression check PlanetSubView) + clic globe centroïde hover

**Commits** : `2664364`, `40da8c4`, `fad0973`, `ec65103`, `03e6a49`, `898f274`

**Résultat validé en Play Mode :**
> Clic tuile → RightPanel Claim/Unclaim ✓ | Tuile claimée → badge + nom corpo ✓ | Bordures ownership sur globe ✓ | Hover et clic cohérents ✓

### Phase 7.2 — Bâtiments v1 (modèle entrée → sortie)

> Design de référence : [GDD.md §11](GDD.md) — Bâtiments & Production

- [x] **B1** — `SimulationCore/terraformation_sim/models.py` : `BuildingType` enum, `ResourceType` enum, `BuildingData` Pydantic, `BUILDING_CONFIGS`, `CorporationData` enrichi (liste bâtiments + stocks)
- [x] **B2** — `SimulationCore/terraformation_sim/runtime.py` : `construct_building()`, `demolish_building()`, `_process_building_production()` dans `tick_loop`
- [x] **B3** — `DedicatedServer/app/server.py` : `POST /game/corporations/{id}/buildings`, `GET /game/corporations/{id}/buildings`, `DELETE /game/corporations/{id}/buildings/{building_id}`, `PATCH /game/corporations/{id}/buildings/{building_id}/workers`
- [x] **B4** — `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` : `CorpBuildingType` enum + `CorpBuilding` struct miroir (renommés pour éviter conflit Economy/BuildingData)
- [x] **B5** — `Game/Assets/Scripts/UI/GameHUD.cs` : section Bâtiments dans RightPanel (visible si tuile claimée par la corpo locale)
- [x] **B5.1** — `Game/Assets/Scripts/UI/GameHUDBuildingIcons.cs` + `Assets/Resources/Fonts/Font Awesome 7 Free-Solid-900.otf` : couche d'icônes UI des bâtiments avec mapping `CorpBuildingType -> icon token`, preview dans le RightPanel, rendu Font Awesome si disponible et fallback texte sinon

### ✅ Phase 7.3 — Marché local v1 (terminé 2026-04-21)

> Design de référence : [Description_du_jeu.md §12](description_jeu/Description_du_jeu.md) — Marchés | [questions/marche_local.md](description_jeu/questions/marche_local.md)

- [x] `SocialClass` (Poor/Middle/Rich) + `PopulationTier` + besoins différenciés par classe (`_DEMAND_PER_PERSON`)
- [x] `compute_market_prices()` avec offre/demande par tick, élasticité, prix min/max (`logic/market.py`)
- [x] `apply_social_mobility()` — mobilité entre classes selon taux d'emploi
- [x] `taxRate` propagé depuis `StateData` vers `LocalMarketState` (`_resolve_tax_rate_locked`)
- [x] `_process_market_tick_locked()` dans `runtime.py` — mise à jour des marchés à chaque tick
- [x] `GET /game/market` + `GET /game/market/{corp_id}` dans `server.py`
- [x] MCP `get_market_state(corp_id)` + MCP `get_global_market()` (Phase 9.5)
- [x] `_marketPanel` dans `GameHUD.cs` — prix + tendance + population par classe
- [x] **7 tests** dans `test_phase73_market.py` — tous passants

**Écart différé** : propagation hiérarchique des prix (tuile → planète → système) — Phase 9.5 global market

### ✅ Phase 7.4 — Contrats v1 (terminé 2026-04-21)

> Design de référence : [Description_du_jeu.md §13](description_jeu/Description_du_jeu.md) — Contrats | [questions/contrats.md](description_jeu/questions/contrats.md)

- [x] `ContractData` Pydantic + C# miroir (`SimulationContracts.cs`)
- [x] Visibilité `Public` (enchère avec fenêtre de bid) et `Private` (bilatéral direct)
- [x] Durée fixe (`durationTicks`) et open-ended (`durationTicks=0`), rupture avec `penaltyCredits`
- [x] `knowledgeBonus` crédité à l'accepteur à la complétion
- [x] `_process_contract_tick_locked()` — auto-livraison, complétion, expiration, pénalités
- [x] `GET/POST /game/contracts`, `POST /game/contracts/{id}/accept|bid|confirm|break`
- [x] MCP `propose_contract`, `list_contracts`, `list_public_contracts`, `accept_contract`, `bid_on_contract`, `confirm_bidder`, `break_contract`
- [x] `_contractPanel` dans `GameHUD.cs` — liste + boutons Accept/Bid/Break
- [x] **12 tests** dans `test_phase74_contracts.py` — tous passants

**Écart différé** : types non-livraison (contrôle territorial, exploration, présence militaire) — différé Phase 8+

### ✅ Phase 7.5 — Réputation, États et nationalisation (terminé 2026-04-21)

> Design de référence : [Description_du_jeu.md §11](description_jeu/Description_du_jeu.md) — États | [questions/perte_de_controle_tuile.md](description_jeu/questions/perte_de_controle_tuile.md)

- [x] `globalReputation` dans `CorporationData` + `_reputations: dict[tuple, float]` bilatéral dans runtime
- [x] `StateData` : `toleranceThreshold`, `bureaucracy`, `corruptionRate`, `taxRate`, `StateType` enum
- [x] `NationalizationProcess` avec délai = bureaucratie + corruption
- [x] Fenêtre de réaction : `POST /game/nationalizations/{id}/corrupt` + `POST .../cancel-contract`
- [x] `GET /game/states`, `GET /game/reputation/{source}/{target}`, `GET /game/scoreboard`
- [x] `ScoreboardEntry` + `GET /game/scoreboard`
- [x] MCP `create_state`, `list_states`, `get_reputation`, `list_reputations`, `list_nationalizations`, `get_scoreboard`
- [x] `_nationalizationPanel` + `_scoreboardPanel` dans `GameHUD.cs`
- [x] **11 tests** dans `test_phase75_states.py` — tous passants

**Résultat** : une corpo joueur peut claim des hexes, construire des mines, signer des contrats avec les États, être nationalisée, monter au classement. `habitabilityScore` est le KPI environnemental commun.

---

## ✅ Phase 8 — Système d'Événements (terminé 2026-04-21)

> Design de référence : [Description_du_jeu.md §16](description_jeu/Description_du_jeu.md) — Événements

- [x] `EventData` : nom, description, `EventEffect`, poids de probabilité, déclencheur tick
- [x] `EventType` : RencontreAlienne, TempêteSolaire, DécouverteMinière, CriseÉconomique, SabotageCorpo, Rébellion, MigrationPopulation, DecouverteMegastructure, EmpireGalactique
- [x] `_process_event_tick_locked()` — tirage pondéré à chaque tick serveur
- [x] `_game_events: list[EventData]` en mémoire dans runtime
- [x] **8 tests** dans `test_phase8_events.py` — tous passants

**Écarts fermés** :
- [x] Popup UI de notification Unity — ✅ 2026-04-21 (`_eventPopupPanel` + `ShowEventPopup()` dans `GameHUD.cs`)
- [x] Endpoint REST `/game/events` pour exposer le log — ✅ 2026-04-21 (`GET /game/events`, MCP `list_game_events`)

---

## ✅ Phase 8.5 — Agents LLM & Game Master (terminé 2026-04-21)

> Design de référence : [Description_du_jeu.md §17](description_jeu/Description_du_jeu.md) — IA & Agents LLM | [questions/ia_modele_langage.md](description_jeu/questions/ia_modele_langage.md)

- [x] `AgentAction`, `AgentMemory`, `AgentActionType` modèles Pydantic
- [x] `AgentMemory` par entité dans runtime (`_agent_memories`)
- [x] Logique agent pure : `logic/agent.py` (décision, scoring, priorités)
- [x] **11 tests** dans `test_phase85_agent_logic.py` + **5 tests** `test_phase85_agent_models.py`
- [x] Tests `agent_behavior`, `agent_scenarios`, `agent_benchmark` (marqués `scenario/llm`)
- [x] **GM (Phase 11.3)** — `_gm_cooldown_tick` + `_gm_last_lever` ; **25 tests** dans `test_phase113_gm.py`

**Écarts** :
- Intégration LLM live — tests marqués `@llm`, modèles validés (gemma4 FAST + Qwen2.5-14B DEEP, 29/30 benchmark)
- [x] Endpoints agent — ✅ 2026-04-21 (`GET /game/agent/context/{state_id}`, `POST /game/agent/run/{state_id}`, MCP `get_agent_context` + `run_agent_for_state`)

---

## ✅ Phase 9 — Économie avancée & Routes commerciales (terminé 2026-04-21)

> Design de référence : [Description_du_jeu.md §12](description_jeu/Description_du_jeu.md) — Marchés, Routes commerciales

### Phase 9 core — Modèles & Routes
- [x] `TradeRoute`, `TradeRouteType`, `TradeRouteActivityStatus` modèles + `_trade_routes` dans runtime
- [x] `ExpeditionUnit`, `ExpeditionStatus` + `_expeditions` dans runtime
- [x] `GET/POST /travel`, `POST /travel/{id}/cancel` ; MCP `initiate_travel`, `list_active_travels`, `cancel_travel`
- [x] **12 tests** dans `test_phase9_models.py` + `test_phase9_runtime.py`

### Phase 9.4 — Vélocité des prix
- [x] `priceVelocity` + `priceHistory` (10 entrées) dans `ResourceListing`
- [x] `compute_market_prices()` peuple velocity + history à chaque tick
- [x] **4 tests** dans `test_phase94_market.py`

---

## ⏳ Phase Rébellion — Perte de tuile par insatisfaction pop (non démarré)

> Design de référence : [Description_du_jeu.md §15](description_jeu/Description_du_jeu.md) — Contrôle et perte de tuiles

- [ ] `satisfactionScore` (float 0–1) calculé par tuile en fin de tick (besoins pop vs ressources disponibles)
- [ ] Seuil configurable (`rebellion_threshold`, défaut : 0.25) dans les constantes de simulation
- [ ] Si `satisfactionScore < rebellion_threshold` pendant N ticks consécutifs → déclenche `EventType.Rébellion`
- [ ] Perte de contrôle : tuile repasse à `controlledBy = None`, corporation perd la tuile
- [ ] Pénalité réputation pour la corporation (−réputation dans l'État concerné)
- [ ] **6+ tests** dans `test_phase_rebellion.py`

**Assertion script** : `SimulationCore/tests/assertions/test_p_rebellion.py` (à créer lors de l'implémentation)

---

## ⏳ Phase Réseau énergétique — Distribution énergie entre tuiles (non démarré)

> Design de référence : [Description_du_jeu.md §9](description_jeu/Description_du_jeu.md) — Bâtiments

- [ ] `EnergySegment` modèle — `fromTileId`, `toTileId`, `capacityKw`, `currentLoadKw`
- [ ] `_energy_segments` dans runtime — segments créés à la construction d'un bâtiment réseau
- [ ] Centrale produit X énergie → distribuée aux tuiles adjacentes via segments (capacité max par segment)
- [ ] Énergie disponible sur le marché local de chaque tuile connectée
- [ ] Saturation segment → pénurie sur les tuiles en bout de chaîne
- [ ] **6+ tests** dans `test_phase_energy_grid.py`

---

## ⏳ Phase Déchets — Accumulation et impact écologique (non démarré)

> Design de référence : [Description_du_jeu.md §9](description_jeu/Description_du_jeu.md) — Bâtiments

- [ ] `wasteAccumulated` (float) sur `ClaimedTile` — s'incrémente à chaque tick par les bâtiments producteurs
- [ ] Mine, Centrale → génèrent `Waste` sur le marché local + `wasteAccumulated` sur la tuile
- [ ] Sans bâtiment de traitement : `wasteAccumulated > seuil` → malus `habitabilityScore` + malus biodiversité
- [ ] `WasteTreatmentPlant` — bâtiment de traitement : consomme `Waste` du marché, réduit `wasteAccumulated`
- [ ] **6+ tests** dans `test_phase_waste.py`

---

## ⏳ Phase Épuisement & Reconversion — Ressource épuisée (non démarré)

> Design de référence : [Description_du_jeu.md §9](description_jeu/Description_du_jeu.md) — Bâtiments

- [ ] `resourceReserve` (float) par tuile pour les ressources extractibles (minerals, iron…)
- [ ] Mine : réduit `resourceReserve` à chaque tick ; à 0 → `BuildingData.status = depleted`
- [ ] Bâtiment `depleted` → ne produit plus, émet un `EventType` d'épuisement
- [ ] Action de reconversion : remplacer un bâtiment déplété par un autre (coût réduit vs construction neuve)
- [ ] **6+ tests** dans `test_phase_depletion.py`

---

## ⏳ Phase Corruption — Stat État exploitable (non démarré)

> Design de référence : [Description_du_jeu.md §12](description_jeu/Description_du_jeu.md) — États & Gouvernements

- [ ] `corruptionLevel` (float 0–1) sur `StateData`
- [ ] Corruption passive : réduit l'efficacité des bâtiments d'État et la qualité des contrats proposés
- [ ] Action corpo `CorruptState` : dépense crédits → augmente `corruptionLevel` de l'État cible
- [ ] Effets : réduction taxes, délai nationalisation multiplié, avantages contrats, seuil tolérance relevé
- [ ] **6+ tests** dans `test_phase_corruption.py`

---

## ⏳ Phase Bureaucratie — Délai décisions État (non démarré)

> Design de référence : [Description_du_jeu.md §12](description_jeu/Description_du_jeu.md) — États & Gouvernements

- [ ] `bureaucracyLevel` (float 0–1) sur `StateData`
- [ ] Toute décision d'État (nationalisation, proposition contrat, bannissement corpo) a un délai = `base_ticks × (1 + bureaucracyLevel)`
- [ ] File de décisions d'État `_state_decision_queue` avec `ticksRemaining` par décision
- [ ] Corruption réductrice : `corruptionLevel` élevé → réduit le `bureaucracyLevel` effectif
- [ ] **6+ tests** dans `test_phase_bureaucracy.py`

---

## ⏳ Phase Migrations — Flux de population entre tuiles (non démarré)

> Design de référence : [Description_du_jeu.md §13](description_jeu/Description_du_jeu.md) — Marchés

- [ ] **Porosité naturelle** : micro-flux passif entre tuiles limitrophes à chaque tick (proportion configurable)
- [ ] **Migration économique** : flux dirigé amplifié par l'écart `attractiveness` (emploi, salaires, ressources)
- [ ] `attractiveness` calculé par tuile en fin de tick : `workerRatio × avgIncome × habitabilityScore`
- [ ] Routes commerciales actives → amplifient le flux migratoire entre tuiles connectées
- [ ] **6+ tests** dans `test_phase_migration.py`

---

## ⏳ Phase Mobilité sociale — Évolution des classes (non démarré)

> Design de référence : [Description_du_jeu.md §13](description_jeu/Description_du_jeu.md) — Marchés

- [ ] `avgIncome` par `SocialClass` sur chaque tuile, mis à jour à chaque tick selon `workerRatio`
- [ ] Seuils de promotion : `Poor → Middle` si `avgIncome > seuil_pm` pendant N ticks consécutifs ; `Middle → Rich` idem
- [ ] Seuils de régression : `Middle → Poor` si `avgIncome < seuil_mp` pendant N ticks
- [ ] Migration des classes : la population promue peut migrer vers des tuiles correspondant à son niveau
- [ ] **6+ tests** dans `test_phase_social_mobility.py`

---

## ⏳ Phase Événements en trajet — Incidents sur ExpeditionUnit (non démarré)

> Design de référence : [Description_du_jeu.md §16](description_jeu/Description_du_jeu.md) — Voyages interplanétaires

- [ ] À chaque tick, chaque `ExpeditionUnit` active a ~3% de probabilité de déclencher un incident
- [ ] Types : `Piracy` (perte partielle cargo), `Breakdown` (`ticksRemaining += X`), `Discovery` (ressources bonus à l'arrivée)
- [ ] Incidents stockés comme `EventData` dans le log d'événements de la simulation
- [ ] Notification MCP `list_game_events` inclut les incidents de trajet
- [ ] **6+ tests** dans `test_phase_travel_events.py`

---

## ⏳ Phase Leaderboard — Classement corporations (non démarré)

> Design de référence : [Description_du_jeu.md §19](description_jeu/Description_du_jeu.md) — Multijoueur

- [ ] `leaderboardScore` calculé à chaque tick : `credits + (claimedTiles × 100) + (globalReputation × 50)`
- [ ] `GET /game/leaderboard` — top 10 corporations triées par score, rafraîchi chaque tick
- [ ] MCP tool `get_scoreboard` expose le classement aux agents LLM
- [ ] Stocké en mémoire (pas de persistance requise — calculé à la volée)
- [ ] **4+ tests** dans `test_phase_leaderboard.py`


### Phase 9.5 — Marché global & ressources avancées
- [x] `ResourceType` étendu : Iron, Oxygen, Water, Tech (Phase 9.5)
- [x] `GlobalMarketState` + `compute_global_market()` — agrégation weighted-average par système
- [x] `GET /game/global-market` (via `get_global_market()`); MCP `get_global_market`
- [x] **4 tests** `test_phase95_global_market.py` + **4 tests** `test_phase95_resources.py`

### Phase 9.6 — Emploi, revenus, expéditions avancées
- [x] `employmentSlots` dans `BuildingData` + `EMPLOYMENT_CONFIGS` par `SocialClass`
- [x] `avgIncome` comme multiplicateur de demande ; `_INCOME_DEFAULTS` par classe
- [x] Cargo sur `ExpeditionUnit` + livraison de ressources en transit
- [x] **6 tests** `test_phase96_employment.py` + **6 tests** `test_phase96_income.py` + **6 tests** `test_phase96_expeditions.py`

**Écarts différés** :
- Routes spatiales inter-planètes liées au Spaceport (building existe, logique de voyage non branchée)
- Organisme inter-étatique (marché global corruptible) — non implémenté

---

## ✅ Phase 10.5 — File de construction par territoire (terminé 2026-04-21)

- [x] `ConstructionItem`, `ConstructionStatus`, `TerritoryQueue` modèles
- [x] `_construction_queues: dict[str, TerritoryQueue]` dans runtime
- [x] Accumulation de points de construction par tick (EB Fortune → `constructionCapacity`)
- [x] `isEBDeFortune` — spawn automatique d'un EB quand territoire sans EB actif
- [x] **16 tests** dans `test_phase105_construction.py` — tous passants

---

## ✅ Phase 10 — Multijoueur Réseau (terminé 2026-04-21)

> Design de référence : [Description_du_jeu.md §18](description_jeu/Description_du_jeu.md) — Multijoueur

> **Complété** — voir [CHANGELOG.md §Phase 10](CHANGELOG.md) pour le détail.

- [x] Authentification joueur JWT (HS256, bcrypt) — `/auth/register`, `/auth/login`, `/auth/link-corp`
- [x] Table `players` PostgreSQL + stubs InMemoryRepository
- [x] WebSocket push FastAPI `GET /game/ws/events?token=JWT` — broadcast tick aux clients
- [x] `PlayerSession.cs` (singleton) + `LoginPanel.cs` + `SimulationWebSocketClient.cs` (NativeWebSocket, reconnexion auto)
- [x] `TickManager.cs` + `GameHUD.cs` — events via WS push, polling HTTP en fallback
- [x] Colonisation caravane — `ExpeditionUnit` Land → arrivée → `ClaimedTile` créée avec pop
- [x] 3 tests `test_phase10_caravane.py` — tous passants

**Prochaine étape** : Auth Unity Authentication + PostgreSQL multi-instance (voir Phase 10 ext. backlog)

---

## ✅ Phase 11.2 — IA Corporations FSM (terminé 2026-04-21)

> Design de référence : [Description_du_jeu.md §17](description_jeu/Description_du_jeu.md) — IA

- [x] `CorpProfile` enum : Expansionniste, Économiste, Militariste
- [x] `BotFSMState` : Idle, Expanding, Building, Trading, Defending
- [x] `fsmState` + `fsmThresholds` dans `CorporationData`
- [x] `_process_bot_corporations_locked()` — une décision FSM par tick par corpo IA
- [x] `AgentActionType` : ClaimTile, ConstructBuilding, UpdateFsmThresholds, ReorderConstructionQueue
- [x] **20 tests** dans `test_phase112_corp_fsm.py` + **20 tests** `test_phase112_llm_corp.py`

---

## ✅ Phase 11.3 — Game Master narratif (terminé 2026-04-21)

- [x] `_gm_cooldown_tick` + `_gm_last_lever` dans runtime
- [x] Leviers GM : ajustement prix, déclenchement événement, boost réputation, accélération nationalisation
- [x] Cooldown configurable + logique de scoring par levier
- [x] **25 tests** dans `test_phase113_gm.py` — tous passants

---

## ✅ Phase 11.5 — Biodiversité par espèce (terminé 2026-04-21)

> Design de référence : [Description_du_jeu.md §Écologie](description_jeu/Description_du_jeu.md)

- [x] **M1** — Modèle `SpeciesData` (Python + C# `SimulationContracts.cs`)
- [x] **M2** — Logique pure `SimulationCore/terraformation_sim/logic/ecology.py` (4 fonctions)
- [x] **M3** — `_process_ecology_tick_locked()` dans `runtime.py` (intégré au tick)
- [x] **M4** — Endpoint REST `GET /bodies/{id}/tiles/{tile_id}/ecology` + MCP tool `get_tile_ecology` + section Écologie dans `GameHUD`
- [x] **18 tests** dans `test_phase115_ecology.py` — tous passants

---

## Phase 11 — IA Corporations (remplacé par 11.2 + 11.3 ci-dessus)

> Toutes les fonctionnalités IA Corporations sont implémentées dans les phases 11.2 et 11.3 ci-dessus.

---

## ✅ Sprint DB — Persistence complète des entités gameplay (2026-04-21)

> Voir détail complet dans [CHANGELOG.md](CHANGELOG.md)

- [x] `persistence.py` — 9 nouvelles tables + 30 méthodes ABC + implémentations `PostgresRepository`
- [x] `runtime.py` — write-through sur toutes les mutations gameplay + flush 10-ticks corps/marchés/expéditions
- [x] `runtime.py` / `_hydrate_from_saved()` — restauration complète des 9 collections au démarrage
- [x] `bootstrap_sol()` — wipe DB des 9 entités
- [x] `test_phase_sprint_db.py` — 5 tests, 41 passed, 0 failed
- [x] `test_phase12_building_level.py` — 12 tests, `upgrade_building` / `downgrade_building`, level clamp [1–5]
- [x] **Assertion script** : `SimulationCore/tests/assertions/test_p12_sprint_db.py`

---

## ✅ Phase Colonisation Initiale Terre — Partition territoriale + population bootstrap

> Design de référence : [Description_du_jeu.md §colonisation](description_jeu/Description_du_jeu.md)

**Objectif** : au premier `bootstrap_sol()`, toutes les tuiles terrestres d'Earth sont partitionnées en territoires appartenant à 7 États-nations continentaux avec une population seedée.

### Critères de sortie

- [x] `TerritoryData` + `StateProfile` + `STATE_PROFILES` dans `models.py`
- [x] `StateData` enrichi : `territoryIds`, `literacyRate`, `profileKey`
- [x] `logic/colonization.py` : `build_territories_from_tiles`, `is_terrestrial_tile`, `seed_tile_population`, `tile_population_factor`, `assign_tile_to_continent`
- [x] Multiplicateurs terrain/eau : Vegetation×1.5, Coast×1.5, Roche×0.5, OpenOcean=0, Glace=0
- [x] Distribution population 40% Poor / 59% Middle / 1% Rich (via `PopDistribution` injectable, jamais hardcoded)
- [x] 5 profils `STATE_PROFILES` : Standard, RicheUtopique (1/98/1), EnDeveloppement, Pauvre, Autoritaire
- [x] 7 zones continentales : NordAmérique, SudAmérique, Europe, Afrique, MoyenOrient, Asie, Océanie
- [x] BFS flood-fill pour garantir la contiguïté des territoires
- [x] `persistence.py` : table `territories`, ABC + InMemory + PostgresRepository
- [x] `runtime.py` : `_territories`, `_territory_tile_index`, `_bootstrap_earth_colonization_locked()`, `list_territories()`, `get_territory()`, `get_tile_territory()`
- [x] Hydratation `_territories` dans `_hydrate_from_saved()`
- [x] `DedicatedServer/app/server.py` : `GET /game/territories` + `GET /game/territories/{id}`
- [x] `Mcp/server.py` : `list_territories()` + `get_territory()`
- [x] `SimulationContracts.cs` : `TerritoryData`, `PopDistribution`, `SimStateData` enrichi
- [x] `test_phase_earth_colonization.py` — 9 tests (T01–T08) + `test_p_colonisation_terre.py` assertion

### Fichiers modifiés

| Fichier | Changement |
|---------|------------|
| `SimulationCore/terraformation_sim/models.py` | `PopDistribution`, `StateProfile`, `STATE_PROFILES`, `TerritoryData`, `StateData` enrichi |
| `SimulationCore/terraformation_sim/logic/colonization.py` | Nouveau fichier — 7 fonctions pures |
| `SimulationCore/terraformation_sim/logic/__init__.py` | Exports colonisation |
| `SimulationCore/terraformation_sim/persistence.py` | Table `territories`, ABC, InMemory, PostgresRepository |
| `SimulationCore/terraformation_sim/runtime.py` | Registres, bootstrap, hydrate, méthodes publiques |
| `DedicatedServer/app/server.py` | 2 nouveaux endpoints |
| `Mcp/server.py` | 2 nouveaux tools |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | `TerritoryData`, `PopDistribution`, `SimStateData` enrichi |
| `SimulationCore/tests/test_phase_earth_colonization.py` | 8 tests (T01–T08) |
| `SimulationCore/tests/assertions/test_p_colonisation_terre.py` | Assertion script |

---

## Phase 12 — Polish

### ✅ Sprint UI (2026-04-21)

- [x] **P1** — Tick counter + solde crédits dans le TopBar — `_tickCreditsLabel` TMP inséré entre `_planetLabel` et `_toggleViewBtn` ; `PollTickStatus()` coroutine (10s, `GET /tick/status`) ; `UpdateTickCreditsLabel()` affiche `Tick N` ou `Tick N | X cr` ; `RefreshCorpListForTile()` capture `credits` depuis la corpo propriétaire — ✅ 2026-04-21
- [x] **P2** — Noms des `EventType` en français dans la popup d'événement — `LocalizeEventType(EventType t)` switch-expression 9 valeurs FR ; `PollEventFeed()` remplace `{ev0.eventType}` par `{LocalizeEventType(ev0.eventType)}` — ✅ 2026-04-21

### Backlog Polish (non démarré)

- [x] **P3** — Équilibrage économique v1 — 8 constantes ajustées (`credits` départ 1000→5000, `Mine` 60→50pts, `Farm` 45→40pts, `EB_FORTUNE_CAPACITY` 5→10, `_PRICE_MAX` 10→50, `BASE_NATIONALIZATION_DELAY` 10→20, `CREDIT_SCALE` 10k→50k, `BRIBE_COST_PER_TICK` 50→100) — 172 tests passants — ✅ 2026-04-22
- [x] **P4** — Tooltips flottants HUD — `GameHUDBuildingIcons.cs` : `TooltipText` par type de bâtiment (Mine/Farm/EnergyPlant/Research) ; `GameHUD.cs` : `TooltipTrigger` nested class (`IPointerEnter/Exit/MoveHandler`), `BuildTooltipPanel()`, `ShowTooltip/HideTooltip/RepositionTooltip` avec clamp écran, `AddTooltipTrigger()` câblé sur lignes de bâtiments + boutons Rompre/Corrompre — ✅ 2026-04-22
- [x] UI/UX complet : menus, écrans de résumé
- [ ] Sound design
- [ ] Optimisation performances (profiler Unity)
- [ ] Distribution (itch.io ou autre)

---

## ⚠️ Dettes Techniques — Audit 2026-04-26

> Dérives identifiées lors de l'audit cross-projet du 2026-04-26. À traiter avant la Phase 13 (Mirror Networking).

### A — Contrats C# manquants dans `SimulationContracts.cs`

Modèles Python existants sans miroir C# dans `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` :

- [ ] `TradeRoute`, `SpaceTravel`, `ExpeditionUnit` (Phase 9) — utilisés dans `GET /travel` mais non désérialisables côté Unity
- [ ] `GlobalMarketState` (Phase 9.5) — endpoint `/game/global-market` sans réception Unity
- [ ] `AgentAction`, `AgentMemory`, `AgentActionType` (Phase 8.5) — agent LLM sans surface Unity
- [ ] `CorpProfile`, `BotFSMState` (Phase 11.2) — FSM corpo sans miroir C#

### B — Endpoints DedicatedServer manquants

Endpoints présents dans `Mcp/server.py` ou consommés par Unity, absents de `DedicatedServer/app/server.py` :

- [ ] `GET /game/territories` et `GET /game/territories/{id}` — existent via MCP mais non exposés en REST direct
- [ ] `WebSocket /game/ws/events` — Phase 10 marquée ✅ mais endpoint WS absent du serveur dédié ; `NativeWebSocket` Unity ne peut pas se connecter

### C — Bug Unity : port WebSocket incorrect

- [ ] `Game/Assets/Scripts/Networking/SimulationWebSocketClient.cs` : `simulationServerUrl = "http://localhost:8001"` → `"http://localhost:8080"` (port 8001 = Roadmap service, pas DedicatedServer)

### D — Dérives simulation runtime

- [ ] Passe `solarIrradiance` post-bootstrap manquante — les tuiles `solarIrradiance` ne sont pas recalculées après `bootstrap_sol` ; valeurs stale si la star change
- [ ] `_region_mutations` non persistées en DB — les mutations de région disparaissent au redémarrage serveur ; nécessite une table ou colonne dédiée dans `persistence.py`

### E — Scripts d'assertions manquants

Phases `done` sans `assertionScript` lié dans `roadmap.json` :

- [ ] Créer `SimulationCore/tests/assertions/test_p8_events.py` (Phase 8)
- [ ] Créer `SimulationCore/tests/assertions/test_p10_multiplayer.py` (Phase 10)
- [ ] Créer `SimulationCore/tests/assertions/test_p113_gm.py` (Phase 11.3)
- [ ] Créer `SimulationCore/tests/assertions/test_p115_ecology.py` (Phase 11.5)
- [ ] Créer `SimulationCore/tests/assertions/test_p94_prices.py` (Phase 9.4)

### F — Documentation MCP tools debug

- [ ] Documenter dans `Documentation/MCP_TOOLS_ARCHITECTURE.md` les 5 tools debug récents non référencés : `debug_generation_stats`, `debug_noise_distribution`, `compare_generation_profiles`, `compare_presets`, `run_body_tile_checks`

---

## Récapitulatif

| Phase | Contenu | Statut |
|---|---|---|
| 0–6.9, Sprint 0 | Fondations, grille, génération, vues, terraformation, cosmos, split sim | ✅ Voir [CHANGELOG.md](CHANGELOG.md) |
| 6.75 | Isolation bridge Unity | ✅ Voir [CHANGELOG.md](CHANGELOG.md) |
| 6.5 + Sprints A→D | Hydrologie, cohérence, persistance, AtmosphericState | ✅ Terminé 2026-04-19 |
| MCP-1, 2, 3 | Outils cellule, tests auto, API gameplay | ✅ Terminé 2026-04-19 |
| 7.1 | Propriété de tuile + Ownership UI | ✅ Terminé 2026-04-19 |
| 7.2 | Bâtiments v1 | ✅ Terminé 2026-04-19 |
| 7.3 | Marché local v1 (social classes, offre/demande, mobilité, taxe État) | ✅ Terminé 2026-04-21 |
| 7.4 | Contrats v1 (public/privé, enchère, pénalités, knowledgeBonus) | ✅ Terminé 2026-04-21 |
| 7.5 | Réputation, États, Nationalisation, Scoreboard | ✅ Terminé 2026-04-21 |
| 8 | Événements de base + popup Unity + endpoint `/game/events` | ✅ Terminé 2026-04-21 |
| 8.5 | Agents LLM + GM narratif + endpoints agent context/run | ✅ Terminé 2026-04-21 |
| 9 | Routes commerciales, Expéditions, Vélocité prix | ✅ Terminé 2026-04-21 |
| 9.4 | Vélocité & historique des prix | ✅ Terminé 2026-04-21 |
| 9.5 | Marché global + ressources avancées (Iron/O₂/Water/Tech) | ✅ Terminé 2026-04-21 |
| 9.6 | Emploi, revenus, cargo expéditions | ✅ Terminé 2026-04-21 |
| 10 | Multijoueur Réseau (WebSocket JWT + NativeWebSocket Unity) | ✅ Terminé 2026-04-21 |}
| 10.5 | File de construction par territoire (EB Fortune, TerritoryQueue) | ✅ Terminé 2026-04-21 |
| 11.2 | IA Corporations FSM (3 profils, 5 états) | ✅ Terminé 2026-04-21 |
| 11.3 | Game Master narratif (leviers, cooldown) | ✅ Terminé 2026-04-21 |
| 11.5 | Biodiversité par espèce | ✅ Terminé 2026-04-21 |
| 12 Polish P1+P2 | Tick counter TopBar + EventType FR popup | ✅ Terminé 2026-04-21 |
| 12 Polish P3+P4 | Équilibrage économique v1 (8 constantes) + Tooltips flottants HUD | ✅ Terminé 2026-04-22 |
| Sprint DB | Persistence complète des 9 entités gameplay (PostgreSQL write-through + hydratation) | ✅ Terminé 2026-04-21 |
| **Colonisation Initiale Terre** | **Partition territoriale Earth + 7 nations + population bootstrap (PopDistribution injectable)** | **✅ Terminé 2026-04-25** |
| 12 Polish suite | Menus, sound, perf, distribution | ⬜ Continu |
| Rébellion | SatisfactionScore tuile → EventType.Rébellion → perte contrôle | ⬜ Non démarré |
| Réseau énergétique | Segments entre tuiles, capacité, marché local énergie | ⬜ Non démarré |
| Déchets | Accumulation par tick, impact écologique, bâtiment de traitement | ⬜ Non démarré |
| Épuisement & reconversion | Ressource épuisée → reconversion bâtiment | ⬜ Non démarré |
| Corruption | Stat État exploitable : taxes, nationalisation, délais | ⬜ Non démarré |
| Bureaucratie | Délai décisions État = base × (1 + %) | ⬜ Non démarré |
| Migrations | Porosité naturelle + flux économique entre tuiles | ⬜ Non démarré |
| Mobilité sociale | Poor → Middle → Rich selon avgIncome sur N ticks | ⬜ Non démarré |
| Événements en trajet | Piraterie/panne/découverte ~3%/tick sur ExpeditionUnit | ⬜ Non démarré |
| Leaderboard | score = credits + tiles×100 + rep×50, top 10 par tick | ⬜ Non démarré |
| Fine-tuning GM narratif | LoRA sur Qwen3-8B/xLAM-2-8b — dataset ~200-500 (état_monde→message), export GGUF → llama-swap ; voir `gameplay_llm.md §Fine-tuning GM` | ⬜ Après Phase 11.3 stable |

