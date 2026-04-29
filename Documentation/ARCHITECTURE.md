# Architecture Technique — Terraformation & Colonisation Spatiale

> **Voir aussi** : [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md) pour le découpage monorepo · [MCP_TOOLS_ARCHITECTURE.md](MCP_TOOLS_ARCHITECTURE.md) pour le détail des tools MCP et endpoints · [SIMULATION_CONTRACTS.md](SIMULATION_CONTRACTS.md) pour les contrats Python ↔ C#

## Stack Technique

| Composant | Technologie | Pourquoi |
|---|---|---|
| Moteur | Unity 6 LTS (3D URP) | Stable, bien documenté, large communauté |
| Langage | C# | Natif Unity |
| Réseau | WebSocket FastAPI natif + NativeWebSocket (Unity) | ~~Mirror Networking~~ (remplacé — [2026-04-21]) ; WebSocket plus simple, LLM/agent compatible, même bus que les endpoints REST |
| Persistance (serveur) | PostgreSQL 16 + SQLAlchemy Core 2.x | Write-through depuis `InMemorySimulationRuntime`, restauration au démarrage |
| Caméra | CameraController (custom) | Pan/zoom/orbit new Input System, 3 modes selon la vue active (ortho solaire, orbit planétaire, ortho local) |
| Grille | Mesh procédural (axial coordinates) | Inspiré Catlike Coding Hex Map, un seul mesh, vertex colors, zéro gap |
| Build | Desktop (Windows / Mac / Linux) | Pas de contrainte réseau (WebGL écarté) |
| Agent IA / MCP | FastMCP 3.x (Python) + Docker | Serveur MCP HTTP conteneurisé, wrapp les APIs debug et serveur sans porter les règles du jeu |

---

## Cible d'Architecture

La cible retenue n'est plus un jeu Unity monolithique avec un bridge debug autour, mais une séparation explicite en quatre couches :

| Couche | Responsabilité | Doit rester dans Unity ? |
|---|---|---|
| `Simulation Core` | génération, hydrologie, terraformation, règles du monde, tick, états métier | Non |
| `Simulation Host` | boucle serveur autoritaire, stockage d'état, commandes, snapshots | Non |
| `Unity Client` | rendu, caméra, vues, input, HUD, visualisation des snapshots | Oui |
| `MCP / Tools` | debug, smoke tests, diagnostics, opérations | Non |

### Décision structurante

- Unity doit devenir un **client de rendu et d'interaction**.
- Le serveur doit devenir la **source de vérité** du monde.
- Le MCP doit rester une **façade d'outillage**, jamais le moteur métier ni le backend autoritaire.

### Conséquence immédiate

Les futurs systèmes `Corporation`, `Economy`, `Events` et `Networking` ne doivent plus être conçus comme des extensions du runtime client Unity. Ils doivent naître côté `Simulation Core` / `Simulation Host`, puis être consommés par le client.

### Conséquence dépôt / monorepo

Le dépôt doit converger vers plusieurs sous-projets visibles à la racine, et non un seul bloc autour de `Game/` :

| Sous-projet | Rôle |
|---|---|
| `Game/` | client Unity |
| `Mcp/` | FastMCP, Docker, outils agent |
| `DedicatedServer/` | serveur autoritaire |
| `SimulationCore/` | logique métier partagée hors Unity |

Le dossier `Tools/` doit devenir un espace transitoire ou utilitaire, pas le lieu final de composants de production.

---

## Décisions d'Architecture

### Client-Serveur (pas P2P)
- Le serveur dédié est **autoritaire** : toutes les actions passent par lui
- Les clients n'envoient que des **intentions** (vouloir claimer un hex, acheter une ressource)
- Le serveur valide, applique et renvoie le nouvel état
- **Avantages** : monde persistant, anti-triche, déconnexion propre

### Refactor en cours

Un premier lot de seams d'extraction a été posé dans le projet Unity pour préparer la sortie du coeur de simulation :

- `ITickSource`
- `IHexCellStore`
- `IGridRefreshSink`
- `IClientSnapshotSource`
- `TerraformSimulationSession`
- `TerraformHabitabilityEvaluator`

Objectif : déplacer progressivement la logique autoritaire hors des `MonoBehaviour` sans casser la scène actuelle.

Le client Unity commence aussi à être repositionné comme **adaptateur de snapshots** : `ViewManager` sait maintenant produire `ProjectionState`, `RegionState`, `ClientSnapshot` et `WorldState` via les contrats partagés, au lieu de laisser chaque consommateur reconstituer l'état ad hoc.

`SimulationCore/terraformation_sim/` est opérationnel hors Unity : `models.py` (Pydantic), `logic.py` (logique pure), `runtime.py` (`InMemorySimulationRuntime`). Le `DedicatedServer` en dépend directement. Les contrats C# (`SimulationContracts.cs`) reflètent fidèlement ces modèles Python pour la désérialisation Unity.

`TerraformSystem.cs` délègue maintenant toutes les actions de terraformation au `DedicatedServer` via HTTP POST avec fallback local. Les réponses `WorldState` et `RegionState` sont appliquées autoritairement sur la grille locale : `ApplyAuthoritativeRegionState` itère `regionState.cells` (tableau complet de `SimulationCellState`) et écrase chaque `HexCell` correspondant.

### Monde Persistant
- Le serveur tourne **en continu**, même sans joueurs connectés
- **Write-through PostgreSQL** : chaque mutation (tile, corps, région, pending action) est écrite immédiatement en base
- `tickCount` persisté toutes les 10 ticks
- Au redémarrage du container, l'état est rechargé depuis PostgreSQL via `_hydrate_from_saved()`
- Mode `in-memory` disponible via `SERVER_MODE=in-memory` (zéro base de données, backward-compatible)
- **Évolution du schéma en dev** : wipe DB + `bootstrap_sol()` suffit — pas de scripts de migration SQL nécessaires en développement. Les `ALTER TABLE ADD COLUMN IF NOT EXISTS` dans `_ensure_schema()` sont conservés pour la prod/staging uniquement.
- `population_json` (JSON sérialisé) est persisté dans la table `tiles` — hydraté au démarrage via `_hydrate_tiles_from_db()`, re-sauvegardé après bootstrap colonisation (`runtime_bootstrap.py`)

### Pas de WebGL
- WebGL interdit les sockets IP directs → incompatible avec Mirror Networking sans transport custom
- On cible le **Desktop** uniquement pour cette version

### ScriptableObjects pour les données
- Terrains, bâtiments, événements sont définis comme **ScriptableObjects**
- Permet de modifier les données sans recompiler le code
- Facilite l'équilibrage en cours de développement

### Icônes UI bâtiments
- Les bâtiments gardent leur définition métier dans `Economy/BuildingData.cs` et leurs contrats réseau dans `SimulationContracts.cs`
- L'iconographie UI des bâtiments est une couche de présentation séparée côté client Unity
- `GameHUDBuildingIcons.cs` mappe `CorpBuildingType` vers un libellé, une teinte et un token d'icône
- La source visuelle actuelle est une police locale `Font Awesome 7 Free-Solid-900.otf` placée sous `Assets/Resources/Fonts/`
- Le rendu des icônes bâtiments est géré par les sous-contrôleurs HUD (`TileInspectorController`, `BottomActionBarController`) via `GameHUDBuildingIcons.cs` ; si la police ou les glyphes sont indisponibles, fallback texte (`M`, `F`, `E`, `R`)
- Conséquence : la logique gameplay ne dépend jamais d'un glyph, d'un nom d'icône ou d'un asset UI particulier ; la source visuelle pourra être remplacée plus tard par un `TMP Sprite Asset` sans modifier les types métier

### Système de Vues 3 Niveaux
Implémenté dans une seule scène `Game.unity` — 3 racines de GameObject activées/désactivées par `ViewManager`.

| Vue | Caméra | Root GO | Transition entrée | Transition sortie |
|---|---|---|---|---|
| Système Solaire | Orbit perspective | `SolarSystemRoot` | Démarrage / retour local | — |
| Planétaire | Orbit Perspective (Globe) / Ortho tangente (Flat) | `PlanetRoot` | Clic planète | `Escape` |
| Locale (hex) | Ortho top-down | `HexGridRoot` | Clic projection | `Escape` |

**Machine d'état `ViewManager`** :
- `ViewState` : `SolarSystem → Planet → Local`
- Souscrit aux events `CameraController.OnZoomedToMin` et `OnZoomedToMax`
- À chaque transition : désactive le root actuel, active le suivant, configure `CameraController.SetMode()`

**`CameraController` — 3 modes** :
- `OrthoTopDown` : pan (right-drag XZ) + zoom (orthographicSize)
- `OrbitPerspective` : right-drag = rotation azimut/élévation autour d'un pivot, scroll = distance
- Events : `Action OnZoomedToMin`, `Action OnZoomedToMax` → déclenchés aux bornes de zoom

**Couleur planétaire (H3 server tiles)** :
- Les tuiles de la sphère Goldberg sont colorisées depuis les données H3 autoritatives du `DedicatedServer` (`GET /bodies/{id}/tiles`)
- `GoldbergFaceColorizer.ColorizeFromServerTiles()` mappe chaque face GP vers la tuile H3 la plus proche par lat/lon (nearest-neighbor)
- Le `colorByType` est construit depuis `OrbitalBody.layers[].biomes` (tous les `TerrainType` déclarés)
- `PlanetaryHexGrid` n'est **plus** impliqué dans la colorisation des vues planétaires — ses constantes `MaxCols/MaxRows` restent utilisées uniquement par `GoldbergSphereGenerator` pour calibrer la résolution de la sphère
- La sphère `PlanetSphereGoldberg` déclenche `OnH3TilesReady(GoldbergTileState[], Dictionary<TerrainType, Color>)` après chaque fetch réussi — `ViewManager` distribue ce résultat à `PlanetFlatView` et `PlanetTangentView`
- Clic → `OnRegionClicked` → coroutine `GET /bodies/{id}/tiles/at` → `OnH3TileResolved(GoldbergTileState)` → HUD

**Cohérence des données entre vues** :
- `OrbitalBody` contient les paramètres source du monde, pas une persistance exhaustive de tous les hexes.
- Les tuiles H3 du `DedicatedServer` sont la **source de vérité** des couleurs pour Globe, FlatView et TangentView.
- `MapRegion` capture la zone cliquée (`latitude`, `longitude`, `solarSystem`, `planet`) et sert de source à la génération locale.
- `HexGrid.LoadRegion()` régénère la vue locale depuis `MapRegion` pour conserver le contexte régional et orbital.
- La tuile H3 cliquée (`GoldbergTileState`) porte la contrainte macro (`terrainType`, `waterRatio`, `temperature`) qui guide, sans écraser, la génération locale.

---

## Structure des Dossiers Unity

```
Assets/
├── Scripts/
│   ├── HexGrid/          # HexMetrics, HexMesh, HexGrid, HexCell, HexInput
│   ├── World/
│   │   ├── Cosmos/       # Hiérarchie corps célestes
│   │   │   ├── CelestialBody.cs      # Base ScriptableObject abstraite
│   │   │   ├── OrbitalBody.cs        # Physique, atmo, géo, couches WorldLayer
│   │   │   ├── StarBody.cs
│   │   │   ├── Planet.cs
│   │   │   ├── Moon.cs
│   │   │   ├── Asteroid.cs
│   │   │   ├── GasGiant.cs
│   │   │   └── GalaxyData.cs
│   │   ├── Data/         # Structs et contrats de données
│   │   │   ├── CelestialBodyData.cs  # PlanetaryPhysics, AtmosphericComposition…
│   │   │   ├── StarData.cs           # Legacy
│   │   │   ├── OrbitalParameters.cs
│   │   │   ├── SolarSystemData.cs
│   │   │   ├── IHexSystem.cs         # Interface pipeline génération
│   │   │   ├── TerraformAction.cs
│   │   │   ├── TerraformActionData.cs
│   │   │   └── TerraformProgressTracker.cs
│   │   ├── Generation/   # Pipeline génération monde
│   │   │   ├── MapRegion.cs
│   │   │   ├── MapGenerator.cs
│   │   │   ├── MapGenParameters.cs
│   │   │   ├── PlanetaryHexGrid.cs   # Constantes résolution sphère GP + grille Mercator
│   │   │   ├── PlanetaryWeatherState.cs
│   │   │   ├── GenerationContext.cs
│   │   │   ├── GoldbergSphereGenerator.cs
│   │   │   └── LocalProjection.cs
│   │   ├── Hexasphere/   # Géométrie sphère de Goldberg (bas niveau)
│   │   │   ├── Hexasphere.cs
│   │   │   ├── Face.cs
│   │   │   ├── Tile.cs
│   │   │   ├── Point.cs
│   │   │   └── MeshDetails.cs
│   │   ├── Input/        # Entrées caméra vue planétaire
│   │   │   ├── PlanetFlatInput.cs
│   │   │   └── PlanetTangentInput.cs
│   │   ├── Rendering/    # Rendu planète, sphère Goldberg, overlays
│   │   │   ├── PlanetSphereGoldberg.cs            # Sphère GP principale — fetch tiles, clic, overlay
│   │   │   ├── PlanetSphereGoldbergServerFetch.cs # Fetch paginé GET /bodies/{id}/tiles
│   │   │   ├── PlanetSphereGoldbergInput.cs       # Raycasting clic → OnH3TileResolved
│   │   │   ├── PlanetSphereGoldbergOverlay.cs     # Colorisation territoire / ownership
│   │   │   ├── GoldbergFaceColorizer.cs           # Nearest-neighbor lat/lon → TerrainType → Color
│   │   │   ├── GoldbergAtmosphere.cs
│   │   │   ├── PlanetFlatMesh.cs
│   │   │   ├── PlanetFlatView.cs
│   │   │   ├── PlanetTangentMesh.cs
│   │   │   ├── PlanetTangentView.cs
│   │   │   ├── PlanetSphere.cs                    # Archivé — précédente sphère UV
│   │   │   ├── PlanetTextureGenerator.cs          # Archivé
│   │   │   ├── FlatDebugOverlay.cs
│   │   │   ├── OwnershipBorderRenderer.cs
│   │   │   ├── PlanetCloudLayer.cs
│   │   │   ├── MinimapController.cs
│   │   │   ├── TerrainColorPalette.cs
│   │   │   └── WorldLayer.cs
│   │   └── Systems/      # IHexSystem pipeline (Phase 4)
│   │       ├── HeightSystem.cs
│   │       ├── TemperatureSystem.cs
│   │       ├── WaterSystem.cs
│   │       ├── WaterClassificationSystem.cs
│   │       ├── HydrologySystem.cs
│   │       ├── WindSystem.cs
│   │       ├── SoilSystem.cs
│   │       ├── BiomeSystem.cs
│   │       ├── RiverSystem.cs
│   │       ├── ValidationSystem.cs
│   │       ├── CoherenceValidationSystem.cs
│   │       └── TerraformSystem.cs
│   ├── Corporation/      # Entités politiques
│   │   └── PoliticalEntity.cs
│   ├── Economy/
│   │   ├── ResourceType.cs
│   │   ├── BuildingData.cs
│   │   └── BuildingInstance.cs
│   ├── Events/
│   ├── Networking/       # SimulationWebSocketClient, SimHttp, auth helpers
│   └── UI/
│       ├── CameraController.cs
│       ├── ViewManager.cs            # Machine d'état 3 vues (SolarSystem → Planet → Local)
│       ├── SolarSystemView.cs
│       ├── GalaxyView.cs
│       ├── GameHUDController.cs      # Orchestrateur HUD principal — voir section HUD ci-dessous
│       ├── TerraformHUD.cs           # Events OnProgressUpdated, OnRegionStateChanged
│       ├── TestLaunchMenu.cs         # Legacy UGUI — Hydrology Test Launcher (s'ouvre via btn Debug)
│       ├── DebugHydrologyPanel.cs    # Legacy UGUI — panneau projection/hydro (F10)
│       ├── LoginPanel.cs
│       └── HUD/                      # Sous-contrôleurs UI Toolkit
│           ├── TopBarController.cs           # Barre haute : retour, nom planète, tick, barre terraform, debug
│           ├── LeftPanelController.cs        # Panneau gauche : données atmo + scoreboard (caché si vide)
│           ├── TileInspectorController.cs    # Panneau gauche : inspecteur tuile (remplace LeftPanel au clic)
│           ├── TerritoryPanelController.cs   # Panneau droit : état / territoire (s'ouvre via badge tuile)
│           ├── BottomActionBarController.cs  # Barre basse : onglets Territoire/Construction/Marché…
│           ├── EventFeedController.cs        # Flux d'événements overlay
│           ├── DebugDrawerController.cs      # Tiroir debug (toggle bouton Debug / F9)
│           └── TimeControlsController.cs     # Contrôles vitesse tick (1x, 2x, 10x…)
│
├── Scripts/Editor/
│   ├── HUDAssetsSetup.cs     # MenuItem "Terraformation/Setup HUD Assets" — assigne les UXML/USS sur GameHUDController
│   └── SceneSetupHelper.cs
│
├── UI/
│   ├── HUDTheme.tss          # Thème PanelSettings — importe tous les USS via @import
│   ├── Templates/            # UXML par contrôleur
│   │   ├── TileInspector.uxml
│   │   ├── BottomActionBar.uxml
│   │   ├── DebugDrawer.uxml
│   │   ├── EventFeed.uxml
│   │   ├── EventPopup.uxml
│   │   ├── TopBar.uxml
│   │   ├── LeftPanel.uxml
│   │   └── Tooltip.uxml
│   └── Styles/               # USS tokens + styles par composant
│       ├── variables.uss     # Design tokens CSS (couleurs, tailles, espacements)
│       ├── base.uss          # Styles globaux (séparateur, label, btn)
│       ├── TopBar.uss
│       ├── LeftPanel.uss
│       ├── TileInspector.uss # Inclut .territory-panel + .tile-inspector__badge-btn
│       ├── BottomActionBar.uss
│       ├── DebugDrawer.uss
│       └── DESIGN.md         # Source de vérité design tokens (synced vers variables.uss)
│
├── ScriptableObjects/
│   ├── Worlds/
│   ├── Terrains/
│   ├── Buildings/
│   └── Events/
│
├── Materials/
│   └── HexVertexColor.mat
│
├── Prefabs/
│
└── Scenes/
    ├── MainMenu.unity
    ├── Game.unity
    └── Loading.unity
```

---

## Architecture HUD Unity (UI Toolkit)

> **Décision [2026-05]** : Abandon de l'ancien `GameHUD.cs` UGUI. Tout le HUD principal est construit via **UI Toolkit** (code-driven, pas de `UIDocument.sourceAsset`). `GameHUDController.cs` orchestre 8 sous-contrôleurs `MonoBehaviour`.

### Hiérarchie de composants

```
[HUDController]  (GameObject dans Game.unity)
  ├── GameHUDController          ← Point d'entrée, UIDocument racine, wiring ViewManager
  ├── TopBarController           ← Bouton retour, nom planète, tick, barre terraform inline, bouton Debug
  ├── LeftPanelController        ← Données atmosphériques + scoreboard (masqué si pas de données)
  ├── TileInspectorController    ← Inspecteur tuile sélectionnée (badge territoire → TerritoryPanel)
  ├── TerritoryPanelController   ← Panneau droit : état / territoire / population
  ├── BottomActionBarController  ← Onglets Territoire / Construction / Marché / Diplomatie
  ├── EventFeedController        ← Flux événements overlay
  ├── DebugDrawerController      ← Tiroir debug (toggle F9 / bouton Debug)
  └── TimeControlsController     ← Contrôles vitesse tick
```

### Règles de construction HUD

1. **Aucun `UIDocument.sourceAsset`** — les templates UXML sont des `[SerializeField] VisualTreeAsset` sur `GameHUDController`, passés aux sous-contrôleurs via `Initialize(root, template)`.
2. **Styles inline pour layout critique** — après `CloneTree()`, les propriétés `position`, `flex-direction`, `bottom`, `right` sont forcées en C# inline (CloneTree n'applique pas les `<Style src>` du UXML dans un conteneur existant).
3. **Visibilité conditionnelle** : `LeftPanelController` n'affiche le panneau que si `_hasAtmoData = true` (évite un panneau vide au démarrage). De même `TerritoryPanelController` démarre caché.
4. **Single event source** : F9 est géré uniquement par `GameHUDController.ToggleDebugDrawer()` → `testLaunchMenu?.ToggleMenu()`. `TestLaunchMenu.Update()` ne capture plus F9 pour éviter le double-déclenchement.

### Flux TileInspector → TerritoryPanel

```
Clic tuile → PlanetSphereGoldbergInput.OnH3TileResolved(GoldbergTileState)
  → GameHUDController.OnTileSelected()
    → TileInspectorController.ShowTile(tile)
      → badge territoire (initiales stateName) visible si tile.stateId non vide
      → clic badge → GameHUDController.ShowTerritoryPanel(stateId, stateName)
        → TerritoryPanelController.ShowTerritory(stateId)
          → GET /game/states/{stateId} → RenderState(StateDto)
```

### Barre terraform (TopBar)

La barre de progression TERRAFORMATION est embarquée **inline** dans `TopBarController.BuildTopBarProcedural()` : label "TERRA" + track 80 px + fill (width en `Percent`) + label pourcentage. `SetTerraformProgress(float progress)` la masque si `progress >= 1f`.

---

## Architecture Réseau (WebSocket FastAPI)

> **Décision [2026-04-21]** : Mirror Networking remplacé par WebSocket FastAPI natif (`GET /game/ws/events?token=<JWT>`) + JWT maison (python-jose HS256, passlib bcrypt, table `players` PostgreSQL). Client Unity utilise NativeWebSocket (OpenUPM `com.endel.nativewebsocket`). Le tick serveur push `{"type":"tick_advanced","tick":N}` à tous les clients connectés. Firebase exclu (contrainte architecture existante).

> **Contrainte implémentation [2026-04-28]** : `ws_broadcast()` est appelé depuis le **thread tick (synchrone)**. `WebSocket.send_text()` étant une coroutine async, le bridge se fait via `asyncio.run_coroutine_threadsafe(ws.send_text(msg), _main_event_loop)` où `_main_event_loop` est capturé au `@app.on_event("startup")`. À la connexion, le tick courant est envoyé immédiatement pour synchroniser la date chez tous les clients.

```
[Client A]──┐
[Client B]──┼──► [FastAPI DedicatedServer :8001]
[Client C]──┘      │   GET /game/ws/events?token=JWT  (WebSocket push)
                   │   POST /auth/login|register      (JWT HS256)
                   │
              [InMemorySimulationRuntime]
                   │   _advance_tick_locked() → ws_broadcast_callback
                   │
              [PostgreSQL]  (persistance tous les 10 ticks)
```

- Les **bots IA tournent uniquement côté serveur**
- Les **prix du marché** sont calculés côté serveur et broadcastés aux clients
- Les **événements** sont tirés et appliqués côté serveur
- Le client reçoit uniquement l'état visible (hexes proches, ses données corpo, prix marché)

---

## Architecture Agent IA / MCP

```
[VS Code Copilot / tout client MCP]
         │ HTTP MCP (port 8000)
         ▼
[Docker: terraformation-mcp]          ← Mcp/
  FastMCP 3.x (Python)
  Transport: streamable-http
         │
         ├── HTTP debug → client Unity / visualisation
         └── HTTP gameplay/debug → futur serveur de simulation
```

### Tools MCP exposés (server.py)

Les tools MCP sont répartis sur deux backends selon leur nature :

**Backend Unity bridge (port 48621)** — nécessite Unity en Play mode

| Tool | Endpoint | Description |
|---|---|---|
| `get_view_state` | `GET /debug/state` | État vue courante, planète active, région, hex sélectionné |
| `get_projection_summary` | `GET /debug/projection` | Résumé Mercator : distribution biomes, couverture eau |
| `get_local_summary` | `GET /debug/local` | Résumé région locale : terrain, hydrologie, biomes |
| `get_client_snapshot` | `GET /debug/client` | Snapshot structuré orienté client |
| `get_console_errors` | `GET /debug/console` | Logs Unity filtrés par sévérité |
| `take_screenshot` | `GET /debug/screenshot` | Capture d'écran runtime |
| `launch_preset` | `GET /debug/launch-preset` | Lance un scénario debug par nom |
| `open_region` | `GET /debug/open-region` | Navigue vers une région lat/lon normalisée |

**Backend DedicatedServer (port 8080)** — fonctionne sans Unity

| Tool | Endpoint | Description |
|---|---|---|
| `get_projection_state` | `GET /projection` | Snapshot `ProjectionState` autoritaire |
| `get_region_state` | `GET /region` | Snapshot `RegionState` avec `cells[]` complet |
| `get_world_state` | `GET /world` | Snapshot `WorldState` global (ticks, région, projection) |
| `get_last_simulation_event` | `GET /events/last` | Dernier `SimulationEvent` émis |
| `get_server_action_definitions` | `GET /actions/catalog` | Catalogue des actions de terraformation |
| `advance_simulation_tick` | `POST /tick/advance` | Avance le tick manuellement |
| `open_server_region` | `POST /commands/open-region` | Charge une région par lat/lon normalisé |
| `queue_server_terraform_action` | `POST /commands/queue-action` | File une action de terraformation |
| `apply_server_cell_delta` | `POST /commands/apply-cell-delta` | Applique un delta direct sur une cellule |

### Démarrer le serveur MCP

```bash
docker compose up -d          # démarre la stack canonique: dedicated server + MCP
docker compose down           # arrêt propre
docker compose logs -f        # logs en direct
```

La source de vérité Docker est désormais le compose racine. Les fichiers
`Mcp/docker-compose.yml` et `DedicatedServer/docker-compose.yml` restent utilisables,
mais seulement comme wrappers vers `../docker-compose.yml`.

### Configuration VS Code (.vscode/mcp.json)

```json
"terraformation-debug": {
  "type": "http",
  "url": "http://localhost:8000/mcp"
}
```

### Routes DedicatedServer (port 8080)

Le `DedicatedServer` expose 14 endpoints HTTP. Il fonctionne sans Unity.

| Endpoint | Méthode | Paramètres | Retourne |
|---|---|---|---|
| `/health` | GET | — | statut, service, tickCount, tickRunning, activePlanetName |
| `/world` | GET | — | `WorldState` complet |
| `/projection` | GET | — | `ProjectionState` |
| `/region` | GET | — | `RegionState` avec `cells[]` |
| `/events/last` | GET | — | dernier `SimulationEvent` |
| `/actions/definitions` | GET | — | `TerraformActionDefinition[]` |
| `/actions/catalog` | GET | — | `SimulationActionCatalog` |
| `/commands/bootstrap-demo` | POST | `planet_name`, `projection_override`, `projection_water_level` | `WorldState` — monde fictif paramétrable |
| `/commands/bootstrap-sol` | POST | — | `WorldState` — système Sol complet (Soleil + 8 planètes + 5 lunes, Terre active, Kepler-442 caché) |
| `/commands/open-region` | POST | `latitude`, `longitude` | `RegionState` avec `cells[]` |
| `/commands/queue-action` | POST | `action_type`, `q?`, `r?` | `WorldState` mis à jour |
| `/commands/apply-cell-delta` | POST | `water_delta`, `temp_delta`, `q?`, `r?` | `WorldState` mis à jour |
| `/commands/set-projection` | POST | `projection_override`, `water_level` | `WorldState` mis à jour |
| `/tick/advance` | POST | `steps` (défaut 1) | `WorldState` |
| `/tick/pause` | POST | — | `WorldState` |
| `/tick/resume` | POST | — | `WorldState` |
| `/tick/status` | GET | — | `{ tickCount, tickRunning, tickIntervalSeconds }` |
| `/bodies` | GET | — | liste de corps sans tiles |
| `/bodies/{id}` | GET | — | métadonnées du corps |
| `/bodies/{id}/tiles` | GET | `page`, `size` | `GoldbergTileState[]` paginé |
| `/bodies/{id}/tiles/at` | GET | `lat`, `lon` | `GoldbergTileState` — tuile H3 contenant la coordonnée |
| `/bodies/{id}/tiles/{tile_id}` | GET | — | `GoldbergTileState` (`tile_id` = index H3 string) |
| `/bodies/{id}/tiles/{tile_id}/neighbors` | GET | — | `GoldbergTileState[]` voisins directs (≤6) |
| `/bodies/{id}/tiles/{tile_id}/delta` | POST | `water_delta`, `temperature_delta` | `GoldbergTileState` |
| `/bodies/{id}/tiles/{tile_id}/action` | POST | `action_type` | `GoldbergTileState` |
| `/bodies/{id}/cells` | GET | `page`, `size` | `SimulationCellState[]` (zones intérieures) |
| `/bodies/{id}/zones` | POST | `zone_type`, `cols`, `rows`, `parent_tile_id?`, `seed?` | `InteriorZoneState` |

**Runtime** : `InMemorySimulationRuntime` — daemon thread, tick configurable (défaut 5s), état protégé par `threading.RLock`. Consomme `SimulationCore/terraformation_sim/` (models, logic, runtime, persistence Python partagé).

**Persistance** : `StateRepository` (ABC) → `InMemoryRepository` (no-op) | `PostgresRepository` (SQLAlchemy Core + psycopg2). Sélectionné par `SERVER_MODE` (`in-memory` ou `postgres`). `PostgresRepository` crée les tables au démarrage (`CREATE TABLE IF NOT EXISTS`) — 5 tables : `world_state`, `bodies`, `tile_mutations`, `cell_mutations`, `pending_actions`.

### Phase transitoire possible — Unity Dedicated Server dans Docker

Un build Unity headless peut servir d'étape intermédiaire, mais ce n'est pas la cible finale de référence si la simulation est réellement hébergée hors du jeu.

Quand un serveur dédié Unity est buildé en mode Linux headless :
- Ajouter un service `unity-server` dans `docker-compose.yml`
- Changer `GAME_BRIDGE_URL=http://unity-server:48621`
- Réseau Docker interne `terranet` pour isoler le trafic jeu / MCP

### Cible finale recommandée

À terme, le pont MCP doit parler majoritairement au `Simulation Host`, et seulement secondairement au client Unity pour les besoins visuels : screenshots, caméra, état de la vue, artefacts UI.

### Contrainte technique — Host header Windows HTTP.sys

`HttpListener` sous Windows délègue à `HTTP.sys` qui valide le header `Host` contre le prefix enregistré.
Quand Docker envoie `Host: host.docker.internal:48621`, HTTP.sys retourne **400** avant que Unity ne voie la requête.
**Fix** : `server.py` force `headers={"Host": "127.0.0.1:48621"}` sur toutes les requêtes httpx. Ne pas retirer cette override.



---

## Cycle de Tick Serveur

```
Tick (toutes les 10 secondes) :
  1. Calculer production de chaque bâtiment actif
  2. Mettre à jour les propriétés de terraformation des hexes actifs
  3. Recalculer les prix du marché (offre/demande)
  4. Tirer un événement aléatoire (probabilité configurée)
  5. Exécuter les décisions des bots IA
  6. Broadcaster le nouvel état aux clients connectés
  7. (Toutes les 10 ticks) Persister `world_state` dans PostgreSQL
```

---

## Modèle Objet 4 Niveaux

```
Niveau 0 — Galaxie / Système Solaire
  GalaxyData (ScriptableObject)
    └── SolarSystemData[]
  SolarSystemData (ScriptableObject)
    ├── StarBody (ScriptableObject) : type spectral, luminosité, zone habitable, seuil tidal
    ├── StarBody[] companionStars (systèmes binaires)
    └── OrbitalSlot[]
          ├── OrbitalParameters (struct) : demi-grand axe, excentricité, Hohmann
          └── OrbitalBody ──────────────────────────────── Niveau 1

Niveau 1 — Corps Orbital
  OrbitalBody (ScriptableObject abstrait)
    ├── Planet        (Rocky, OceanWorld, Desert, Volcanic)
    ├── Moon          (Icy, Rocky, Volcanic, Oceanic) — colonisable
    ├── Asteroid      (Rocky, Metallic, Icy, Carbonaceous)
    └── GasGiant      (non-atterrissable, grille hex orbitale)

  Champs communs (OrbitalBody) :
    ├── PlanetaryPhysics : baseEquatorTemperature, axialTilt, rotationSpeed
    ├── AtmosphericComposition : N2/O2/CO2/CH4/toxinRatio, density (presets: EarthLike, Mars, Volcanic)
    ├── GeologicalProfile : waterAbundance, geologicalActivity, mineralRichness, magneticField
    └── LayerZone[] : zones WorldLayer (Underground → Space)

Niveau 2 — Région (carte)
  MapRegion (ScriptableObject)
    ├── SolarSystemData (référence)
    ├── OrbitalBody planet (référence)
    ├── MapGenParameters
    ├── latitude [0..1] : 0 = pôle sud, 0.5 = équateur
    ├── longitude [0..1] : critique pour tidal lock
    ├── projectedTerrain / projectedWaterRatio
    └── CoherenceConstraint : oceanicity, deserticity, frigidity, flags extrêmes
  PlanetaryWeatherState (runtime, calculé une fois par Populate)
    ├── Cellules de Hadley simulées par latitude
    ├── Cas tidal lock : vent depuis face jour → face nuit
    └── Précipitations = waterAbundance × atmosphere.density

Niveau 3 — Hex
  HexCell
    ├── HexPhysicalState
    │     ├── altitude, tempLocale, waterRatio, toxinLevel
    │     ├── windVector, windSpeed, rainShadow
    │     ├── flowAccumulation, terrainClass, waterClassification
    │     └── SoilProfile : rockHardness, organicContent, porosity, mineralDensity
    └── HexOwnership
          ├── ownerType : Neutral | Corporation | Nation
          └── ownerId : identifiant de l'entité propriétaire
```

**Propriétés calculées** (jamais stockées manuellement) :
- `SolarIntensity` : calculé depuis `OrbitalParameters` + `StarBody.luminosity`
- `IsTidallyLocked` : `orbitalSlot.semiMajorAxis < star.TidalLockThresholdAU`
- `GreenhouseTemperatureOffset` : CO₂ > 0.5 → +20°C, CH₄ > 0.1 → +15°C

---

## Pipeline de Génération (IHexSystem)

```
Populate(HexCell[], MapRegion)
  │
  ├── BuildContext()  →  GenerationContext
  │       ├── SolarSystemData
  │       ├── OrbitalBody (Planet / Moon / Asteroid / GasGiant)
  │       ├── MapRegion
  │       ├── CoherenceConstraint
  │       ├── PlanetaryWeatherState  (calculé ici)
  │       ├── MapGenParameters
  │       └── seed / System.Random
  │
  ├── HeightSystem.Execute()
  ├── TemperatureSystem.Execute()
  ├── WaterSystem.Execute()        ← flux inter-hexes (critique)
  ├── HydrologySystem.Execute()    ← direction d'écoulement, accumulation, bassins
  ├── WindSystem.Execute()
  ├── SoilSystem.Execute()
  ├── CoherenceValidationSystem.Execute() ← garde-fou macro → micro
  ├── WaterClassificationSystem.Execute() ← océan / côte / eau intérieure / sec / gelé
  ├── BiomeSystem.Execute()        ← scoring relief + hydrologie + cohérence
  ├── RiverSystem.Execute()        ← flow-based
  └── ValidationSystem.Execute()
```

**Règle de séquencement** : chaque système ne lit que les champs remplis par les systèmes précédents. L'ordre du pipeline est donc déterministe et non modifiable sans vérifier les dépendances.

### Couche relief + hydrologie implémentée (v1)

**Objectif atteint en v1** : faire du relief un moteur réel du comportement de l'eau locale, et non un simple décor dérivé de l'altitude.

**Responsabilités actuelles** :
- `WaterSystem` : humidité initiale, évaporation, gel, précipitations, premiers échanges d'eau, rétention des bassins et ruissellement guidé par `downstream`
- `HydrologySystem` : champ d'écoulement, repérage des bassins, crêtes, chenaux, accumulation aval
- `CoherenceValidationSystem` : correction des cas extrêmes avant résolution finale des biomes
- `WaterClassificationSystem` : classification locale `OpenOcean / Coast / InlandWater / Dry / FrozenWater`
- `BiomeSystem` : prise en compte de la cohérence macro, du relief et de la classe d'eau pour choisir le `TerrainType`
- `RiverSystem` : suit le champ d'écoulement pré-calculé au lieu de recalculer chaque pente à la volée
- `HexMesh` : applique une teinte visuelle légère selon `waterClassification` et `terrainClass`, sans remplacer les `TerrainData`

**Principe physique simplifié** :
- les points hauts évacuent l'eau plus facilement
- les points bas l'accumulent
- les bassins retiennent l'eau jusqu'au débordement
- la connectivité à une masse d'eau ouverte distingue océan, côte et eau intérieure
- la température distingue eau liquide et eau gelée

**Principe de cohérence avec la projection** :
- la projection globale reste une approximation basse résolution
- la vue locale ajoute le détail de relief et d'hydrologie
- les contraintes de la case projetée servent de biais et de garde-fous, pas de vérité rigide absolue sauf cas extrêmes

**Limites connues de la v1** :
- le débordement réel des bassins n'est pas encore simulé
- la distinction côte / océan repose encore sur une heuristique de voisinage local
- la cohérence macro → micro ne tient pas encore compte d'une vraie rugosité ou d'une connectivité hydrologique agrégée

### Feuille de route technique immédiate

**Sprint 0 — Outillage AI, Debug et MCP**
- formaliser un workflow AI/debug partage par l'equipe
- definir la checklist de validation des presets de reference
- definir une facade runtime de debug Terraformation exploitable par MCP
- prioriser un premier lot d'outils: etat courant, lancement de preset, resume projection, resume local, console, screenshot
- traiter Unity MCP comme cible d'integration privilegiee pour les outils projet

**Sprint A — Stabilisation debug + hydrologie locale v2**
- fiabiliser `DebugHydrologyPanel` et tous les refreshs visuels associés
- terminer la logique locale de bassins, débordements et classification eau/côte
- valider en Play Mode les cas de référence : océan, côte, bassin, désert, gel

**Sprint B — Cohérence macro → micro + projection hydrologique**
- enrichir `MapRegion.ComputeCoherence()` avec des signaux de relief et d'hydrologie agrégés
- rendre la projection planétaire plus crédible sur les zones humides, côtières, arides et gelées
- conserver les presets debug comme cas de validation de non-régression

**Sprint C — Persistance régionale + synchro local → projection**
- introduire un cache runtime des modifications de région
- réappliquer ces deltas lors des reloads de projection et de région
- faire remonter un résumé local vers la projection pour préparer le gameplay de corporation

### Persistance runtime régionale prévue

Avant d'introduire les corporations, le monde local doit cesser d'être purement régénéré à la volée sans mémoire des interventions du joueur.

**Principe visé** :
- la projection reste une approximation globale générée
- chaque `MapRegion` peut accumuler des deltas runtime (eau, température, état terraformé, éventuellement biome forcé)
- ces deltas sont réappliqués à l'ouverture de la région locale
- une agrégation contrôlée de ces deltas peut ensuite influencer la projection planétaire

**Conséquence d'architecture** :
- `ViewManager` deviendra le point d'orchestration des ouvertures/reloads avec lecture d'un cache de région
- la vue locale ne devra plus dépendre uniquement de `MapGenerator.Populate()` mais aussi d'une passe de réapplication runtime
- la vue planète devra pouvoir recharger une projection tenant compte d'un état agrégé partiellement persistant

---

## Classes Principales

### HexGrid
| Classe | Rôle |
|---|---|
| `HexMetrics` | Constantes géométriques (outerRadius, innerRadius, coins flat-top) |
| `HexGrid` | Gère le tableau de cellules, déclenche la génération du mesh |
| `HexCell` | Données d’un hexagone (coordonnées, terrain, corpo owner) |
| `HexMesh` | Génère le mesh procédural unique (vertices, triangles, vertex colors) |
| `HexInput` | Raycast 3D, tooltip au survol, clic pour info |
| `TerrainData` (SO) | Définition d'un type de terrain |

### World (génération procédurale)
| Classe | Rôle |
|---|---|
| `CelestialBody` (SO abstrait) | Classe de base pour tous les corps célestes |
| `OrbitalBody` (SO abstrait) | Physique, atmo, géologie, couches WorldLayer — remplace `CelestialBodyData` |
| `StarBody` (SO) | Étoile : type spectral, luminosité, zone habitable, seuil tidal lock |
| `Planet` (SO) | Planète rocheuse / océanique / désert / volcanique |
| `Moon` (SO) | Lune colonisable avec pipeline génération complet |
| `Asteroid` (SO) | Astéroïde focus mining |
| `GasGiant` (SO) | Géante gazeuse — non-atterrissable, grille orbitale |
| `GalaxyData` (SO) | Conteneur galaxie — navigation inter-système |
| `OrbitalParameters` (struct) | Demi-grand axe, excentricité, période, transit Hohmann |
| `SolarSystemData` (SO) | Étoile + corps orbitaux + lunes, `IsTidallyLocked()`, `TransitDays()` |
| `MapRegion` (SO) | Localise une carte : système + corps + latitude + longitude |
| `PlanetaryWeatherState` | Météo régionale runtime — `Compute(body, region)` |
| `MapGenerator` | Orchestrateur du pipeline `IHexSystem` |
| `IHexSystem` | Interface commune de tous les systèmes de génération |
| `GenerationContext` | Contexte partagé injecté dans chaque `IHexSystem.Execute()` |
| `HexPhysicalState` (struct) | État physique complet d'un hex (altitude, temp, eau, sol…) |
| `SoilProfile` (struct) | Profil sol (dureté, matière organique, porosité, minéraux) |
| `HydrologySystem` | Calcule le champ d'écoulement, l'accumulation et les bassins |
| `WaterClassificationSystem` | Classe chaque hex en océan, côte, eau intérieure, sec ou gelé |
| `CoherenceValidationSystem` | Vérifie que la région locale reste cohérente avec la case projetée |

### Corporation & Entités Politiques
| Classe | Rôle |
|---|---|
| `PoliticalEntity` (abstract, `[Serializable]`) | Base runtime pour toutes les entités politiques (transport JSON serveur) |
| `Corporation` (`[Serializable]`) | Corpo joueur : stratégie, crédits, points R&D |
| `NationState` (`[Serializable]`) | État-nation : gouvernement, population, armée, stabilité |
| `OwnerType` (enum) | Neutral \| Corporation \| Nation |
| `HexOwnership` (struct, `[Serializable]`) | Appartenance politique d'un hex |
| `CorporationStrategy` (enum) | Expansionist \| Economist \| Militarist |
| `GovernmentType` (enum) | Democracy \| Autocracy \| Technocracy \| Military |
| `DiplomacyRelation` (`[Serializable]`) | Relation diplomatique entre deux entités |

### Economy & Bâtiments
| Classe | Rôle |
|---|---|
| `ResourceType` (enum) | Iron, Oxygen, Water, Energy, Tech, Food, RareMetal, Fuel, Credits |
| `ResourceStack` (struct, `[Serializable]`) | Quantité d'une ressource (inventaires, coûts, production) |
| `BuildingType` (enum) | Mine, Greenhouse, Refinery, PowerPlant, Laboratory, HQ, SpacePort… |
| `BuildingData` (SO) | Définition d'un bâtiment (coût, production, consommation, layers valides) |
| `BuildingInstance` (`[Serializable]`) | Instance runtime d'un bâtiment sur un hex |

### Projets
| Classe | Rôle |
|---|---|
| `Project` (abstract, `[Serializable]`) | Base runtime pour tous les projets longue-durée |
| `TerraformationProject` | Terraformation d'un hex spécifique |
| `InfrastructureProject` | Construction d'un bâtiment sur un hex |
| `ExplorationProject` | Exploration d'un corps céleste |
| `DiplomaticProject` | Diplomatie entre entités (alliance, guerre, annexion) |
| `ResearchProject` | Déblocage d'un nœud technologique |

### Economy (Marché)
| Classe | Rôle |
|---|---|
| `MarketManager` | Gère les prix, ordres, transactions |
| `MarketOrder` | Ordre d'achat ou de vente |

### Events
| Classe | Rôle |
|---|---|
| `EventManager` | Tirage et déclenchement des événements |
| `EventData` (SO) | Données d'un événement (effets, probabilité) |
| `EventEffect` | Application concrète d'un effet sur l'état du monde |

### Networking
| Classe | Rôle |
|---|---|
| `SimulationWebSocketClient` | WebSocket NativeWebSocket, reconnexion auto |
| `ServerTickManager` | Gère le cycle de tick serveur |
| `HexSyncObject` | NetworkBehaviour pour synchroniser un hex |
| `CorpoSyncObject` | NetworkBehaviour pour synchroniser une corpo |

---

## PostgreSQL — Structure des tables

```
world_state       -- 1 ligne (id=1, upserted)
  tick_count, tick_running, tick_interval_seconds,
  active_planet_name, projection_override, projection_water_level,
  has_region, region_lat, region_lon

bodies            -- 1 ligne par corps enregistré
  body_id PK, body_json TEXT  ← Pydantic model_dump_json (sans tiles/cells)

tile_mutations    -- sparse : seulement les tuiles mutées par des actions joueur
  body_id, tile_id  → UNIQUE
  water_ratio, temperature, toxin_level
  (tile_id = index H3 string, ex : "820007fffffffff")

cell_mutations    -- sparse : cellules de région modifiées
  body_id, cell_q, cell_r  → UNIQUE
  cell_json TEXT

pending_actions   -- queue terraform en vol
  action_id PK, action_json TEXT
```

Les tiles H3 complètes **ne sont pas stockées** — elles sont recalculées de façon déterministe depuis la résolution H3 (`h3Resolution`, dépend du rayon du corps), les paramètres de bruit (`waterLevel`, `seed`, `projectionOverride`). Seules les mutations joueur sont persistées (table `tile_mutations`).

---

## Ressources d'Apprentissage

| Sujet | Lien |
|---|---|
| Grille hexagonale (référence absolue) | https://www.redblobgames.com/grids/hexagons/ |
| NativeWebSocket (OpenUPM) | https://github.com/endel/NativeWebSocket |
| Firebase Unity SDK | https://firebase.google.com/docs/unity/setup |
| Unity ScriptableObjects | https://docs.unity3d.com/Manual/class-ScriptableObject.html |
| YouTube Unity 2D (Code Monkey) | https://www.youtube.com/@CodeMonkeyUnity |
| YouTube fondations Unity (Brackeys) | https://www.youtube.com/@Brackeys |
