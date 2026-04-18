# Plan de migration — Serveur Dédié Autoritaire

> Mis à jour le 18 avril 2026  
> Concerne : `DedicatedServer/`, `SimulationCore/`, `Game/Assets/Scripts/Simulation/`

> ⚠️ **ARCHIVÉ** — Tous les items serveur sont implémentés (§3.1 et §3.3 ✅). §3.2 (hydrologie) reporté en Phase 3. Items Unity (§4) délégués à l'agent Unity.

---

## 1. Philosophie cible

```
Unity Client           DedicatedServer (Python / FastAPI)
─────────────────      ─────────────────────────────────
Rendu / Input          Tick autoritaire
                       Génération canonique  ✅ fait
Actions joueur    ───► Queue + validation
                  ◄─── WorldState / RegionState / ProjectionState / GoldbergTiles
Fallback offline       Source de vérité
```

---

## 2. Contrats stables (NE PAS casser)

### Modèles partagés (`SimulationContracts.cs` ↔ `models.py`)

| Contrat C# | Équivalent Python | Stabilité |
|---|---|---|
| `WorldState` | `WorldState` | ✅ stable |
| `RegionState` + `SimulationCellState[]` | `RegionState` | ✅ stable |
| `ProjectionState` | `ProjectionState` | ✅ stable |
| `TerraformAction` (enum) | `TerraformAction` (IntEnum) | ✅ stable |
| `SimulationCellAddress` | `SimulationCellAddress` | ✅ stable |
| `HexGridDebugSummary` | `HexGridDebugSummary` | ✅ stable |
| `TerrainType`, `WaterClassification`, `WorldLayer` | idem | ✅ stable |
| — | `GoldbergTileState` | ✅ nouveau — pas encore de pendant C# |
| — | `SphericalBodyState`, `InteriorZoneState` | ✅ nouveau — pas encore de pendant C# |

### Routes HTTP live

| Route | Statut |
|---|---|
| `GET /health` | ✅ live |
| `GET /world` | ✅ live |
| `GET /projection` | ✅ live |
| `GET /region` | ✅ live |
| `GET /events/last` | ✅ live |
| `GET /actions/definitions` | ✅ live |
| `GET /actions/catalog` | ✅ live |
| `POST /commands/bootstrap-demo` | ✅ live |
| `POST /commands/open-region` | ✅ live |
| `POST /commands/queue-action` | ✅ live |
| `POST /commands/apply-cell-delta` | ✅ live |
| `POST /tick/advance` | ✅ live |
| `POST /tick/pause` / `/resume` | ✅ live |
| `GET /bodies` | ✅ live |
| `GET /bodies/{id}` | ✅ live |
| `GET /bodies/{id}/tiles` | ✅ live — paginé, max 200/page |
| `GET /bodies/{id}/tiles/{tile_id}` | ✅ live |
| `POST /bodies/{id}/tiles/{tile_id}/delta` | ✅ live |
| `POST /bodies/{id}/tiles/{tile_id}/action` | ✅ live |
| `GET /bodies/{id}/cells` | ✅ live — zones intérieures |
| `POST /bodies/{id}/zones` | ✅ live |

---

## 3. Travaux restants côté serveur

### 3.1 `GET /tick/status` — ✅ IMPLÉMENTÉ

Retourne `{ tickCount, tickRunning, tickIntervalSeconds }`. Disponible dans `DedicatedServer/app/server.py` et MCP tool `get_tick_status()`.

---

### 3.2 Pipeline hydrologie complet — **priorité moyenne**

`logic.py` classe déjà `WaterClassification` sur les tuiles et cellules. Ce qui manque est le **pipeline de rivières et flux** (équivalent de `RiverSystem.cs` + `HydrologySystem.cs`) pour que les cellules de région aient des valeurs `hasRiver`, `flowAccumulation`, `downstream` cohérentes avec la géographie plutôt que générées par bruit.

Cible : `apply_hydrology_pass(cells)` dans `SimulationCore` branché dans `_build_region_state()`.

**Effort** : Élevé. Peut se faire incrémentalement.

---

### 3.3 `POST /commands/set-projection` — ✅ IMPLÉMENTÉ

Change l'override de cohérence (Ocean=1 / Arid=2 / Frozen=3 / Coast=4 / Basin=5) et le `water_level` sans relancer `bootstrap-demo`. Invalide le cache de tuiles du body actif. Disponible dans `DedicatedServer/app/server.py` et MCP tool `set_projection()`.

---

## 4. Travaux restants côté Unity

### 4.1 Polling tick — **priorité haute**

Unity ne reçoit pas les mises à jour de tick automatiquement. **Recommandation : Option A — polling `GET /world` toutes les 5s.**

```
Coroutine Unity : GET /world → si tickCount > local → ApplyWorldState()
```

`GET /events/last` retourne le dernier événement unique, ce n'est **pas** du long-polling. L'utiliser uniquement pour des événements ponctuels, pas pour le suivi de tick.

Option WebSocket (`WS /events/stream`) en Phase 2 uniquement, quand multijoueur réel.

---

### 4.2 Désactiver le tick local — **priorité haute**

`TerraformSimulationSession.ProcessTick()` s'exécute encore localement. Quand `_isContextAuthoritative = true`, ce tick doit être inhibé. `process_pending_actions()` côté serveur (`logic.py`) gère déjà la queue.

---

### 4.3 `MapGenerator` en fallback seulement — **priorité moyenne**

`POST /commands/open-region` renvoie déjà un `RegionState` avec `cells[]` complets. `SynchronizeAuthoritativeRegionState()` existe dans Unity et les applique à `HexGrid`. Il reste à désactiver `MapGenerator` comme path principal et ne le conserver qu'en fallback offline.

---

### 4.4 Colorisation Goldberg depuis les tuiles serveur — **priorité moyenne, opportunité nouvelle**

`GET /bodies/{id}/tiles` retourne maintenant `terrainType`, `waterClassification` et `temperature` pour chaque tuile de surface. `GoldbergFaceColorizer` peut consommer ces données au lieu de les recalculer localement, garantissant une cohérence entre la vue planétaire Unity et les données serveur.

Mapping : `tileId = row * cols + col`. `latDeg` / `lonDeg` permettent de retrouver la face GP par proximité — même logique que `GoldbergFaceColorizer.Colorize()` actuel.

---

## 5. Ce qui N'A PAS à migrer (reste Unity)

---

## 5. Ce qui N'A PAS à migrer (reste Unity)

| Système | Raison |
|---|---|
| `GoldbergSphereGenerator` — mesh 3D | Rendu pur |
| `PlanetTangentView`, `PlanetFlatMesh` | Rendu pur |
| `HexMesh`, `HexMetrics` | Rendu pur |
| `CameraController`, `ViewManager` | Input / navigation |
| `TerraformHUD` | UI |
| `GoldbergFaceColorizer` | Colorisation biome — les *données* viennent du serveur, le *rendu* reste Unity |
| Shaders, Materials | Rendu |

---

## 6. Ordre de migration recommandé

```
Phase 1 — Simulation autoritaire (tick serveur → Unity)          ✅ CÔTÉ SERVEUR COMPLET
  ├── 1a. [Serveur] GET /tick/status                              ✅
  ├── 1b. [Unity]   Polling GET /world toutes les 5s             (Unity agent)
  └── 1c. [Unity]   Désactiver ProcessTick() si isContextAuthoritative (Unity agent)

Phase 2 — Génération de région et colorisation planétaire autoritaires  ✅ CÔTÉ SERVEUR COMPLET
  ├── 2a. [Unity]   Désactiver MapGenerator comme path principal  (Unity agent)
  ├── 2b. [Unity]   Brancher GoldbergFaceColorizer sur /bodies tiles (Unity agent)
  └── 2c. [Serveur] POST /commands/set-projection                ✅

Phase 3 — Hydrologie serveur
  ├── 3a. [Serveur] Porter HydrologySystem + RiverSystem en Python (SimulationCore)
  └── 3b. [Serveur] Brancher apply_hydrology_pass() dans _build_region_state()

Phase 4 — Multijoueur (futur)
  ├── 4a. [Serveur] WebSocket push WS /events/stream
  └── 4b. [Serveur] Autorisation actions par joueur
```

---

## 7. Couplage actuel Unity ↔ Serveur

```
ViewManager.SynchronizeRegionStateFromServer()
    POST /commands/open-region
        ← RegionState (cells[])
            → terraformHUD.SetAuthoritativeRegionState()
            → terraformSystem.SynchronizeAuthoritativeRegionState()
            → _isContextAuthoritative = true

ViewManager.TryBuildRegionState()  →  POST /mcp/region (via MCP Tools)
ViewManager.BuildWorldState()       →  POST /mcp/world  (via MCP Tools)
```

Le flag `_isContextAuthoritative` est le pivot : quand `true`, Unity utilise les données serveur ; quand `false`, il utilise sa génération locale. C'est le bon pattern à étendre.
