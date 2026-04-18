# Architecture MCP — Terraformation

## Statut

| Composant | État |
|---|---|
| `RuntimeDebugHttpServer.cs` | ✅ opérationnel — Play Mode Unity, port 48621 |
| `RuntimeDebugFacade.cs` | ✅ opérationnel — 7 endpoints stables |
| Serveur MCP FastMCP (Docker) | ✅ opérationnel — `http://localhost:8000/mcp` |
| VS Code MCP config | ✅ configuré — `.vscode/mcp.json`, transport HTTP |
| Handshake MCP validé | ✅ validé le 17/04/2026 (`get_view_state` → JSON Unity) |

### Problème connu résolu — Host header Windows HTTP.sys

Quand Docker envoie une requête vers `http://host.docker.internal:48621`, le header HTTP automatique est `Host: host.docker.internal:48621`. Or `HttpListener` sous Windows est géré par `HTTP.sys`, qui valide que le header `Host` correspond au prefix enregistré (`http://127.0.0.1:48621/`). Si ce n'est pas le cas, HTTP.sys retourne **400 avant** que le code C# ne voie la requête.

**Fix appliqué** dans `Mcp/server.py` : le client httpx force `Host: 127.0.0.1:48621` sur toutes les requêtes vers le bridge Unity. Ne pas retirer cette override.

---

## Objet

Ce document définit l'architecture des outils MCP Terraformation, leur état actuel et la roadmap d'expansion vers le debug avancé, l'automatisation et le gameplay.

La cible n'est pas de tout automatiser d'un coup, mais d'exposer des actions simples, fiables, lisibles et utiles — d'abord au debug, ensuite au gameplay.

### Rôle architectural du MCP

Le MCP n'est pas la couche autoritaire du jeu.

- Le MCP expose des **tools d'observation, de diagnostic et d'orchestration**.
- Les règles du jeu, le tick, l'état persistant et la validation métier doivent vivre dans le **serveur de simulation**.
- Le bridge Unity reste utile pour le **debug visuel** et les artefacts client, mais ne doit pas devenir la source de vérité du monde.

## Objectifs du premier lot

1. observer l'etat du projet sans ambiguite
2. lancer des scenarios reproductibles
3. capturer des resumes et des artefacts
4. eviter les actions destructives implicites

## Principes de conception

### 1. Un outil = une intention claire

Un outil ne doit pas faire plusieurs choses implicites.

Bon exemple:

- `LaunchPreset`
- `GetProjectionSummary`
- `GetLocalSummary`
- `GetRecentConsoleErrors`

Mauvais exemple:

- `FixHydrologyAndRetest`

### 2. Les sorties doivent etre structurees

Chaque outil doit retourner des donnees exploitables par un humain et par un agent.

Format recommande:

- `success`
- `message`
- `data`
- `warnings`

### 3. Les outils de lecture avant les outils d'action

Ordre recommande:

1. lecture d'etat
2. lancement de scenario
3. capture d'artefacts
4. actions debug locales bornees

## Architecture recommandee

### Couche 1 - Runtime facade Terraformation

Ajouter un petit ensemble de services runtime ou Editor exposes explicitement.

Responsabilites:

- centraliser les actions de debug deja presentes
- eviter d'appeler les composants UI ou scene de maniere ad hoc
- fournir des DTO simples a serialiser

Types recommandes:

- `TerraformationDebugFacade`
- `ProjectionSummaryDto`
- `LocalRegionSummaryDto`
- `ConsoleSnapshotDto`
- `ViewStateDto`
- `PresetLaunchRequest`

### Couche 2 - Bridge Unity / outils

Deux options viables:

- outils Unity MCP custom
- API locale HTTP minimale si MCP n'est pas encore pret

Recommandation:

- viser Unity MCP comme cible finale
- accepter une facade interne testable avant l'exposition MCP

## Bridge HTTP local actuellement disponible

Le serveur MCP est opérationnel. Il se compose de deux couches :

### Couche 1 — Bridge HTTP Unity (`RuntimeDebugHttpServer.cs`)

Exposé automatiquement en Play mode sur `http://127.0.0.1:48621/`.

Condition de disponibilité :
- Unity doit être en Play mode
- le log `[RuntimeDebugHttpServer] Started on http://127.0.0.1:48621/` doit apparaître dans la console Unity
- le serveur force `Application.runInBackground = true` pendant son cycle de vie

### Couche 2 — Serveur MCP FastMCP (Docker)

- Fichiers : `Mcp/server.py`, `Mcp/Dockerfile`, `docker-compose.yml`
- Transport : `streamable-http` sur `http://0.0.0.0:8000/mcp`
- VS Code : `.vscode/mcp.json` → `type: http`, `url: http://localhost:8000/mcp`

Démarrer depuis la racine :
```bash
docker compose up -d
```

Démarrer depuis le sous-projet :
```bash
cd Mcp
docker compose up -d
```

Le compose racine est la stack canonique et démarre maintenant ensemble `terraformation-dedicated-server` et `terraformation-mcp`.
Le compose du sous-projet `Mcp/` n'est plus qu'un wrapper vers cette définition racine.

Variables d'environnement :
- `GAME_BRIDGE_URL` : URL du bridge Unity (défaut `http://host.docker.internal:48621`)
- `MCP_PORT` : port du serveur MCP (défaut `8000`)
- `SIMULATION_SERVER_URL` : URL du serveur de simulation; par défaut la résolution inter-service de la stack canonique (`http://terraformation-dedicated-server:8080`)

### Limite actuelle

Le serveur FastMCP Docker parle aujourd'hui principalement au bridge Unity local. C'est adapté au debug et au test en Play Mode, mais ce n'est pas la cible finale des tools métier quand la simulation sera hébergée hors Unity.

`Tools/mcp` reste présent seulement comme shim legacy, mais ne doit plus être traité comme la source principale.

### Évolution cible

À terme, il faut distinguer deux familles de tools :

- `debug-client` : captures, vue courante, projection affichée, région locale affichée, console, screenshots
- `simulation-server` : état autoritaire, commandes de gameplay, smoke tests métier, diagnostics de cohérence, comparaison de presets

### État désormais atteint

Le serveur MCP a maintenant un découpage fonctionnel initial entre ces deux familles :

- les tools visuels et client continuent à interroger le bridge Unity
- les snapshots métier structurés (`WorldState`, `ProjectionState`, `RegionState`) et certaines actions de simulation passent par `DedicatedServer`

En pratique :

- Unity reste la source pour `get_view_state`, `get_projection_summary`, `get_local_summary`, `get_client_snapshot`, `get_console_errors`, `take_screenshot`, `launch_preset`, `open_region`
- le serveur dédié devient la source pour `get_projection_state`, `get_region_state`, `get_world_state`, `get_last_simulation_event`, `get_server_action_definitions`, `advance_simulation_tick`, `open_server_region`, `queue_server_terraform_action`, `apply_server_cell_delta`

Ce n'est pas encore la cible finale, mais la séparation des responsabilités est maintenant visible dans le MCP lui-même.

### Contrats déjà posés côté runtime Unity

Une première version des contrats partagés a été ajoutée dans le runtime pour préparer l'extraction du host :

- `ProjectionState`
- `RegionState`
- `WorldState`
- `ClientSnapshot`
- `SimulationCommand`
- `SimulationEvent`

Le bridge HTTP local expose maintenant aussi ces snapshots structurés :

- `/debug/projection-state`
- `/debug/region-state`
- `/debug/world`
- `/debug/client`

Ces endpoints restent servis par Unity aujourd'hui, mais les formes JSON doivent servir de base à la future API du `Simulation Host`.

Workflow de vérification :
1. `docker compose up -d` → conteneur `terraformation-mcp` démarré
2. Lancer Unity en Play mode → `RuntimeDebugHttpServer` démarre sur 48621
3. Depuis Copilot Chat : appeler `get_view_state` → retourne le JSON d'état Unity

## Endpoints HTTP du bridge

### 1. GET /debug/state

#### But

Retourner l'etat runtime courant du flow de vues.

#### Parametres

- aucun

#### Reponse

- `currentView`
- `activePlanetName`
- `activeProjectionOverride`
- `activeProjectionWaterLevel`
- `hasRegion`
- `regionLatitude`
- `regionLongitude`
- `hasSelectedCell`
- `selectedCellQ`
- `selectedCellR`
- `terraformationProgress`
- `localCellCount`

#### Exemple

- `http://127.0.0.1:48621/debug/state`

### 2. GET /debug/projection

#### But

Retourner un resume structure de la projection active.

#### Parametres

- aucun

#### Reponse

- `isValid`
- `activePlanetName`
- `activeProjectionOverride`
- `activeProjectionWaterLevel`
- `gridSummary`

#### Exemple

- `http://127.0.0.1:48621/debug/projection`

### 3. GET /debug/local

#### But

Retourner le resume de la region locale active.

#### Parametres

- aucun

#### Reponse

- `isValid`
- `activePlanetName`
- `regionLatitude`
- `regionLongitude`
- `coherenceOceanicity`
- `coherenceDeserticity`
- `coherenceFrigidity`
- `projectedWaterRatio`
- `terraformationProgress`
- `hasSelectedCell`
- `selectedCellQ`
- `selectedCellR`
- `gridSummary`

#### Exemple

- `http://127.0.0.1:48621/debug/local`

### 4. GET /debug/console

#### But

Lire les logs recents captures par la facade runtime.

#### Parametres

- `maxEntries` optionnel, defaut `20`
- `minimumSeverity` optionnel, defaut `Warning`

#### Reponse

- `isValid`
- `totalEntries`
- `logCount`
- `warningCount`
- `errorCount`
- `exceptionCount`
- `entries`

#### Exemples

- `http://127.0.0.1:48621/debug/console`
- `http://127.0.0.1:48621/debug/console?maxEntries=50&minimumSeverity=Error`

### 5. GET /debug/screenshot

#### But

Demander une capture d'ecran runtime dans `Application.persistentDataPath/DebugCaptures`.

#### Parametres

- `fileName` optionnel
- `superSize` optionnel, defaut `1`

#### Reponse

- `success`
- `filePath`
- `message`

#### Exemples

- `http://127.0.0.1:48621/debug/screenshot`
- `http://127.0.0.1:48621/debug/screenshot?fileName=coast_projection&superSize=2`

### 6. GET /debug/launch-preset

#### But

Lancer un preset debug par son nom affiche ou son nom d'asset.

#### Parametres

- `preset` requis

#### Reponse

- `success`
- `message`
- `state`

#### Exemples

- `http://127.0.0.1:48621/debug/launch-preset?preset=Coast`
- `http://127.0.0.1:48621/debug/launch-preset?preset=Basin`

### 7. GET /debug/open-region

#### But

Ouvrir une region locale sans clic manuel sur la projection.

#### Parametres

- `lat` optionnel, defaut `0.5`
- `lon` optionnel, defaut `0.5`

#### Reponse

- `success`
- `message`
- `state`

#### Exemples

- `http://127.0.0.1:48621/debug/open-region?lat=0.42&lon=0.67`

## Workflow minimal de verification

Sequence recommandee pour verifier rapidement le bridge:

1. `docker compose up -d` (si pas déjà démarré)
2. entrer en Play mode dans Unity
3. verifier le log de demarrage HTTP dans la console Unity
4. depuis Copilot Chat, appeler `get_view_state`
5. lancer un preset : appeler `launch_preset` avec `preset_name="Coast"`
6. relire `get_view_state`
7. lire `get_projection_summary`
8. ouvrir une region : appeler `open_region` avec `latitude=0.42`, `longitude=0.67`
9. lire `get_local_summary`
10. lire `get_console_errors`

Automatisation disponible:

- script PowerShell `Tools/Invoke-TerraformationDebugSmokeTest.ps1`
- il encapsule la sequence standard de verification du bridge local
- il peut cibler un preset, des coordonnees explicites et un dossier d'artefacts JSON

---

## Roadmap d'expansion MCP

### Périmètre de responsabilité

**GitHub Copilot est en charge du MCP et de l'API du jeu.**
Toutes les décisions d'architecture, d'exposition d'endpoints et de tools MCP passent par cette couche.

---

### Axe 1 — Debug et validation semi-automatisée (Sprint A → B)

Objectif : permettre à l'agent AI de lire, diagnostiquer et valider les comportements du jeu sans intervention manuelle systématique.

#### Tools déjà disponibles (Sprint 0)

| Tool MCP | Endpoint Unity | Usage |
|---|---|---|
| `get_view_state` | `/debug/state` | état courant de la vue |
| `get_projection_summary` | `/debug/projection` | résumé projection planétaire |
| `get_local_summary` | `/debug/local` | résumé région locale + hydrologie |
| `get_console_errors` | `/debug/console` | logs Unity filtrés par sévérité |
| `take_screenshot` | `/debug/screenshot` | capture scène en jeu |
| `launch_preset` | `/debug/launch-preset` | lancement de preset debug |
| `open_region` | `/debug/open-region` | navigation vers une région |

#### Tools à ajouter (Sprint A → B)

| Tool MCP | Endpoint Unity à créer | Usage |
|---|---|---|
| `get_cell_detail` | `/debug/cell?q=&r=` | infos complètes d'un hexagone (terrain, eau, biome, température, flow) |
| `set_cell_override` | POST `/debug/cell` | modifier un hex en runtime pour tests de régression |
| `get_hydrology_stats` | `/debug/hydrology` | métriques agrégées : bassins, côtes, flux max, overflow |
| `run_validation` | `/debug/validate` | déclencher `CoherenceValidationSystem` et retourner les warnings |

#### Règles de conception pour ces ajouts

- Toujours read-only par défaut — les writes sont nommés explicitement (`set_`, `apply_`)
- Chaque endpoint retourne `{ "success": bool, "message": string, "data": {...} }`
- Pas d'effet de bord implicite : `run_validation` ne modifie pas l'état, il ne fait que lire

---

### Axe 2 — Automatisation de tests (Sprint B → C)

Objectif : l'agent peut lancer un preset, lire les résultats, comparer aux critères de la checklist et signaler les regressions — sans ouvrir Unity.

#### Séquence type (à implémenter dans un skill ou un script)

```
launch_preset("Coast")
→ get_view_state()           # confirmer currentView = Local
→ get_local_summary()        # lire coastCells, openOceanCells
→ comparer à TEST_PRESETS_CHECKLIST critères SA-1
→ get_console_errors()       # vérifier absence d'erreurs
→ take_screenshot()          # archiver artefact visuel
```

Cette boucle peut être exécutée pour les 5 presets (Coast, Ocean, Arid, Frozen, Basin) en séquence automatisée.

#### Artefacts à produire

- JSON de résultats par preset dans `Artifacts/<PresetName>/`
- Screenshot par preset (déjà supporté)
- Rapport de delta entre run (à construire côté agent)

---

### Axe 3 — API Gameplay (Phase 7 → 10)

Objectif : exposer l'état du jeu en cours (corporations, marché, événements) à l'agent AI et à des clients externes (UI web, spectateur, bots IA).

Ces tools seront ajoutés à `RuntimeDebugFacade` puis à un futur `GameplayAPIServer` quand le multijoueur arrivera.

#### Lot Gameplay prévu

| Tool MCP | But |
|---|---|
| `get_corporation_state` | solde, hexes possédés, score, bâtiments |
| `get_market_state` | prix des ressources, volume d'échanges par tick |
| `get_active_events` | événements en cours + effets actifs |
| `get_tick_state` | numéro de tick, vitesse, pause |
| `get_planet_overview` | couverture terraformation globale par zone |

#### Règles pour la couche gameplay

- Les writes (claim hex, acheter ressource) passent par le serveur Mirror, jamais directement par l'API debug
- L'API HTTP reste un canal de lecture + commandes admin délibérées (pas de gameplay automatisé implicite)
- Toute action destructive (reset planète, kick joueur) doit passer par un outil nommé explicitement et retourner une confirmation avant exécution

---

### Axe 4 — Architecture future (Phase 10+)

Quand Unity Dedicated Server (headless Linux) sera containerisé :

| Composant | Rôle |
|---|---|
| `GameAPIServer.cs` | remplace `RuntimeDebugHttpServer` en mode serveur — expose HTTP/WebSocket |
| `docker-compose.yml` | conteneur Unity headless + conteneur MCP + conteneur Firebase sync |
| Serveur MCP FastMCP | inchangé — pointe vers `http://unity-server:48621` au lieu de `host.docker.internal` |
| `.vscode/mcp.json` | inchangé côté VS Code |

La bascule `GAME_BRIDGE_URL` dans `docker-compose.yml` suffit à rediriger le MCP vers le serveur dédié sans modifier le serveur MCP lui-même.

Commande type:

- `powershell -ExecutionPolicy Bypass -File .\Tools\Invoke-TerraformationDebugSmokeTest.ps1 -Preset Basin -OutputDirectory .\Artifacts\Basin`

## Limites actuelles

- le bridge est local uniquement sur `127.0.0.1`
- il repose sur Unity en Play mode
- les actions HTTP sont bornees aux lectures et actions debug deja encapsulees par `RuntimeDebugFacade`
- un adaptateur MCP PowerShell minimal existe maintenant dans `Tools/TerraformationDebugMcp.ps1`
- cet adaptateur reste dependant du bridge HTTP local et donc du Play mode

## Adaptateur MCP local disponible

Le workspace expose maintenant un serveur MCP local `terraformation-debug` dans `.vscode/mcp.json`.

Implementation:

- script `Tools/TerraformationDebugMcp.ps1`
- transport stdio
- forwarding direct vers les endpoints HTTP du bridge runtime

Usage:

1. lancer Unity en Play mode
2. verifier que `GET /debug/state` repond ou que le smoke test passe
3. demarrer le serveur MCP `terraformation-debug` depuis le client compatible MCP

Tools exposes actuellement:

- `get_view_state`
- `launch_preset`
- `get_projection_summary`
- `open_region`
- `get_local_summary`
- `get_console_errors`
- `take_screenshot`
- `get_generation_stats`
- `get_generation_noise_distribution`
- `run_generation_quality_suite`
- `compare_generation_profiles`
- `run_preset_smoke_test`
- `compare_presets`
- `diagnose_hydrology_mismatch`

Contraintes actuelles:

- aucune logique metier supplementaire dans l'adaptateur
- erreurs reseau ou Play mode renvoyees comme erreurs d'outil
- mapping principalement 1:1 entre tools MCP et endpoints HTTP
- exception utile: `run_preset_smoke_test` compose les appels existants via le script `Tools/Invoke-TerraformationDebugSmokeTest.ps1`

### Tool compose disponible

`get_generation_stats` permet d'interroger directement le `DedicatedServer` pour lire la signature d'un preset/profil de generation sans lancer Unity.

Sorties utiles:

- distribution `terrain`
- distribution `terrain_class`
- distribution `water_classification`
- metriques `quality` (`dry_pct`, `humid_pct`, `saturated_pct`, `habitable_pct`, `cold_pct`, `hot_pct`)
- temperature moyenne/min/max

Usage recommande:

1. utiliser `get_generation_stats` avant toute retouche de `logic.py`
2. comparer explicitement Coast, Ocean, Arid, Frozen et Basin apres chaque changement serveur
3. n'utiliser Unity qu'en confirmation visuelle, pas comme premier oracle de tuning

`get_generation_noise_distribution` permet d'inspecter la distribution du bruit H3/hash quand un seuil ou un preset semble se comporter de maniere contre-intuitive.

Usage recommande:

1. l'utiliser quand un preset repond mal a un changement de seuil sans explication evidente
2. verifier si la distribution est plate ou biaisee avant de retoucher les classifications

`run_generation_quality_suite` est l'equivalent MCP de `Tools/Test-GenerationQuality.ps1`.
Il execute les 5 profils de reference cote serveur et retourne un verdict structure avec checks et failures.

Usage recommande:

1. le lancer juste apres une modification de `SimulationCore/terraformation_sim/logic.py`
2. traiter le resultat comme garde-fou de tuning avant les smoke tests Unity
3. s'en servir comme base pour une future automatisation Docker/CI

`compare_generation_profiles` permet de comparer deux profils serveur directement sur les metriques de qualite sans passer par Unity ni par les smoke tests visuels.

Sorties utiles:

- `resultA` et `resultB`
- `delta` par metrique (`dryPct`, `openOceanPct`, `vegetationPct`, `basinPct`, etc.)

Usage recommande:

1. l'utiliser quand deux presets semblent trop proches ou mal differencies
2. s'en servir avant `compare_presets` pour savoir si le probleme est deja visible cote serveur

`run_preset_smoke_test` permet de lancer un scenario complet de validation preset et de recuperer:

- le succes global
- le code de sortie
- le dossier d'artefacts
- le chemin du resume JSON
- le resume complet
- le verdict structure avec checks, warnings et failures

Usage recommande:

1. utiliser les tools unitaires pour le debug interactif
2. utiliser `run_generation_quality_suite` pour valider rapidement la projection serveur sans Unity
3. utiliser `compare_generation_profiles` si deux presets doivent etre contrastes cote serveur
4. utiliser `run_preset_smoke_test` pour une verification reproductible Ocean, Coast, Basin, Arid ou Frozen
5. s'appuyer sur `verdict` avant de conclure qu'un preset est sain

`compare_presets` permet de lancer deux smoke tests et de recuperer un delta structure entre deux presets.

Sorties utiles:

- succes global de la comparaison
- resultats individuels gauche et droite
- dossier d'artefacts de comparaison
- metriques de projection comparees
- metriques locales comparees
- compteurs console compares

Usage recommande:

1. utiliser `run_preset_smoke_test` pour valider un preset seul
2. utiliser `compare_presets` pour repondre a des questions du type `Coast vs Ocean`, `Basin vs Ocean`, `Frozen vs Arid`
3. s'appuyer sur les deltas pour detecter si deux presets sont trop proches ou si un preset ne differencie pas assez son comportement

`diagnose_hydrology_mismatch` permet de lancer un preset et de retourner une lecture plus metier du resultat.

Sorties utiles:

- `primaryMismatch`
- liste structuree de `findings`
- `likelySubsystems`
- `verdict` du smoke test sous-jacent
- artefacts et resume complets du smoke test utilise

Usage recommande:

1. utiliser `run_preset_smoke_test` pour savoir si un preset passe ou echoue
2. utiliser `compare_presets` pour mesurer les differences entre deux presets
3. utiliser `diagnose_hydrology_mismatch` quand le probleme porte sur l eau, les bassins, les rivieres, la coherence macro-vers-micro ou les faux positifs biome/hydrologie

## Tranche MCP suivante recommandee

La prochaine etape utile n'est pas de reimplementer la logique debug une seconde fois, mais de durcir cet adaptateur MCP minimal.

Outils MCP a exposer en premier:

- `GetCurrentViewState` -> `GET /debug/state`
- `LaunchPreset` -> `GET /debug/launch-preset?preset=...`
- `GetProjectionSummary` -> `GET /debug/projection`
- `OpenRegion` -> `GET /debug/open-region?lat=...&lon=...`
- `GetLocalSummary` -> `GET /debug/local`
- `GetRecentConsoleErrors` -> `GET /debug/console`
- `CaptureSceneScreenshot` -> `GET /debug/screenshot`

Contraintes d'implementation:

- conserver les memes noms de champs que les DTO runtime actuels
- ne pas ajouter de logique metier dans l'adaptateur MCP
- traiter le bridge HTTP comme source de verite pour le runtime debug
- garder l'echec explicite si Unity n'est pas en Play mode ou si le bridge ne repond pas

Ordre d'implementation recommande:

1. client HTTP local robuste
2. mapping des 7 outils MCP vers les 7 endpoints
3. normalisation des erreurs reseau et Play mode
4. commandes de smoke test automatiques sur Ocean, Coast et Basin
5. ajout eventuel d'un outil compose type `RunPresetSmokeTest`

### Couche 3 - Client AI

Le client AI consomme les outils sans connaitre les details scene/UI.

Il doit pouvoir enchainer:

1. `GetCurrentViewState`
2. `LaunchPreset`
3. `GetProjectionSummary`
4. `OpenRegion`
5. `GetLocalSummary`
6. `GetRecentConsoleErrors`
7. `CaptureSceneScreenshot`

## Premier lot d'outils recommandes

### 1. GetCurrentViewState

#### But

Savoir dans quelle vue on se trouve et quel contexte est actif.

#### Entree

- aucune

#### Sortie

- vue active
- planete active
- niveau d'eau projete
- override actif
- region ouverte si presente
- cellule selectionnee si presente

#### Sources Unity

- `ViewManager`
- `TerraformHUD`

### 2. LaunchPreset

#### But

Lancer un preset debug de facon reproductible.

#### Entree

- nom preset ou identifiant
- override optionnel lat/lon
- `openLocalView` optionnel

#### Sortie

- preset reellement lance
- vue d'arrivee
- planete active
- warnings si preset introuvable ou incomplet

#### Sources Unity

- `TestScenarioPreset`
- `ViewManager`

### 3. OpenRegion

#### But

Ouvrir explicitement une region locale sans passer par un clic manuel.

#### Entree

- latitude
- longitude

#### Sortie

- succes/echec
- region context
- vue active

#### Sources Unity

- `ViewManager.TryOpenRegionNormalized()`

### 4. GetProjectionSummary

#### But

Retourner un resume structure de la projection en cours.

#### Entree

- aucune si une projection est deja active
- optionnellement `body`, `override`, `waterLevelOffset` si on veut regen avant lecture

#### Sortie

- dimensions projection
- counts par `WaterClassification`
- counts par `TerrainType`
- eau moyenne
- temperature moyenne si disponible
- screenshot optionnelle

#### Sources Unity

- `PlanetSphere`
- `PlanetaryHexGrid`
- futur helper de resume projection

### 5. GetLocalSummary

#### But

Retourner le resume agregé local deja expose par `HexGridDebugSummary`.

#### Entree

- aucune si une region est deja ouverte

#### Sortie

- toutes les stats de `HexGridDebugSummary`
- coherence locale
- infos region et planete

#### Sources Unity

- `HexGrid.TryBuildDebugSummary()`
- `TerraformHUD.RegionContext`

### 6. GetRecentConsoleErrors

#### But

Identifier rapidement si le scenario a produit des erreurs ou warnings importants.

#### Entree

- severite minimum optionnelle
- nombre maximum d'entrees

#### Sortie

- liste structuree des logs
- severite
- timestamp
- message
- stack optionnelle

#### Sources Unity

- pont a construire sur la collecte console Editor/PlayMode

### 7. CaptureSceneScreenshot

#### But

Produire un artefact visuel du resultat.

#### Entree

- nom fichier
- vue cible optionnelle
- mode de capture optionnel

#### Sortie

- chemin fichier
- metadata de capture

#### Sources Unity

- screenshot runtime ou outil de capture scene

### 8. ApplyDebugCellAdjustment

#### But

Appliquer une modification limitee et observable a une cellule.

#### Entree

- q
- r
- waterDelta
- temperatureDelta

#### Sortie

- etat cellule avant
- etat cellule apres
- succes/echec

#### Sources Unity

- `TerraformSystem.DebugApplyDirectState()`
- `HexGrid.GetCell()`

### 9. RegenerateCurrentLocalRegion

#### But

Relancer la region locale et recuperer l'etat apres regen.

#### Entree

- aucune

#### Sortie

- succes/echec
- nouveau summary local

#### Sources Unity

- `ViewManager.RegenerateCurrentLocalRegion()`

## DTO recommandes

### ViewStateDto

- `currentView`
- `activePlanet`
- `activeProjectionOverride`
- `activeProjectionWaterLevel`
- `regionLatitude`
- `regionLongitude`
- `selectedCellQ`
- `selectedCellR`

### ProjectionSummaryDto

- `cols`
- `rows`
- `totalCells`
- `openOceanCells`
- `coastCells`
- `inlandWaterCells`
- `frozenWaterCells`
- `dryCells`
- `averageWaterRatio`
- `terrainCounts`

### LocalRegionSummaryDto

- `totalCells`
- `dryCells`
- `coastCells`
- `inlandWaterCells`
- `openOceanCells`
- `frozenWaterCells`
- `ridgeCells`
- `basinCells`
- `channelCells`
- `sourceCells`
- `riverCells`
- `downstreamCells`
- `overflowCells`
- `averageWaterRatio`
- `averageTemperature`
- `maxFlowAccumulation`
- `coherenceOceanicity`
- `coherenceDeserticity`
- `coherenceFrigidity`

## Garde-fous

### Outils safe par defaut

Le premier lot doit privilegier:

- lecture
- navigation
- captures
- petites actions debug reversibles

### Outils a ne pas exposer d'abord

- suppression d'assets
- edition libre de scene
- modifications de masse sans previsualisation
- actions gameplay irreversibles complexes

## Ordre de mise en oeuvre recommande

### Sprint 1

- facade debug runtime
- `GetCurrentViewState`
- `LaunchPreset`
- `OpenRegion`
- `GetLocalSummary`

### Sprint 2

- `GetProjectionSummary`
- `GetRecentConsoleErrors`
- `CaptureSceneScreenshot`

### Sprint 3

- `ApplyDebugCellAdjustment`
- `RegenerateCurrentLocalRegion`
- `RunViewFlowSmokeTest`

## Definition de done du premier lot

Le premier lot sera considere pret quand un agent externe pourra:

1. lancer `Coast` ou `Basin`
2. lire le resume projection
3. ouvrir une region locale
4. lire le resume local
5. lire la console
6. faire une capture
7. produire un rapport simple de succes ou regression

## Lien avec le reste du projet

Ce lot n'est pas un chantier secondaire. Il sert directement a:

- accelerer le debug de Phase 6.5
- fiabiliser les presets et la coherence projection/local
- preparer la persistance regionale et les futures regressions gameplay