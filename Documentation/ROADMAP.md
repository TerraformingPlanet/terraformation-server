# Roadmap — Terraformation & Colonisation Spatiale (Backlog Actif)

Chaque phase a une cible claire. **Ne pas passer à la suivante avant d'avoir atteint la cible.**

> Pour l'historique des phases complétées (Phase 0 → 6.9, Sprint 0), voir [CHANGELOG.md](CHANGELOG.md).

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

## En cours : Phase 6.75 — Split Simulation / Client / MCP

**Restant (1 tâche)** :
- [ ] Garder le bridge Unity uniquement pour le debug visuel et les artefacts de rendu — finaliser la migration des tools `get_view_state`, `get_projection_summary`, `get_local_summary`, `get_client_snapshot` vers le `DedicatedServer` ou les marquer définitivement comme "debug client uniquement"

**Cible**
> Le monde peut tourner sans la scène Unity, Unity peut afficher des snapshots serveur, et le MCP n'est plus un backend de fortune mais une couche d'outillage.

---

## En cours : Phase 6.5 — Relief & Hydrologie Locale

### Tâches restantes
- [ ] Étendre `MapRegion.ComputeCoherence()` et `CoherenceValidationSystem` avec rugosité, accumulation et signaux relief/hydrologie
- [ ] Ajouter un débordement de bassin avec exutoire dynamique
- [ ] Remplacer l'heuristique locale côte / océan par une logique de connectivité hydrologique plus robuste
- [ ] Vérifier en jeu les cas de référence : océan ouvert, côte, bassin, lac intérieur, désert drainant, pôle gelé

**Cible**
> Une région locale où l'eau suit le relief : les montagnes drainent, les cuvettes se remplissent, les côtes sont distinguées des lacs, et les pôles gelés restent cohérents avec la projection.

---

## Sprint A — Stabilisation Debug + Hydrologie Locale v2 (reste)

**Restant** :
- [ ] Vérifier en Play Mode les 5 cas de référence (océan ouvert, côte, bassin, désert drainant, pôle gelé)

**Critères de sortie restants** :
- [ ] Les bassins fermés, côtes et lacs sont lisibles visuellement dans les cas de test de base
- [ ] Les seuils hydrologiques ont une première passe de tuning documentée

**Fichiers** :
- `Game/Assets/Scripts/World/Systems/WaterSystem.cs`
- `Game/Assets/Scripts/World/Systems/WaterClassificationSystem.cs`

---

## Sprint B — Cohérence Macro → Micro + Projection Hydrologique

**Objectif**
> Améliorer la cohérence entre cellule projetée et région locale pour que la projection devienne un résumé hydrologique crédible du globe.

**Backlog** :
- [ ] Étendre `MapRegion.ComputeCoherence()` avec signaux de rugosité, accumulation et structure de relief
- [ ] Enrichir `CoherenceValidationSystem` pour utiliser ces signaux comme biais progressifs plutôt que des overrides trop binaires
- [ ] ~~Ajouter une hydrologie simplifiée côté `PlanetaryHexGrid` pour améliorer océan/côte/aride/gel côté projection~~ *(obsolète — la projection est maintenant H3 serveur)*
- [x] Rendre les zones côtières projetées plus robustes via une logique de connectivité ou de voisinage enrichi (côté serveur `logic.py`)
- [x] Remplacer le bonus transitoire `Basin` par une vraie connectivité hydrologique H3 côté serveur (`logic.py`) : voisinage, exutoires, distinction lac/côte et accumulation cohérente
- [x] Vérifier que les presets debug (Ocean, Arid, Frozen, Basin, Coast) restent cohérents après enrichissement de la projection
- [ ] Mettre à jour le HUD/debug pour comparer clairement projection et local sur les nouveaux signaux si nécessaire

**Livré côté serveur (v8)** :
- `SimulationCore/terraformation_sim/logic.py` applique une passe hydrologique H3 post-génération : composantes d'eau, eau connectée à l'océan, eau enclavée, cuvettes, chenaux et côtes
- `DedicatedServer/app/server.py` expose un bloc `hydrology` dans `/debug/generation-stats`
- les garde-fous `generation_smoke.py`, `Tools/Test-GenerationQuality.ps1` et `Mcp/server.py::run_generation_quality_suite()` ont été réalignés et validés sur les 5 presets

**Fichiers** :
- `Game/Assets/Scripts/World/MapRegion.cs`
- `Game/Assets/Scripts/World/GenerationContext.cs`
- `Game/Assets/Scripts/World/Systems/CoherenceValidationSystem.cs`
- ~~`Game/Assets/Scripts/World/PlanetaryHexGrid.cs`~~ *(projection maintenant côté serveur H3)*
- `Game/Assets/Scripts/UI/ViewManager.cs`

**Critères de sortie** :
- [ ] Un clic sur une zone projetée humide/aride/gelée produit une région locale cohérente sans forçage excessif
- [ ] La projection distingue mieux océan, côte et zones continentales humides
- [ ] Les presets debug restent exploitables et n'introduisent pas de régression de navigation

---

## Sprint C — Persistance Régionale + Synchro Local → Projection

**Objectif**
> Faire survivre les modifications locales aux régénérations et préparer la transition vers un vrai gameplay de corporation.

**Backlog** :
- [ ] Introduire un cache runtime des modifications par région (deltas d'eau, température, état terraformé)
- [ ] Réappliquer ces deltas lors de `ReloadCurrentProjection`, `OpenRegion` et `RegenerateCurrentLocalRegion`
- [ ] Définir la granularité de remontée local → projection (moyenne, max, ou agrégation hydrologique)
- [ ] Implémenter une première synchro locale → projection pour les signaux essentiels
- [ ] Vérifier qu'une région modifiée puis rechargée conserve son état attendu
- [ ] Préparer les points d'entrée qui serviront au claim de territoire et aux bâtiments

**Fichiers** :
- `Game/Assets/Scripts/UI/ViewManager.cs`
- `Game/Assets/Scripts/World/PlanetSphereGoldberg.cs`
- ~~`Game/Assets/Scripts/World/PlanetaryHexGrid.cs`~~ *(persistance régionale : côté serveur via `/tiles/{id}/delta`)*
- `Game/Assets/Scripts/HexGrid/HexGrid.cs`
- `Game/Assets/Scripts/World/MapRegion.cs`

**Critères de sortie** :
- [ ] Une modification locale persiste après fermeture/réouverture de la région
- [ ] La projection reflète au moins partiellement l'état local modifié sur la zone concernée
- [ ] Le socle technique est prêt pour démarrer Phase 7

---

## Sprint D — AtmosphericState : progression terraformation mesurable (prérequis Phase 7)

**Objectif**
> Donner aux corporations un indicateur de progression de la terraformation calculé à l'échelle de la région entière.

**Contexte**
La terraformation doit être modélisée comme une évolution atmosphérique agrégée (CO₂, O₂, pression) avec des boucles de feedback. L'`AtmosphericState` est l'agrégation des `SimulationCellState` en un indicateur région/planète lisible par les corporations.

**Backlog** :
- [ ] Définir `AtmosphericState` (Pydantic + C#) : `co2Ratio`, `o2Ratio`, `atmosphericPressure`, `averageTemperature`, `toxinRatio`, `habitabilityScore`
- [ ] Ajouter `atmosphericState: AtmosphericState` à `RegionState` (Python + C#) — mettre à jour [SIMULATION_CONTRACTS.md](SIMULATION_CONTRACTS.md)
- [ ] `SimulationCore/logic.py` — fonction `compute_atmospheric_state(cells)`
- [ ] `DedicatedServer` — peupler `atmosphericState` dans `/commands/open-region`
- [ ] `SimulationContractFactory.cs` — peupler `atmosphericState` dans `TryBuildRegionState`
- [ ] `TerraformHUD.cs` — afficher O₂%, CO₂%, pression, score d'habitabilité
- [ ] `TerraformProgressTracker.cs` — utiliser `habitabilityScore` comme source du slider
- [ ] Ajouter tool MCP `get_atmospheric_state(latitude, longitude)`

**Fichiers** :
- `SimulationCore/terraformation_sim/models.py`
- `SimulationCore/terraformation_sim/logic.py`
- `DedicatedServer/app/server.py`
- `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs`
- `Game/Assets/Scripts/Simulation/Contracts/SimulationContractFactory.cs`
- `Game/Assets/Scripts/UI/TerraformHUD.cs`
- `Game/Assets/Scripts/World/TerraformProgressTracker.cs`
- `Mcp/server.py`

**Critères de sortie** :
- [ ] `GET /commands/open-region` retourne un champ `atmosphericState` non vide
- [ ] Le HUD affiche O₂%, pression et score d'habitabilité depuis les données serveur
- [ ] `get_atmospheric_state` répond sans Unity ouvert
- [ ] Le slider de progression est cohérent avec `habitabilityScore`

---

## Sprints MCP — Responsabilité GitHub Copilot

**GitHub Copilot est propriétaire du MCP et de l'API du jeu.**
Référence complète : [MCP_TOOLS_ARCHITECTURE.md](MCP_TOOLS_ARCHITECTURE.md)

### Sprint MCP-1 — Outils de cellule et validation (Sprint B → C)

**Backlog** :
- [ ] Endpoint `/debug/cell?q=&r=` → tool `get_cell_detail`
- [ ] Endpoint `/debug/hydrology` → tool `get_hydrology_stats`
- [ ] Endpoint `/debug/validate` → tool `run_validation`
- [ ] Exposer ces 3 tools dans `Mcp/server.py` + documenter dans `MCP_TOOLS_ARCHITECTURE.md`
- [ ] Valider les 3 tools en Play Mode via Copilot Chat

**Critères de sortie** :
- [ ] L'agent peut sélectionner un hex par coordonnées axiales et lire son état complet
- [ ] L'agent peut déclencher `run_validation` et obtenir la liste des incohérences sans ouvrir Unity

### Sprint MCP-2 — Boucle de test automatisée (Sprint C → Phase 7)

**Backlog** :
- [ ] Implémenter la séquence `launch_preset → get_local_summary → comparer checklist → get_console_errors → take_screenshot` pour chaque preset
- [ ] Archiver les résultats JSON par preset dans `Artifacts/<PresetName>/`
- [ ] Produire un rapport de delta entre deux runs (régression / amélioration)
- [ ] Durcir `Tools/Test-GenerationQuality.ps1` et l'équivalent MCP (`run_generation_quality_suite`) comme garde-fou de tuning serveur : seuils par preset, faux positifs et lecture plus robuste des régressions
- [ ] Brancher cette suite dans un smoke Docker automatisé (`docker compose up -d --build` → exécution → code retour exploitable CI) pour verrouiller les régressions de génération sans Unity

**Critères de sortie** :
- [ ] Un seul appel déclenche la validation complète des 5 presets et produit un rapport lisible

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

- [ ] Ne pas démarrer la Phase 7 avant la fin du Sprint C et du Sprint D
- [ ] Considérer la Phase 6.5 comme terminée seulement quand les critères de sortie des sprints A et B sont validés
- [ ] Utiliser le Sprint C comme sas de stabilisation avant `Corporation`, `Events` et `Economy`

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
| 6.75 | Isolation bridge Unity | 🔄 1 tâche restante |
| 6.5 + Sprints A→D | Hydrologie, cohérence, persistance, AtmosphericState | 🔄 En cours |
| MCP-1, 2, 3 | Outils cellule, tests auto, API gameplay | ⬜ À faire |
| 7 | Corporations | ⬜ À faire (attend Sprints C + D) |
| 8 | Événements | ⬜ À faire |
| 9 | Économie & Bourse | ⬜ À faire |
| 10 | Multijoueur Réseau | ⬜ À faire |
| 11 | IA Corporations | ⬜ À faire |
| 12 | Polish | ⬜ Continu |
