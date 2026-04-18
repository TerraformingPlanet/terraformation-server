# Unity AI Assistant, Skills, MCP - Plan pour Terraformation

## Objet

Ce document cadre comment utiliser Unity AI Assistant 2.6 pour accelerer le debug, la creation d'outils internes, et une future boucle de test plus autonome dans Terraformation.

Il repond a trois questions:

1. Peut-on s'appuyer sur les skills Unity AI Assistant pour le projet ?
2. Faut-il creer des outils ou skills dedies au debug code et au debug gameplay ?
3. Peut-on aller jusqu'a une API ou un MCP pour laisser un agent lancer des tests, inspecter le jeu, voire jouer des scenarios ?

## Ce que dit la doc Unity AI Assistant 2.6

### 1. Ask mode et Agent mode

- Ask mode est lecture seule.
- Agent mode peut modifier le projet, avec permissions et confirmations.
- Pour Terraformation, Ask mode est adapte a l'analyse, Agent mode a l'automatisation dans l'Editor.

### 2. Skills

- Unity AI Assistant expose des skills comme modules specialises.
- En Ask mode, un skill guide et explique.
- En Agent mode, un skill peut appeler des outils et agir dans l'Editor.
- La doc publique 2.6 mentionne l'utilisation des skills, mais ne documente pas clairement un workflow simple et stable de creation de skills projet sur mesure equivalent a un package de skills custom complet.

Conclusion pratique:

- Il faut considerer les skills integres Unity comme une capacite exploitable.
- Pour les extensions specifiques Terraformation, le point d'extension concret et documente est surtout MCP et Unity MCP, pas un systeme de skills custom maison a grande echelle.

### 3. Automatisation

- Unity AI Assistant sait utiliser captures d'ecran et checkpoints.
- Il peut analyser des captures Profiler, mais il n'enregistre pas lui-meme les sessions de profiling.
- L'automatisation documentee est surtout orientee workflow Editor, pas simulation gameplay complete autonome out of the box.

### 4. Integrations et MCP

La doc distingue deux directions importantes:

- Assistant comme client MCP: Unity Assistant se connecte a des serveurs MCP externes pour appeler des outils hors Editor.
- Unity comme serveur MCP: Unity MCP expose des outils du Unity Editor a des clients externes.

La doc mentionne explicitement:

- MCP tools in Assistant: connecter des serveurs externes et consommer leurs outils.
- Unity MCP: connecter des clients IA externes a l'Editor Unity.
- Register custom MCP tools: creer et enregistrer des outils custom exposes via Unity MCP.

Conclusion pratique:

- Oui, il existe un chemin realiste pour brancher Terraformation a une couche d'outils IA.
- Le meilleur point d'entree n'est probablement pas un "skill custom" pur, mais un petit ensemble d'outils MCP dedies au debug et aux tests.

## Recommandation strategique

### Position recommandee

Ne pas commencer par "faire une IA qui joue".

Commencer par une pile en trois niveaux:

1. Documentation projet et workflows AI clairement cadres.
2. Outils MCP de debug et de verification reproductibles.
3. Harness de tests gameplay semi-automatiques, puis eventuellement agent autonome.

Cela reduit fortement le risque de construire une couche IA spectaculaire mais peu utile au quotidien.

## Ce que nous pouvons faire utilement pour Terraformation

### Axe A - Documentation AI projet

Objectif: donner a l'assistant un contexte stable et reutilisable.

Contenu recommande:

- architecture des 3 vues et transitions attendues
- pipeline de generation local et projection
- checklist des presets Ocean / Arid / Frozen / Coast / Basin
- conventions de debug: quels boutons, quels panneaux, quels logs regarder
- definition de "bon comportement" pour hydrologie, bassin, coast, projection, local

Livrables recommandes:

- guide "comment debugger Terraformation avec Assistant"
- guide "scenarios de test manuels"
- guide "outils MCP Terraformation"

### Axe B - Outils MCP de debug code et gameplay

Objectif: donner a l'assistant et aux agents des actions explicites, deterministes, et peu dangereuses.

Exemples d'outils a forte valeur:

1. `launch_debug_preset`
- entree: nom preset, openLocalView, lat, lon
- effet: lance Ocean, Arid, Frozen, Coast, Basin depuis Unity

2. `capture_projection_summary`
- entree: body, override, waterLevelOffset
- sortie: dimensions projection, ratio eau total, nombre ocean/coast/inland/dry/frozen, screenshot optionnelle

3. `capture_local_region_summary`
- entree: lat, lon, override
- sortie: resume du `HexGridDebugSummary`, coherence locale, biome counts, flow stats

4. `regenerate_local_region`
- entree: lat, lon, override optionnel
- effet: recharge la region locale et renvoie les stats apres generation

5. `apply_debug_cell_adjustment`
- entree: q, r, waterDelta, temperatureDelta
- sortie: etat cellule avant/apres

6. `run_view_flow_smoke_test`
- effet: enchaine SolarSystem -> Planet -> Local -> retour, detecte erreurs console et echec de transitions

7. `collect_console_and_scene_state`
- sortie: erreurs console, vue active, planete active, cellule selectionnee, context region, etat debug panels

8. `capture_playmode_screenshot`
- entree: vue cible, nom fichier
- sortie: image exploitable pour review visuelle

### Axe C - Harness de tests gameplay

Objectif: automatiser des verifications de non-regression sans demander a une IA de "jouer" librement trop tot.

Exemples:

- test Ocean: projection majoritairement eau, local majoritairement eau ou coast
- test Arid: peu d'eau libre, peu de rivieres, projection non oceanique
- test Frozen: eau gelee majoritaire sur zones polaires
- test Coast: vraie transition eau -> coast -> terre
- test Basin: eau interieure et exutoire plausible

Ces tests peuvent d'abord etre implementes comme:

- tests C# d'integration Editor/PlayMode
- commandes runtime debug declenchables via MCP
- snapshots de stats + comparaisons de seuils

## Skills vs MCP vs API maison

### Option 1 - Miser surtout sur les skills Unity

Avantages:

- peu de code initial
- integre a l'Editor
- bon pour assistance, guidage, petites actions

Limites:

- moins maitrise par l'equipe
- moins adapte a des workflows Terraformation tres specifiques
- la doc publique 2.6 n'expose pas aussi clairement un framework de skills custom projet que MCP

Verdict:

- utile en support
- insuffisant seul pour nos besoins de debug et tests repetables

### Option 2 - MCP externe pour Assistant

Avantages:

- bon pour brancher Git, scripts QA, comparateurs de logs, dashboards, exporteurs
- l'assistant Unity peut appeler ces outils pendant la conversation

Limites:

- ne donne pas directement acces a l'interieur du runtime Unity si on ne bridge pas Unity lui-meme

Verdict:

- tres bon complement
- ideal pour chaine QA et post-traitement

### Option 3 - Unity MCP + outils custom Terraformation

Avantages:

- meilleur point d'extension pour exposer le projet a un agent externe
- permet de piloter Unity de maniere plus propre qu'avec des hacks de console ou d'Inspector
- compatible avec une strategie de tests semi-autonomes

Limites:

- demande du code infrastructure
- impose une discipline sur la stabilite des outils exposes

Verdict:

- meilleure option long terme pour Terraformation

### Option 4 - API maison hors MCP

Exemple:

- petit serveur HTTP local dans l'Editor ou en PlayMode
- endpoints `/launch-preset`, `/capture-summary`, `/apply-cell-change`, `/run-smoke-test`

Avantages:

- simple a comprendre
- facile a connecter a n'importe quel outil externe

Limites:

- reinvente une partie de ce que MCP structure deja
- schema d'outils moins standardise pour les agents

Verdict:

- valable comme etape transitoire
- moins interessant que Unity MCP si l'objectif est une vraie boucle agentique

## Recommandation de mise en oeuvre

### Phase 1 - Documentation et conventions

But:

- rendre Terraformation "lisible" pour Assistant et pour les humains

Actions:

- documenter les presets de reference
- documenter les flows normaux et debug
- documenter les sorties attendues des stats hydrologie/coherence

### Phase 2 - Outils runtime de debug stables

But:

- rendre les informations et actions deterministes avant d'exposer quoi que ce soit a MCP

Pre-requis techniques:

- `ViewManager` expose des API publiques stables
- `DebugHydrologyPanel` et `HexGridDebugSummary` fournissent des donnees exploitables
- `TerraformSystem` sait appliquer des actions debug predictibles

### Phase 3 - Unity MCP tools Terraformation

But:

- exposer des outils custom a un client IA externe

Premiers outils recommandes:

- `GetCurrentViewState`
- `LaunchPreset`
- `OpenRegion`
- `GetProjectionSummary`
- `GetLocalSummary`
- `ApplySelectedCellAdjustments`
- `RegenerateCurrentLocalRegion`
- `GetRecentConsoleErrors`
- `CaptureSceneScreenshot`

### Phase 4 - Tests automatiques semi-guides

But:

- permettre a un agent de lancer des checks, sans improviser de gameplay libre

Resultat attendu:

- un agent peut verifier un preset, lire les stats, detecter une regression, et produire un rapport

### Phase 5 - Agent de jeu ou de test plus autonome

But:

- seulement apres stabilisation des outils et des metriques

Capacites possibles:

- jouer un scenario de smoke test
- lancer une sequence de navigation
- appliquer des actions de terraformation limitees
- comparer avant/apres sur screenshots et stats

## Ce qu'il ne faut pas faire tout de suite

- ne pas demander a l'IA de jouer librement sans cadre de test
- ne pas exposer des outils destructifs sans garde-fous
- ne pas baser la validation uniquement sur du visuel
- ne pas construire 20 outils avant d'avoir 5 scenarios de reference stables

## Proposition concrete pour Terraformation

### Court terme

Je recommande de produire en priorite:

1. une doc de workflow AI/debug projet
2. une checklist de validation manuelle par preset
3. un premier lot de tools Terraformation orientes resume et navigation

### Moyen terme

Je recommande de construire un petit package interne ou dossier tooling avec:

- runtime debug facade
- collecte de stats projection/local
- screenshots automatiques
- lecture des erreurs console
- commandes de scenario

### Long terme

Brancher ces outils sur Unity MCP pour qu'un client externe puisse:

- lancer des presets
- executer des smoke tests
- capturer des artefacts
- rediger un rapport de regression

## Reponse courte aux questions initiales

### Peut-on creer de la doc pour le projet plus tard ?

Oui. C'est meme un bon investissement immediat parce que la qualite de l'assistance depend directement du contexte projet disponible et stable.

### Peut-on creer des outils ou skills pour aller plus vite au debug code ?

Oui, et il faut le faire. En pratique, il vaut mieux viser des outils MCP et des API runtime Terraformation stables plutot qu'un pari sur des skills custom opaques.

### Peut-on creer une API ou un MCP pour que l'assistant fasse des tests et joue ?

Oui, c'est realiste.

La bonne cible est:

- d'abord des outils de test et d'inspection
- ensuite des smoke tests automatises
- seulement apres un agent plus autonome

## Decision recommandee

Decision proposee:

- adopter Unity AI Assistant comme couche d'assistance et d'automatisation Editor
- investir dans Unity MCP et des outils Terraformation custom pour debug et test
- ne pas chercher un agent de jeu libre tant que les scenarios, stats et outils ne sont pas stabilises

## Suite recommandee

Si l'equipe valide cette direction, les trois prochains livrables a produire sont:

1. `Documentation/AI_DEBUG_WORKFLOW.md`
2. `Documentation/TEST_PRESETS_CHECKLIST.md`
3. un premier lot de tools Terraformation exposes pour navigation, stats, screenshots et console