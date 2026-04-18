# Mcp

Ce dossier contient désormais le sous-projet MCP cible.

## Rôle

- serveur FastMCP
- Dockerfile MCP
- compose local MCP
- wrappers d'orchestration et outils d'agent
- intégration future avec le serveur de simulation

## Fichiers clés

- `server.py`
- `Dockerfile`
- `requirements.txt`
- `docker-compose.yml`

## État de transition

Le code historique existe encore dans `Tools/mcp` pour compatibilité temporaire, mais la racine doit maintenant considérer `Mcp/` comme la destination principale.

## Usage local

Depuis ce dossier :

```bash
docker compose up -d --build
```

Depuis la racine :

```bash
docker compose up -d --build terraformation-mcp
```