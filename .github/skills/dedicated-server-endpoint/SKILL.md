---
name: dedicated-server-endpoint
description: 'Use when adding a new REST endpoint to DedicatedServer/app/server.py and/or a corresponding MCP tool in Mcp/server.py. Trigger words: new endpoint, FastAPI route, MCP tool, server.py, _server_get, _server_post, simulation-server tool, debug-client tool, add route, expose endpoint, MCP_TOOLS_ARCHITECTURE.'
argument-hint: 'Describe the endpoint: e.g. "add GET /game/market endpoint + MCP tool", "expose POST /game/events/trigger"'
---

# Dedicated Server Endpoint + MCP Tool

## When to Use

- Adding a new REST route to `DedicatedServer/app/server.py`
- Adding a corresponding tool to `Mcp/server.py`
- Deciding which MCP family (`debug-client` vs `simulation-server`) a tool belongs to
- Updating `MCP_TOOLS_ARCHITECTURE.md` after adding tools

## Step 1 — Classify the Tool Family

| Family | Data source | Unity required? | Helper |
|--------|------------|-----------------|--------|
| `debug-client` | Unity bridge `http://127.0.0.1:48621` | **Yes — Play Mode** | `_get(path, **params)` |
| `simulation-server` | DedicatedServer `http://...:8080` | No | `_server_get(path, **params)` / `_server_post(path, **data)` |

Rule: if the data is authoritative (persisted state, tick data, entity data) → `simulation-server`. If the data is Unity-only (view state, console, screenshots, visual captures) → `debug-client`. When in doubt, use `simulation-server`.

## Step 2 — Add the FastAPI Endpoint

### GET endpoint (read)
```python
@app.get("/game/xxx/{id}", response_model=XxxModel)
def get_xxx(id: str) -> XxxModel:
    result = runtime.get_xxx(id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"xxx {id!r} not found")
    return result

@app.get("/game/xxx", response_model=list[XxxModel])
def list_xxx() -> list[XxxModel]:
    return runtime.list_xxx()
```

### POST endpoint (command / mutation)
```python
@app.post("/game/xxx", response_model=XxxModel)
def create_xxx(name: str, value: float = 0.0) -> XxxModel:
    return runtime.create_xxx(name=name, value=value)
```

### PATCH endpoint (partial update)
```python
@app.patch("/game/xxx/{id}", response_model=XxxModel)
def update_xxx(id: str, field: float) -> XxxModel:
    result = runtime.update_xxx(id=id, field=field)
    if result is None:
        raise HTTPException(status_code=404, detail=f"xxx {id!r} not found")
    return result
```

**Error codes**:
- `404` — entity not found
- `409` — conflict (e.g., already exists, already claimed)
- `422` — automatically raised by FastAPI for invalid parameter types

**Response format**: always return a Pydantic model directly — not a raw `dict`. FastAPI serializes it.

## Step 3 — Add the MCP Tool

### simulation-server tool
```python
@mcp.tool
def get_xxx(xxx_id: str) -> dict:
    """
    Get the state of an xxx by ID.
    Returns XxxModel fields.
    Does not require Unity. Wraps GET /game/xxx/{id} on the DedicatedServer.

    Args:
        xxx_id: UUID of the xxx entity.
    """
    return _server_get(f"/game/xxx/{xxx_id}")


@mcp.tool
def create_xxx(name: str, value: float = 0.0) -> dict:
    """
    Create a new xxx entity.
    Does not require Unity. Wraps POST /game/xxx on the DedicatedServer.

    Args:
        name: Display name of the xxx.
        value: Initial value (default 0.0).
    """
    return _server_post("/game/xxx", name=name, value=value)
```

### debug-client tool
```python
@mcp.tool
def get_unity_xxx() -> dict:
    """
    Get xxx state from Unity.
    Requires Unity to be running in Play Mode (bridge on port 48621).
    This tool can never be migrated to the simulation server.
    """
    return _get("/debug/xxx")
```

**Docstring rules**:
- First line: one sentence describing what the tool returns
- Include "Does not require Unity" for simulation-server, or "Requires Unity to be running in Play Mode" for debug-client
- Always document arguments with `Args:` block
- Match tool name to endpoint semantics: `get_*` → GET, `create_*` / `add_*` → POST, `update_*` / `patch_*` → PATCH

## Step 4 — Update MCP_TOOLS_ARCHITECTURE.md

Add the new tool(s) to the correct family table in `Documentation/MCP_TOOLS_ARCHITECTURE.md`:

```markdown
| `get_xxx` | `/game/xxx/{id}` | simulation-server |
```

## Placement in Mcp/server.py

Tools are grouped by sprint/phase. Add new tools in the correct section with a comment header:
```python
# ── Phase 7.3: Market tools ────────────────────────────────────────────────
```

The file is ordered: `debug-client` tools first, then `simulation-server` tools by phase.
