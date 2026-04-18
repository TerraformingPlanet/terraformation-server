# Workflow AI & Debug - Terraformation

## Objet

Ce document definit comment utiliser l'assistance AI dans Terraformation sans melanger debug, experimentation et modifications dangereuses.

L'objectif n'est pas d'avoir une IA qui improvise dans le projet, mais une boucle de travail rapide, reproductible et comprehensible par toute l'equipe.

## Principes

### 1. Toujours separer analyse et action

- Utiliser le mode lecture pour comprendre un bug, relire l'etat du projet, ou comparer des comportements.
- Utiliser le mode action seulement quand l'objectif est clair et que le perimetre de changement est limite.

### 2. Les outils de debug doivent etre deterministes

Un bon outil AI pour Terraformation doit repondre a une question precise et retourner un resultat stable.

Exemples de bonnes questions:

- quelle vue est active ?
- quelle planete est chargee ?
- combien de cellules `OpenOcean` ont ete generees ?
- quelle est la coherence locale de la region ouverte ?
- y a-t-il des erreurs console depuis le dernier lancement de preset ?

Exemples de mauvaises questions:

- joue un peu et vois si ca a l'air bon
- modifie des trucs au hasard pour rendre la carte plus jolie
- essaye plusieurs changements jusqu'a ce que ca marche

### 3. Les verifications doivent produire des artefacts

Chaque passe utile de debug doit si possible produire au moins un des artefacts suivants:

- stats locales ou projection
- screenshot
- resume console
- resultat avant/apres
- checklist de validation

## Workflow recommande

### Etape 1 - Choisir un scenario de reference

Avant de demander une analyse ou une action, choisir explicitement un preset ou un flow:

- Ocean
- Arid
- Frozen
- Coast
- Basin
- SolarSystem -> Planet -> Local

### Etape 2 - Choisir le type de session

#### Session A - Analyse pure

Objectif:

- comprendre un comportement
- lire les donnees
- comparer projection et local

Entrants utiles:

- nom du preset
- lat/lon
- capture ou stats existantes
- description du bug observe

Sortants attendus:

- hypothese technique
- liste des fichiers a relire
- liste des metriques a verifier

#### Session B - Debug guide

Objectif:

- lancer une sequence de verification reproductible

Sortants attendus:

- etapes exactes a rejouer
- criteres de succes/echec
- mesures ou screenshots a collecter

#### Session C - Action encadree

Objectif:

- modifier un comportement cible apres diagnostic

Contraintes:

- une seule zone fonctionnelle a la fois
- validation compile systematique
- si possible, verification manuelle ou outillage associee

## Boucles de debug recommandees

## Workflow HTTP runtime recommande

Quand le bridge local est disponible, preferer une sequence courte et deterministe plutot qu'une navigation manuelle libre.

Preconditions:

- Unity en Play mode
- log de demarrage `RuntimeDebugHttpServer` visible dans la console
- base URL `http://127.0.0.1:48621`

Sequence de base:

1. lire `GET /debug/state`
2. lancer un preset avec `GET /debug/launch-preset?preset=...`
3. relire `GET /debug/state`
4. lire `GET /debug/projection`
5. ouvrir une region avec `GET /debug/open-region?lat=...&lon=...` si le preset ne l'a pas deja fait de la bonne maniere
6. lire `GET /debug/local`
7. lire `GET /debug/console`
8. demander une capture avec `GET /debug/screenshot?fileName=...`

Artefacts minimaux a conserver:

- payload `/debug/state` avant et apres lancement
- payload `/debug/projection`
- payload `/debug/local` si region ouverte
- payload `/debug/console`
- screenshot si le rendu visuel fait partie du diagnostic

Automatisation disponible:

- script PowerShell `Tools/Invoke-TerraformationDebugSmokeTest.ps1`
- ce script execute la sequence standard `state -> launch preset -> projection -> open region -> local -> console -> screenshot`
- il peut ecrire les reponses JSON dans un dossier d'artefacts via `-OutputDirectory`

### Boucle 1 - Bug de projection

1. lancer un preset projection only ou ouvrir la vue planete
2. capturer le resume projection
3. verifier la distribution `OpenOcean / Coast / InlandWater / Dry / FrozenWater`
4. comparer au rendu visuel
5. inspecter `PlanetaryHexGrid`, `PlanetSphere`, `PlanetTextureGenerator`, `MapRegion`

Sequence HTTP equivalente:

1. `GET /debug/launch-preset?preset=Coast`
2. `GET /debug/projection`
3. `GET /debug/console?minimumSeverity=Warning`
4. `GET /debug/screenshot?fileName=projection_coast`

### Boucle 2 - Bug local hydrologie

1. ouvrir la region locale
2. lire `HexGridDebugSummary`
3. selectionner une cellule representative
4. comparer HUD cellule et resume de region
5. inspecter `WaterSystem`, `HydrologySystem`, `WaterClassificationSystem`, `RiverSystem`, `BiomeSystem`

Sequence HTTP equivalente:

1. `GET /debug/launch-preset?preset=Basin`
2. `GET /debug/open-region?lat=0.57&lon=0.58`
3. `GET /debug/local`
4. `GET /debug/console?minimumSeverity=Warning`
5. `GET /debug/screenshot?fileName=local_basin`

### Boucle 3 - Bug de flow de vues

1. lancer le flow `SolarSystem -> Planet -> Local`
2. verifier `ESC`, `F9`, `F10`
3. verifier la preservation des overrides et du niveau d'eau projete
4. inspecter `ViewManager`, `TestLaunchMenu`, `DebugHydrologyPanel`, `TerraformHUD`

Sequence HTTP equivalente:

1. `GET /debug/state`
2. `GET /debug/launch-preset?preset=Ocean`
3. `GET /debug/state`
4. `GET /debug/open-region?lat=0.50&lon=0.50`
5. `GET /debug/state`
6. retour manuel via `ESC`
7. `GET /debug/state`

## Scenarios reproductibles par preset

### Ocean

Sequence conseillee:

1. `GET /debug/launch-preset?preset=Ocean`
2. `GET /debug/projection`
3. `GET /debug/open-region?lat=0.50&lon=0.50`
4. `GET /debug/local`
5. `GET /debug/console?minimumSeverity=Warning`

Points a verifier:

- `gridSummary.openOceanCells` doit etre dominant sur la projection
- `gridSummary.averageWaterRatio` doit etre eleve localement
- les warnings ou erreurs ne doivent pas expliquer un rendu incoherent

### Arid

Sequence conseillee:

1. `GET /debug/launch-preset?preset=Arid`
2. `GET /debug/projection`
3. `GET /debug/open-region?lat=0.52&lon=0.52`
4. `GET /debug/local`
5. `GET /debug/console?minimumSeverity=Warning`

Points a verifier:

- `dryCells` doit dominer projection et local
- `riverCells` doit rester faible localement
- le preset ne doit pas produire des masses d'eau ouvertes absurdes

### Frozen

Sequence conseillee:

1. `GET /debug/launch-preset?preset=Frozen`
2. `GET /debug/projection`
3. `GET /debug/open-region?lat=0.20&lon=0.50`
4. `GET /debug/local`
5. `GET /debug/console?minimumSeverity=Warning`

Points a verifier:

- `frozenWaterCells` doit etre visible dans les resumes
- la temperature moyenne locale doit etre basse
- la vegetation ne doit pas dominer sans raison

### Coast

Sequence conseillee:

1. `GET /debug/launch-preset?preset=Coast`
2. `GET /debug/projection`
3. `GET /debug/open-region?lat=0.47&lon=0.18`
4. `GET /debug/local`
5. `GET /debug/screenshot?fileName=coast_validation`

Points a verifier:

- `coastCells` doit etre visible sur projection et local
- la transition eau vers terre doit etre lisible
- la projection ne doit etre ni integralement bleue ni integralement marron

### Basin

Sequence conseillee:

1. `GET /debug/launch-preset?preset=Basin`
2. `GET /debug/projection`
3. `GET /debug/open-region?lat=0.57&lon=0.58`
4. `GET /debug/local`
5. `GET /debug/screenshot?fileName=basin_validation`

Points a verifier:

- `inlandWaterCells` et `basinCells` doivent etre visibles
- un noyau d'eau interieure doit exister
- le rendu ne doit pas se confondre avec `Ocean` ou `None`

### ProjectionOnly

Sequence conseillee:

1. `GET /debug/state`
2. lancement manuel du preset projection only si necessaire
3. `GET /debug/projection`
4. `GET /debug/state`

Points a verifier:

- la projection se recharge sans perdre le contexte runtime
- `hasRegion` reste faux tant qu'aucune region n'est ouverte
- la lecture de projection reste disponible sans ouverture locale

## Questions AI utiles par type de probleme

### Projection

- compare les presets Ocean et Coast sur la projection et liste les differences attendues
- resume comment `PlanetaryHexGrid` decide eau, cote, roche et glace
- liste les endroits ou un override debug peut etre perdu entre menu, vue planete et region locale

### Hydrologie locale

- explique pourquoi une region locale classifie trop de cellules en `Dry`
- montre les biais de coherence appliques a l'eau et aux biomes
- quels seuils de `MapGenParameters` influencent le plus les bassins et les cotes ?

### UI / flow

- quelles transitions peuvent reinitialiser l'etat courant ?
- quelles dependances runtime sont necessaires pour que F9/F10 marchent correctement ?
- quel est l'ordre de refresh entre `ViewManager`, `HexGrid`, `TerraformHUD` et `DebugHydrologyPanel` ?

## Conventions d'usage pour l'equipe

### Quand utiliser l'AI

- pour resumer un sous-systeme complexe
- pour preparer une verification manuelle
- pour rediger une doc de debug ou de regression
- pour appliquer un changement cible apres analyse

### Quand ne pas utiliser l'AI seule

- pour valider un rendu final sans mesure
- pour conclure qu'un bug est regle sans verification runtime
- pour modifier plusieurs sous-systemes critiques en meme temps

## Artefacts de reference a maintenir

Ces artefacts doivent rester a jour pour que l'AI soit vraiment utile:

- `Documentation/ARCHITECTURE.md`
- `Documentation/ROADMAP.md`
- `Documentation/SIMULATION_CONTRACTS.md`
- `Documentation/MCP_TOOLS_ARCHITECTURE.md`
- `Documentation/TEST_PRESETS_CHECKLIST.md`
- script de smoke test HTTP du bridge local
- futurs outils MCP Terraformation

---

## Protocole de mise à jour documentaire

La documentation ne se met pas à jour automatiquement. Ce protocole définit **quand** et **avec quel agent** déclencher une mise à jour.

### Agents disponibles

| Agent | Rôle |
|---|---|
| **Doc Terraformation** | Met à jour GDD, ARCHITECTURE, ROADMAP, CHANGELOG — décisions, tâches, phases |
| **Terraformation Dev** | Code C#/Python, Unity, MCP, serveur — met à jour SIMULATION_CONTRACTS, MCP_TOOLS_ARCHITECTURE en même temps que le code |

### Déclencheurs obligatoires

Ces événements **doivent** déclencher une mise à jour documentaire avant de passer à la tâche suivante.

| Événement | Action | Agent |
|---|---|---|
| Sprint ou phase marqué terminé | Déplacer les tâches `✅` vers `CHANGELOG.md`, réduire `ROADMAP.md` | **Doc Terraformation** |
| Décision d'architecture prise | Ajouter une entrée dans la section "Décisions d'Architecture" de `ARCHITECTURE.md` | **Doc Terraformation** |
| Nouveau type partagé Python ↔ C# | Ajouter la ligne dans `SIMULATION_CONTRACTS.md` (les deux colonnes) | **Terraformation Dev** (dans le même contexte que le changement de code) |
| Nouveau tool MCP ajouté ou modifié | Mettre à jour la table dans `MCP_TOOLS_ARCHITECTURE.md` | **Terraformation Dev** |
| Nouveau endpoint DedicatedServer | Mettre à jour `MCP_TOOLS_ARCHITECTURE.md` et `ARCHITECTURE.md` (table backend) | **Terraformation Dev** |

### Déclencheurs recommandés

Ces événements devraient idéalement déclencher une mise à jour, mais ne bloquent pas le travail en cours.

| Événement | Action | Agent |
|---|---|---|
| Session de smoke test complète | Archiver les artéfacts dans `Artifacts/SmokeTests/`, noter les anomalies dans `TEST_PRESETS_CHECKLIST.md` | **Doc Terraformation** |
| Début d'un nouveau sprint | Vérifier que `ROADMAP.md` reflète le backlog réel | **Doc Terraformation** |
| Divergence détectée Python ↔ C# | Mettre à jour `SIMULATION_CONTRACTS.md` et noter le risque | **Terraformation Dev** |

### Formule de déclenchement

Appeler **Doc Terraformation** avec :
```
marque la phase X comme terminée dans CHANGELOG et nettoie ROADMAP
```

Appeler **Terraformation Dev** avec :
```
j'ai ajouté [ChampY] à [TypeX] en Python — mets à jour SIMULATION_CONTRACTS et le C# miroir
```

### Ce qu'on ne fait pas

- On ne demande pas à un agent de "relire tout le projet et mettre à jour si nécessaire" — périmètre non borné, résultat imprévisible.
- On ne crée pas un agent par sous-projet — les changements sont presque toujours cross-projet.
- On ne reporte pas la mise à jour à "plus tard" après une décision d'architecture — le drift commence là.

## Definition de done pour une passe de debug AI

Une passe de debug est consideree utile si elle produit:

1. un diagnostic clair ou une hypothese testable
2. une liste de verifications ou de changements limites
3. au moins un artefact utile a l'equipe

## Prochaine etape naturelle

Le workflow de ce document suppose l'existence d'outils Terraformation simples et stables pour:

- lancer un preset
- capturer un resume projection
- capturer un resume local
- lire les erreurs console
- prendre un screenshot

Ces outils sont cadrés dans `Documentation/MCP_TOOLS_ARCHITECTURE.md`.

Commande type:

- `powershell -ExecutionPolicy Bypass -File .\Tools\Invoke-TerraformationDebugSmokeTest.ps1 -Preset Coast -CaptureScreenshot -OutputDirectory .\Artifacts\Coast`