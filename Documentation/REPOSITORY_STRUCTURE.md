# Structure de Dépôt Cible

> **Voir aussi** : [ARCHITECTURE.md](ARCHITECTURE.md) pour les décisions d'architecture et la cible des couches · [MCP_TOOLS_ARCHITECTURE.md](MCP_TOOLS_ARCHITECTURE.md) pour le détail du sous-projet `Mcp/`

## Décision

Oui, le dépôt doit être découpé en plusieurs sous-projets explicites.

Le dépôt actuel mélange encore trois responsabilités différentes :

- le client Unity
- les outils MCP / Docker
- le futur serveur dédié

Ce mélange est acceptable pendant une phase de transition, mais ce n'est pas une bonne structure cible si l'on veut héberger la simulation hors du jeu.

## Structure recommandée

```text
terraformation/
├── Game/                 # client Unity actuel
├── Mcp/                  # serveur FastMCP, Dockerfile, wrapper compose local, scripts MCP
├── DedicatedServer/      # host autoritaire, Dockerfile, wrapper compose local, bootstrap serveur
├── SimulationCore/       # coeur métier partagé hors Unity
├── Documentation/
├── Artifacts/
└── Tools/                # scripts transverses temporaires ou utilitaires de migration
```

Le point de vérité pour l'orchestration Docker est `docker-compose.yml` à la racine.
Les compose dans `Mcp/` et `DedicatedServer/` servent uniquement de points d'entrée locaux vers cette stack unique.

## Pourquoi `Game / Mcp / DedicatedServer` est mieux

### `Game/`

Ne doit contenir que le client Unity : rendu, HUD, navigation, caméra, interaction locale, adaptateurs de snapshots.

### `Mcp/`

Doit contenir tout ce qui sert à exposer des tools AI, du transport HTTP MCP, du Docker, et les wrappers d'orchestration.

### `DedicatedServer/`

Doit contenir le runtime autoritaire : tick, commandes de gameplay, persistance, snapshots, intégration réseau, boot serveur.

## Le point important

Le vrai piège serait de ne créer que `Game/`, `Mcp/` et `DedicatedServer/` sans extraire le coeur métier.

Dans ce cas, on dupliquerait rapidement les règles de simulation entre Unity et le serveur.

La bonne cible est donc en réalité :

- `Game/` pour le client
- `Mcp/` pour les tools
- `DedicatedServer/` pour l'hôte autoritaire
- `SimulationCore/` pour les règles communes

## Plan de transition recommandé

### Étape 1

Conserver `Game/` tel quel pour continuer à livrer et tester.

### Étape 2

Basculer toutes les références actives de `Tools/mcp` vers `Mcp/`, puis conserver au plus un shim legacy minimal.

### Étape 3

Créer `DedicatedServer/` comme projet autonome minimal qui sert `WorldState` et `RegionState`.

### Étape 4

Extraire les règles de simulation réutilisables dans `SimulationCore/`.

### Étape 5

Faire dépendre `Game/` et `DedicatedServer/` de `SimulationCore/`, puis faire parler `Mcp/` au serveur plutôt qu'au runtime Unity pour les tools métier.

## État actuel

Le dépôt est maintenant en transition active vers cette forme :

- `Game/` contient le client Unity, mais embarque encore une partie de la logique métier — `TerraformSystem` délègue au serveur avec fallback local, `ViewManager` synchronise autoritairement les régions depuis le serveur
- `Mcp/` existe comme vrai sous-projet Dockerisé et la racine build déjà dessus
- `DedicatedServer/` est un host autoritaire fonctionnel — 14 routes HTTP, `InMemorySimulationRuntime`, tick loop, action queue, intégration `SimulationCore/`
- `SimulationCore/terraformation_sim/` est le coeur métier partagé hors Unity : `models.py` (Pydantic), `logic.py` (logique pure), `runtime.py` (runtime mémoire) — consommé directement par `DedicatedServer`
- `Tools/mcp` reste présent uniquement comme shim legacy de compatibilité, sans nouveau développement

La structure cible est atteinte structurellement. Le coeur de simulation Python est extrait et fonctionnel. Le travail restant porte sur l'injection des paramètres de contexte serveur dans la génération locale Unity (GenerationContext) et la migration des derniers tools MCP encore sur le bridge Unity.