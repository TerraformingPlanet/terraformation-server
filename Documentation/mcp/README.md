# FastMCP — Référence Projet

La documentation complète de FastMCP est sur **[gofastmcp.com](https://gofastmcp.com)**.

Pour un index complet de toutes les pages disponibles, fetcher : `https://gofastmcp.com/llms.txt`

---

## Patterns utilisés dans ce projet

### Transport

Le serveur MCP utilise `streamable-http` sur le port 8000.

```python
mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

### Tools

Chaque tool est une fonction décorée `@mcp.tool`. Les inputs sont typés (Pydantic inféré). Les outputs sont des dicts structurés (`success`, `data`, `message`, `warnings`).

```python
@mcp.tool
async def get_region_state(...) -> dict:
    ...
```

### Client httpx (bridge Unity)

Le client httpx force `Host: 127.0.0.1:48621` sur toutes les requêtes vers le bridge Unity — contournement du bug `HTTP.sys` Windows qui valide le header `Host` contre le prefix enregistré. **Ne pas retirer cette override.**

```python
headers={"Host": "127.0.0.1:48621"}
```

### Variable d'environnement

| Variable | Défaut | Usage |
|---|---|---|
| `GAME_BRIDGE_URL` | `http://host.docker.internal:48621` | Bridge HTTP Unity |
| `SIMULATION_SERVER_URL` | `http://terraformation-dedicated-server:8080` | DedicatedServer |
| `MCP_PORT` | `8000` | Port du serveur MCP |

---

## Liens utiles

- [Installation](https://gofastmcp.com/getting-started/installation)
- [Tools](https://gofastmcp.com/servers/tools)
- [HTTP Transport](https://gofastmcp.com/deployment/running-servers)
- [Client](https://gofastmcp.com/clients/client)

Pour l'état opérationnel du serveur MCP du projet, voir [MCP_TOOLS_ARCHITECTURE.md](../MCP_TOOLS_ARCHITECTURE.md).
