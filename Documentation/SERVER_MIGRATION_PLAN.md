# Plan de migration — Serveur Dédié Autoritaire

> État au 18 avril 2026  
> Concerne : `DedicatedServer/`, `SimulationCore/`, `Game/Assets/Scripts/Simulation/`

---

## 1. Philosophie cible

```
Unity Client           DedicatedServer (Python / FastAPI)
─────────────────      ─────────────────────────────────
Rendu / Input          Tick autoritaire
Génération locale*     Génération canonique  ← migration
Actions joueur    ───► Queue + validation
Snapshot local*   ◄─── WorldState / RegionState / ProjectionState
Fallback offline       Source de vérité
```

`*` = existe des deux côtés aujourd'hui, doit migrer vers le serveur.

---

## 2. État actuel des contrats (stable, NE PAS casser)

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

### Routes HTTP (DedicatedServer — déjà implémentées)

| Route | Statut |
|---|---|
| `GET /health` | ✅ live |
| `GET /world` | ✅ live |
| `GET /projection` | ✅ live |
| `GET /region` | ✅ live |
| `GET /events/last` | ✅ live |
| `GET /actions/definitions` | ✅ live |
| `POST /commands/bootstrap-demo` | ✅ live |
| `POST /commands/open-region` | ✅ live |
| `POST /commands/queue-action` | ✅ live |
| `POST /commands/apply-cell-delta` | ✅ live |
| `POST /tick/advance` | ✅ live |
| `POST /tick/pause` / `/resume` | ✅ live |

---

## 3. Ce qui tourne encore uniquement dans Unity (à migrer)

### 3.1 Génération de région locale — **priorité haute**

**Où** : `MapGenerator.cs`, `HexGrid.cs`, `TerraformSimulationSession.cs`  
**Quoi** : génération procédurale d'une région hex (altitude, biome, hydrologie)  
**Problème** : Unity génère sa propre région localement. Le serveur génère la sienne indépendamment depuis `InMemorySimulationRuntime._build_region_state()`. Les deux peuvent diverger.

**Migration cible** :
```
POST /commands/open-region → renvoie RegionState avec cells[] complets
Unity reçoit le RegionState et l'applique directement à HexGrid (déjà en place via SynchronizeAuthoritativeRegionState)
Unity supprime sa génération locale (MapGenerator) comme path principal
```
**Effort** : Moyen. `SynchronizeAuthoritativeRegionState` existe déjà dans Unity. Il faut que `runtime._build_region_state()` produise des cellules aussi riches que `MapGenerator`.

---

### 3.2 Pipeline hydrologie — **priorité moyenne**

**Où** : `Systems/BiomeSystem.cs`, `Systems/HydrologySystem.cs`, `Systems/RiverSystem.cs`, `Systems/WaterClassificationSystem.cs`  
**Quoi** : classification eau (OpenOcean / Coast / InlandWater / Frozen / Dry), rivières, flux  
**Problème** : implémenté en C# côté Unity. `logic.py` a la logique de classification mais pas le pipeline complet de génération.

**Migration cible** :
```python
# SimulationCore/terraformation_sim/hydrology.py  (à créer)
def apply_hydrology_pass(cells: list[SimulationCellState]) -> list[SimulationCellState]:
    # Porter BiomeSystem + HydrologySystem + RiverSystem
```
**Effort** : Élevé (logique complexe). Peut se faire incrémentalement : la classification `WaterClassification` est déjà dans `models.py`.

---

### 3.3 Simulation de terraformation locale — **priorité haute**

**Où** : `TerraformSimulationSession.cs`  
**Quoi** : queue d'actions (`_pending`), `ProcessTick()`, `ApplyModifier()`, réévaluation de biome  
**Problème** : Unity exécute le tick localement. Le serveur a son propre tick dans `runtime.py`. Risque de désynchronisation.

**Migration cible** :
```
Unity : quand tick serveur → recevoir WorldState mis à jour → appliquer à HexGrid
Unity : ne plus appeler TerraformSimulationSession.ProcessTick() si isContextAuthoritative=true
Serveur : process_pending_actions() gère déjà la queue (logic.py)
```
**Effort** : Faible. `_isContextAuthoritative` existe dans ViewManager. Il faut un event serveur → Unity pour pousser les updates de tick (ou polling sur `GET /world`).

---

### 3.4 Génération planétaire (projection) — **priorité basse**

**Où** : `GoldbergSphereGenerator.cs`, `PlanetaryHexGrid.cs`, `GoldbergFaceColorizer.cs`  
**Quoi** : génération de la sphère Goldberg, grille planétaire, colorisation biomes  
**Problème** : 100% Unity, pas de pendant serveur.  
**Note** : cette partie est du rendu pur (mesh 3D). Elle N'A PAS à migrer vers le serveur. Seules les données de projection (`ProjectionState.summary`) doivent être autoritatives côté serveur.

**Migration cible** :
```
Serveur expose : GET /projection → ProjectionState avec summary global (déjà fait)
Unity garde   : génération mesh Goldberg, colorisation (rendu seulement)
```
**Effort** : Quasi nul. Déjà séparé.

---

### 3.5 Sync tick Unity → Serveur — **priorité haute**

**Où** : `ViewManager.SynchronizeRegionStateFromServer()` (polling sur open-region)  
**Problème** : Unity ne reçoit pas les mises à jour de tick serveur automatiquement. Il faut un appel explicite.

**Migration cible (3 options)** :

| Option | Complexité | Temps réel |
|---|---|---|
| **A. Polling** `GET /world` toutes les N secondes | Faible | Non |
| **B. Long-polling** `GET /events/last` | Moyenne | Partiel |
| **C. WebSocket** push depuis serveur | Élevée | Oui |

**Recommandation** : Option A pour la Phase 1 (polling 5s = intervalle tick), Option C quand multijoueur réel.

**Endpoint à ajouter** :
```python
# server.py
GET /tick/status → { tickCount, tickRunning, nextTickIn }
```

---

## 4. Endpoints manquants à implémenter côté serveur

| Endpoint | Utilité | Priorité |
|---|---|---|
| `GET /tick/status` | Unity sait quand le prochain tick aura lieu | Haute |
| `POST /commands/set-projection` | Changer override de cohérence depuis Unity | Moyenne |
| `GET /snapshot/full` | ClientSnapshot complet (WorldState + RegionState) en un appel | Moyenne |
| `POST /commands/sync-cell-selection` | Notifier le serveur de la cellule sélectionnée | Basse |
| `WS /events/stream` | Push WebSocket pour mises à jour temps réel | Phase 2 |

---

## 5. Ce qui N'A PAS à migrer (reste Unity)

| Système | Raison |
|---|---|
| `GoldbergSphereGenerator` — mesh 3D | Rendu pur |
| `PlanetTangentView`, `PlanetFlatMesh` | Rendu pur |
| `HexMesh`, `HexMetrics` | Rendu pur |
| `CameraController`, `ViewManager` | Input / navigation |
| `TerraformHUD` | UI |
| `GoldbergFaceColorizer` | Colorisation biome (données viennent du serveur) |
| Shaders, Materials | Rendu |

---

## 6. Ordre de migration recommandé

```
Phase 1 — Simulation autoritaire (tick serveur → Unity)
  ├── 1a. Polling tick : Unity GET /world toutes les 5s → ApplyWorldState()
  ├── 1b. Désactiver TerraformSimulationSession.ProcessTick() si isContextAuthoritative
  └── 1c. Ajouter GET /tick/status

Phase 2 — Génération de région autoritaire
  ├── 2a. Enrichir runtime._build_region_state() pour produire des cellules complètes
  ├── 2b. Supprimer MapGenerator comme path principal (garder en fallback offline)
  └── 2c. Implémenter GET /snapshot/full

Phase 3 — Hydrologie serveur
  ├── 3a. Porter HydrologySystem + RiverSystem en Python (SimulationCore)
  └── 3b. Brancher dans _build_region_state()

Phase 4 — Multijoueur (futur)
  ├── 4a. WebSocket push
  └── 4b. Autorisation actions par joueur
```

---

## 7. Couplage actuel Unity ↔ Serveur (résumé)

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
