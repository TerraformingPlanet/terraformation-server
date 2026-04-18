# DedicatedServer

Ce dossier contient maintenant le squelette du futur serveur autoritaire.

## Rôle

- bootstrap serveur
- boucle de tick autoritaire
- chargement et persistance d'état
- traitement des commandes de simulation
- exposition des snapshots `WorldState`, `RegionState`, `ProjectionState`
- conteneurisation Docker serveur

## État actuel

Le dossier contient maintenant un host HTTP minimal réel appuyé sur `SimulationCore/`.

Il ne porte pas encore toute la simulation du jeu, mais il expose déjà un runtime mémoire avec :

- `GET /health`
- `GET /world`
- `GET /projection`
- `GET /region`
- `POST /commands/bootstrap-demo`
- `POST /commands/open-region`
- `POST /tick/advance`
- `POST /tick/pause`
- `POST /tick/resume`

Le but de cette étape est de remplacer le faux scaffold `501` par un vrai host minimal qui parle déjà les contrats de snapshots stabilisés.

## Première cible réaliste

Un host minimal hors Unity qui :

1. démarre un tick
2. charge un état monde minimal
3. renvoie `WorldState`
4. renvoie `RegionState`
5. accepte au moins une commande simple de simulation

## Usage local

Depuis ce dossier :

```bash
docker compose up -d --build
```