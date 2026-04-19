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
> | 2 | [GDD.md §lié](GDD.md) | Design intent : pourquoi la mécanique existe, comment elle se comporte |
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
- [x] `SimulationContracts.cs` — structs `GoldbergTileState` et `BodyListEntry`

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

**Backlog** :
- [ ] `/game/corporation` → `get_corporation_state`
- [ ] `/game/market` → `get_market_state`
- [ ] `/game/events` → `get_active_events`
- [ ] `/game/tick` → `get_tick_state`
- [ ] `/game/planet` → `get_planet_overview`
- [ ] Règle : les writes (claim, achat) passent par Mirror, jamais par cette API

---

## Ordre d'exécution conseillé

- [x] Ne pas démarrer la Phase 7 avant la fin du Sprint C et du Sprint D ✅ (2026-04-19)
- [x] Considérer la Phase 6.5 comme terminée seulement quand les critères de sortie des sprints A et B sont validés ✅ (2026-04-19)
- [x] Utiliser le Sprint C comme sas de stabilisation avant `Corporation`, `Events` et `Economy` ✅ (2026-04-19)

> **→ Phase 7 débloquée.**

---

## Phase 7 — Gameplay Corporation v1

**Prérequis** : Sprint C (persistance régionale) + Sprint D (AtmosphericState) terminés. Phase 6.9 (hiérarchie Cosmos) ✅

> Design de référence : [GDD.md §10-15](GDD.md) — Corporations, États, Marchés, Contrats, Contrôle de tuiles

### Phase 7.1 — Propriété de tuile
- [ ] Créer `CorporationData` côté Python `SimulationCore` + contrat C# miroir
- [ ] Implémenter le claim d'un hex libre — `POST /game/corporations/{id}/claim-hex`
- [ ] Modéliser la propriété : tuile appartient à un État ou une corpo (ou personne)
- [ ] Afficher les hexes possédés (bordure colorée par corpo) — couche ownership sur la grille Unity
- [ ] Exposer `GET /game/corporations` sur `DedicatedServer` pour le MCP

### Phase 7.2 — Bâtiments v1 (modèle entrée → sortie)
- [ ] Implémenter le modèle tick-based : entrées (ressources + travailleurs + énergie) → sorties (ressources + déchets)
- [ ] Types de bâtiments initiaux : mine, ferme, centrale énergetique, bâtiment de recherche
- [ ] Ratio travailleurs 0→100% : 100% = plein rendement, 0% = bâtiment abandonné
- [ ] Réseau énergétique limitrophe : centrale → segments → tuiles adjacentes
- [ ] Épuisement de ressource de tuile + reconversion possible
- [ ] Calcul automatique de la production par tick côté `DedicatedServer`
- [ ] Déchets s'accumulent sur la tuile (impact moteur écologique)

### Phase 7.3 — Marché local v1
- [ ] Catégories sociales de population (pauvres → classes moyennes → riches) avec besoins différents
- [ ] Offre/demande dynamique à chaque tick, propagation des prix atténuée par la distance
- [ ] Mobilité sociale : richesse qui évolue selon l'emploi, migrations sur événement
- [ ] Marché national régulé par l'État (taxes, quotas)
- [ ] Afficher un HUD de base (solde, ressources, score) + barre atmosphérique

### Phase 7.4 — Contrats v1
- [ ] Contrats État ↔ Corporation et Corporation ↔ Corporation
- [ ] Types : livraison de ressources, contrôle territorial, exploration, présence militaire
- [ ] Diffusion publique (enchères, le proposeur choisit) et privée (direct, validation bilatérale)
- [ ] Durée fixe et open-ended, rupture possible avec pénalités
- [ ] Diffusion de connaissance via contrat (corpo → État, corpo → corpo)

### Phase 7.5 — Réputation, États et nationalisation
- [ ] Réputation globale + réputation bilatérale par paire
- [ ] Seuil de tolérance de l'État calculé selon puissance, comportement, contrats
- [ ] Types d'État (capitaliste, nationaliste…) + taux de corruption (passif et exploitable)
- [ ] Processus de nationalisation progressif (délai = bureaucratie + corruption)
- [ ] Fenêtre de réaction pour la corpo (corruption, contrat spécial)
- [ ] Afficher un scoreboard avec toutes les corpos

**Cible**
> Une corpo joueur qui claim des hexes, construit des mines, signe des contrats avec les États, accumule des crédits et monte au classement. `habitabilityScore` est le KPI environnemental commun.

---

## Phase 8 — Système d'Événements & Agents LLM

> Design de référence : [GDD.md §16-17](GDD.md) — Événements, IA & Agents LLM

- [ ] `EventData` : nom, description, effets, poids de probabilité, déclencheur (tick ou condition)
- [ ] Événements de base : RencontreAlienne, TempêteSolaire, DécouverteMinière, CriseÉconomique, SabotageCorpo, Rébellion, MigrationPopulation
- [ ] `EventManager` : tirage pondéré à chaque tick serveur
- [ ] Popup UI de notification
- [ ] Intégration agent LLM via MCP : appelé sur événement significatif ou toutes les N ticks
- [ ] Mémoire contextuelle par entité (profil, événementielle, relationnelle)
- [ ] Agent maître de jeu : peut déclencher des événements scénarisés

**Cible** : événements qui modifient l'état de la partie en temps réel, avec un agent LLM capable de réagir stratégiquement pour les États et corporations IA

---

## Phase 9 — Économie avancée & Routes commerciales

> Design de référence : [GDD.md §12](GDD.md) — Marchés, Routes commerciales, Organisme inter-étatique

- [ ] Ressources tradables : fer, O₂, eau, énergie, tech, nourriture
- [ ] `MarketManager` avec order book simplifié, propagation hiérarchique (tuile → planète → système)
- [ ] Fluctuation des prix (offre/demande par tick)
- [ ] UI de marché pour les corpos joueurs
- [ ] Corpos IA participantes au marché
- [ ] Routes commerciales : exploration → construction → propagation des prix entre tuiles connectées
- [ ] Routes spatiales (inter-planètes/systèmes) + infrastructure spatioport
- [ ] Organisme inter-étatique optionnel (marché global corruptible)

**Cible** : bourse qui fluctue en temps réel, marchés connectés par routes, possibilité de marché global inter-étatique

---

## Phase 10 — Multijoueur Réseau

> Design de référence : [GDD.md §18](GDD.md) — Multijoueur

- [ ] Intégrer Mirror Networking
- [ ] Serveur dédié autoritaire (client-serveur, pas P2P)
- [ ] Synchroniser hexes, corpos, marché entre clients
- [ ] Authentification joueur (Unity Authentication)
- [x] Persistance serveur — PostgreSQL + SQLAlchemy Core (write-through, ✅ Phase 2 terminée)
- [ ] Synchronisation Firebase ou autre pour la persistance client/cloud multi-instances
- [ ] Test avec 2 joueurs simultanés

---

## Phase 11 — IA Corporations

- [ ] `BotCorporation` avec FSM
- [ ] 3 profils : Expansionniste, Économiste, Militariste/Saboteur
- [ ] Réaction aux événements et aux fluctuations de marché

---

## Phase 12 — Polish

- [ ] UI/UX complet : HUD, menus, tooltips
- [ ] Sound design
- [ ] Équilibrage économique (playtesting)
- [ ] Optimisation performances (profiler Unity)
- [ ] Distribution (itch.io ou autre)

---

## Récapitulatif

| Phase | Contenu | Statut |
|---|---|---|
| 0–6.9, Sprint 0 | Fondations, grille, génération, vues, terraformation, cosmos, split sim | ✅ Voir [CHANGELOG.md](CHANGELOG.md) |
| 6.75 | Isolation bridge Unity | ✅ Voir [CHANGELOG.md](CHANGELOG.md) |
| 6.5 + Sprints A→D | Hydrologie, cohérence, persistance, AtmosphericState | 🔄 En cours |
| MCP-1, 2, 3 | Outils cellule, tests auto, API gameplay | ⬜ À faire |
| 7 | Corporations | ⬜ À faire (attend Sprints C + D) |
| 8 | Événements | ⬜ À faire |
| 9 | Économie & Bourse | ⬜ À faire |
| 10 | Multijoueur Réseau | ⬜ À faire |
| 11 | IA Corporations | ⬜ À faire |
| 12 | Polish | ⬜ Continu |
