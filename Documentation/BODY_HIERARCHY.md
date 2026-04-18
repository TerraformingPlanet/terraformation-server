# Body Hierarchy — Système de Corps Célestes et Zones Intérieures

## Résumé

Ce document décrit le système de gestion des corps célestes et des zones intérieures implémenté côté serveur (Python). Il couvre l'architecture des modèles, la génération procédurale des tuiles de surface, la création des zones intérieures, les endpoints REST et les outils MCP exposés.

---

## 1. Problème résolu

Le client Unity gère les planètes comme des **Goldberg polyhedra** : chaque face du polyèdre est associée à une tuile hexagonale. Le serveur doit pouvoir représenter les mêmes surfaces sans porter la librairie C# `Hexasphere`. De plus, le jeu doit supporter non seulement des planètes mais aussi des lunes, astéroïdes, et des zones intérieures (grottes, bâtiments, vaisseaux) vues en grille hexagonale plate — avec une hiérarchie extensible pour les futurs types de corps.

---

## 2. Modèles de données (`SimulationCore/terraformation_sim/models.py`)

### Hiérarchie d'héritage

```
BaseModel
└── BodyBase              ← contrat commun à tous les corps
    ├── SphericalBodyState    ← planètes, lunes, astéroïdes  (surfaceType = "goldberg")
    └── InteriorZoneState     ← grottes, bâtiments, vaisseaux (surfaceType = "hex_flat")
```

Le champ `surfaceType` sert de **discriminateur Pydantic v2** pour le type union :

```python
AnyBodyState = Annotated[
    SphericalBodyState | InteriorZoneState,
    Field(discriminator="surfaceType"),
]
```

---

### `BodyType` (IntEnum)

| Valeur | Nom | Description |
|---|---|---|
| 0 | `Star` | Étoile |
| 1 | `Planet` | Planète tellurique |
| 2 | `Moon` | Lune |
| 3 | `Asteroid` | Astéroïde |
| 4 | `GasGiant` | Géante gazeuse |
| 5 | `SpaceStation` | Station spatiale |

---

### `ZoneType` (IntEnum)

| Valeur | Nom | Description |
|---|---|---|
| 0 | `Cave` | Grotte naturelle simple |
| 1 | `NaturalCavern` | Grande caverne naturelle |
| 2 | `Building` | Bâtiment colonisé |
| 3 | `Underground` | Infrastructure souterraine |
| 4 | `Ship` | Vaisseau spatial |
| 5 | `Station` | Station orbitale ou souterraine |

---

### `BodyBase`

Classe de base partagée par tous les corps et zones.

| Champ | Type | Description |
|---|---|---|
| `bodyId` | `str` | UUID unique |
| `bodyType` | `BodyType` | Type du corps |
| `name` | `str` | Nom lisible |
| `parentId` | `str \| None` | Lune → planète parente ; zone → corps parent |
| `seed` | `int` | Graine de génération procédurale |
| `surfaceType` | `str` | Discriminateur (`"goldberg"` ou `"hex_flat"`) |
| `isDiscovered` | `bool` | Corps découvert par le joueur |
| `isColonized` | `bool` | Corps colonisé |

---

### `SphericalBodyState` (extends `BodyBase`)

Représente une planète, lune ou astéroïde. Les tuiles sont vides par défaut et générées à la demande (lazy).

| Champ | Type | Description |
|---|---|---|
| `surfaceType` | `Literal["goldberg"]` | Discriminateur |
| `radiusKm` | `float` | Rayon en kilomètres |
| `divisions` | `int` | Paramètre N du Goldberg polyhedron (2–15) |
| `tileCount` | `int` | Nombre total de tuiles = `cols × rows` |
| `atmosphereDensity` | `float` | Densité atmosphérique (0–1) |
| `projectionOverride` | `DebugCoherenceOverride` | Override de cohérence pour la projection |
| `waterLevel` | `float` | Niveau d'eau global (0–1) |
| `summary` | `ProjectionDebugSummary` | Statistiques agrégées des tuiles |
| `tiles` | `list[GoldbergTileState]` | Tuiles de surface (vide par défaut) |

---

### `GoldbergTileState`

Une tuile de surface d'un corps sphérique. L'identifiant est stable : `tileId = row * cols + col`.

| Champ | Type | Description |
|---|---|---|
| `tileId` | `int` | Identifiant stable (row × cols + col) |
| `latNorm` | `float` | Latitude normalisée [0, 1] |
| `lonNorm` | `float` | Longitude normalisée [0, 1] |
| `latDeg` | `float` | Latitude en degrés [-90, 90] |
| `lonDeg` | `float` | Longitude en degrés [-180, 180] |
| `terrainType` | `TerrainType` | Type de terrain |
| `waterClassification` | `WaterClassification` | Classification hydrique |
| `terrainClass` | `TerrainClass` | Classe topographique |
| `waterRatio` | `float` | Ratio d'eau (0–1) |
| `temperature` | `float` | Température en °C |
| `toxinLevel` | `float` | Niveau de toxines (0–1) |
| `isHabitable` | `bool` | Tuile habitable |
| `childZoneIds` | `list[str]` | UUIDs des zones intérieures accessibles depuis cette tuile |

---

### `InteriorZoneState` (extends `BodyBase`)

Une zone intérieure vue en grille hexagonale plate (même contrat que `RegionState`). Peut être imbriquée : un bâtiment à l'intérieur d'une grotte a son propre `parentId` pointant vers la zone grotte.

| Champ | Type | Description |
|---|---|---|
| `surfaceType` | `Literal["hex_flat"]` | Discriminateur |
| `zoneType` | `ZoneType` | Type de zone intérieure |
| `parentTileId` | `int \| None` | Tuile de surface où se trouve l'entrée |
| `cols` | `int` | Largeur de la grille hexagonale (3–64) |
| `rows` | `int` | Hauteur de la grille hexagonale (3–64) |
| `summary` | `HexGridDebugSummary` | Statistiques de la grille |
| `cells` | `list[SimulationCellState]` | Cellules hexagonales (même type que `RegionState.cells`) |

---

## 3. Génération procédurale (`SimulationCore/terraformation_sim/logic.py`)

### `compute_goldberg_divisions(radius_km: float) → int`

Miroir exact de `GoldbergSphereGenerator.ComputeDivisions()` en C# (Unity). Calcule le paramètre N de division du polyèdre de Goldberg en fonction du rayon.

```
norm = clamp(radius_km / 69911, 0, 1)          # normalise Jupiter = 1
cols = 24 + 72 * norm
rows = 12 + 36 * norm
N    = round(sqrt(cols * rows / 10))            # [2, 15]
```

Exemples :
- Terre (6 371 km) → N = 7, 465 tuiles
- Jupiter (69 911 km) → N = 15, 2 252 tuiles
- Astéroïde (50 km) → N = 2, 42 tuiles

---

### `_goldberg_grid_dims(divisions: int) → (cols, rows)`

Calcule les dimensions `cols × rows` de la grille lat/lon équivalente. Le serveur utilise une grille lat/lon à la place de la topologie exacte du polyèdre, ce qui est valide car Unity mappe déjà les faces GP vers Mercator par proximité lat/lon (dans `GoldbergFaceColorizer.Colorize()`).

---

### `_tile_noise(col, row, seed, octave=0) → float`

Bruit déterministe basé sur un mixing entier de style Jenkins. Produit des valeurs dans [0, 1], stables entre les runs Python — sans dépendance externe.

```python
h = seed ^ (col * 2654435769) ^ (row * 2246822519) ^ (octave * 3266489917)
h = ((h ^ (h >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
h = ((h ^ (h >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
return (h ^ (h >> 16)) / 0xFFFFFFFF
```

---

### `generate_spherical_tiles(divisions, coherence_override, water_level, seed) → list[GoldbergTileState]`

Génère la grille complète de tuiles d'un corps sphérique. Chaque tuile est produite par bruit déterministe sur 4 octaves, puis classée selon l'override de cohérence (`Ocean`, `Arid`, `Frozen`, `Coast`, `Basin` ou `None_`).

---

### `generate_interior_cells(cols, rows, zone_type, seed) → list[SimulationCellState]`

Génère les cellules hexagonales d'une zone intérieure. Deux comportements selon le type :
- `Cave` / `NaturalCavern` / `Underground` → terrain rocheux, eau souterraine, layer `Underground`
- `Building` / `Ship` / `Station` → terrain métallique structuré, layer `Space`

---

### `is_tile_habitable(terrain_type, temperature, water_ratio) → bool`

Condition d'habitabilité d'une tuile de surface :
- Terrain non hostile (Roche, Végétation ou Eau)
- Température entre -20 °C et +50 °C
- Ratio d'eau entre 0.1 et 0.9

---

## 4. Runtime (`SimulationCore/terraformation_sim/runtime.py`)

### Stockage

```python
self._bodies: dict[str, AnyBodyState] = {}
self._active_body_id: str = ""
```

Toutes les entrées (planètes, lunes, zones) partagent le même dictionnaire. La clé est le `bodyId` (UUID).

---

### Initialisation au démarrage

`bootstrap_demo()` enregistre automatiquement Astra-Prime comme planète active via `_register_spherical_body_locked()`. Les tuiles ne sont pas générées à ce stade.

---

### Méthodes publiques

| Méthode | Description |
|---|---|
| `list_bodies()` | Retourne tous les corps sans tuiles ni cellules |
| `get_body(body_id)` | Retourne les métadonnées d'un corps sans tuiles ni cellules |
| `get_body_tiles(body_id, page, size)` | Génère et cache les tuiles au premier appel, retourne une page |
| `get_body_tile(body_id, tile_id)` | Retourne une tuile unique par son `tileId` |
| `apply_body_tile_delta(body_id, tile_id, water_delta, temperature_delta)` | Applique des deltas additifs (waterRatio clampé [0,1]) |
| `apply_body_tile_action(body_id, tile_id, action)` | Applique un modificateur `TerraformAction` sur une tuile |
| `register_interior_zone(parent_body_id, zone_type, cols, rows, parent_tile_id, seed)` | Crée une zone intérieure, génère ses cellules, lie son ID à `childZoneIds` de la tuile parente |
| `get_interior_zone(zone_id)` | Retourne une zone intérieure avec toutes ses cellules |

### Lazy generation + cache

Les tuiles sont coûteuses (jusqu'à 2 252 pour N=15). Elles sont générées une seule fois au premier appel de `get_body_tiles` ou `get_body_tile`, puis stockées dans `body.tiles`. Les réponses de `list_bodies` et `get_body` retournent toujours `tiles=[]` et `cells=[]` (via `model_copy`).

### Gestion d'erreurs

| Exception | Cause | HTTP |
|---|---|---|
| `KeyError` | `body_id` introuvable | 404 |
| `TypeError` | Mauvais type de corps (ex: tiles sur un InteriorZone) | 400 |
| `IndexError` | `tile_id` hors plage | 400 |

---

## 5. Endpoints REST (`DedicatedServer/app/server.py`)

Tous les endpoints existants restent inchangés (rétrocompatibilité totale).

### Nouveaux endpoints

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/bodies` | Liste tous les corps (tiles/cells vides) |
| `GET` | `/bodies/{body_id}` | Métadonnées d'un corps |
| `GET` | `/bodies/{body_id}/tiles?page=0&size=100` | Tuiles paginées d'un corps sphérique (max 200/page) |
| `GET` | `/bodies/{body_id}/tiles/{tile_id}` | Tuile unique |
| `POST` | `/bodies/{body_id}/tiles/{tile_id}/delta` | Delta waterRatio + température |
| `POST` | `/bodies/{body_id}/tiles/{tile_id}/action` | Action terraform (`action_type`: TerraformAction) |
| `GET` | `/bodies/{body_id}/cells?page=0&size=100` | Cellules paginées d'une zone intérieure |
| `POST` | `/bodies/{body_id}/zones` | Crée une zone intérieure attachée à un corps |

#### Paramètres de `POST /bodies/{body_id}/zones`

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `zone_type` | `ZoneType` | `0` (Cave) | Type de zone |
| `cols` | `int` | `9` | Largeur grille (3–64) |
| `rows` | `int` | `9` | Hauteur grille (3–64) |
| `parent_tile_id` | `int \| None` | `null` | Tuile de surface pour l'entrée |
| `seed` | `int \| None` | `null` | Graine (auto-générée si absente) |

---

## 6. Outils MCP (`Mcp/server.py`)

Neuf nouveaux outils `@mcp.tool` ajoutés, tous délégant vers les endpoints REST du Dedicated Server.

| Outil | Endpoint délégué | Description |
|---|---|---|
| `list_bodies()` | `GET /bodies` | Liste tous les corps |
| `get_body(body_id)` | `GET /bodies/{id}` | Métadonnées d'un corps |
| `get_body_tiles(body_id, page, size)` | `GET /bodies/{id}/tiles` | Tuiles paginées |
| `get_body_tile(body_id, tile_id)` | `GET /bodies/{id}/tiles/{tile_id}` | Tuile unique |
| `apply_body_tile_delta(body_id, tile_id, water_delta, temperature_delta)` | `POST /bodies/{id}/tiles/{tile_id}/delta` | Delta water/temp |
| `terraform_body_tile(body_id, tile_id, action_type)` | `POST /bodies/{id}/tiles/{tile_id}/action` | Action terraform |
| `list_interior_zones(body_id)` | `GET /bodies` (filtré) | Zones intérieures d'un corps parent |
| `get_interior_zone(zone_id)` | `GET /bodies/{id}` + `GET /bodies/{id}/cells` | Zone complète avec cellules |
| `register_interior_zone(body_id, zone_type, cols, rows, parent_tile_id, seed)` | `POST /bodies/{id}/zones` | Crée une zone intérieure |

---

## 7. Fichiers modifiés

| Fichier | Statut | Changements |
|---|---|---|
| `SimulationCore/terraformation_sim/models.py` | Modifié | `BodyType`, `ZoneType`, `GoldbergTileState`, `BodyBase`, `SphericalBodyState`, `InteriorZoneState`, `AnyBodyState` |
| `SimulationCore/terraformation_sim/logic.py` | Modifié | `compute_goldberg_divisions`, `_goldberg_grid_dims`, `_tile_noise`, `generate_spherical_tiles`, `is_tile_habitable`, `summarize_spherical_tiles`, `generate_interior_cells` |
| `SimulationCore/terraformation_sim/runtime.py` | Modifié | `_bodies`, `_active_body_id`, `_register_spherical_body_locked`, 8 méthodes publiques |
| `SimulationCore/terraformation_sim/__init__.py` | Modifié | Export de tous les nouveaux types et fonctions |
| `DedicatedServer/app/server.py` | Modifié | `HTTPException` import + 8 nouveaux endpoints |
| `Mcp/server.py` | Modifié | 9 nouveaux outils MCP |

Aucun nouveau fichier créé. Aucune dépendance ajoutée. Les Dockerfiles et `requirements.txt` sont inchangés.

---

## 8. Décisions d'architecture

### Grille lat/lon plutôt que topologie Goldberg exacte

Le serveur ne porte pas la librairie C# `Hexasphere`. Il génère une grille équivalente `cols × rows` en lat/lon. Unity mappe déjà les faces GP vers Mercator par proximité lat/lon (dans `GoldbergFaceColorizer.Colorize()`), donc les deux systèmes se correspondent sans conversion explicite.

### Bruit déterministe sans dépendance externe

`hash()` Python n'est pas stable entre les runs. La fonction `_tile_noise` utilise un mixing entier de style Jenkins sur des entiers 32 bits — sans numpy, random ni aucune lib externe. Le même `(col, row, seed, octave)` produit toujours le même résultat.

### Lazy generation + cache en mémoire

Les tuiles d'une planète de taille Jupiter pèsent ~2 252 objets Pydantic. Elles ne sont générées qu'au premier accès et stockées dans `body.tiles`. Les endpoints de listing retournent toujours `tiles=[]` via `model_copy(update={"tiles": []})` pour éviter les réponses trop larges.

### Zones intérieures comme `BodyBase`

`InteriorZoneState` hérite de `BodyBase` et non d'une classe séparée, ce qui permet :
- l'imbrication : un bâtiment à l'intérieur d'une grotte a son propre `parentId`
- le listing unifié via `/bodies`
- la même discrimination Pydantic avec `surfaceType`

### Lien surface → zone via `childZoneIds`

Quand une zone intérieure est créée avec un `parent_tile_id`, l'UUID de la zone est ajouté à `tiles[parent_tile_id].childZoneIds`. Le client peut ainsi découvrir les entrées de zones directement depuis une tuile de surface.

---

## 9. Exemples d'utilisation

### Lister les corps et récupérer les tuiles d'Astra-Prime

```powershell
# Liste tous les corps
$bodies = Invoke-RestMethod http://localhost:8080/bodies
$bid = $bodies[0].bodyId

# Première page de 10 tuiles
Invoke-RestMethod "http://localhost:8080/bodies/$bid/tiles?page=0&size=10"

# Tuile numéro 42
Invoke-RestMethod "http://localhost:8080/bodies/$bid/tiles/42"
```

### Appliquer un terraform sur une tuile

```powershell
# Irriguer la tuile 100
Invoke-RestMethod -Method Post "http://localhost:8080/bodies/$bid/tiles/100/action?action_type=1"

# Augmenter l'eau et la température manuellement
Invoke-RestMethod -Method Post "http://localhost:8080/bodies/$bid/tiles/100/delta?water_delta=0.2&temperature_delta=5"
```

### Créer une grotte accessible depuis la tuile 0

```powershell
$zone = Invoke-RestMethod -Method Post "http://localhost:8080/bodies/$bid/zones?zone_type=0&cols=12&rows=8&parent_tile_id=0"
$zid = $zone.bodyId

# Vérifier que la tuile 0 référence la grotte
(Invoke-RestMethod "http://localhost:8080/bodies/$bid/tiles/0").childZoneIds

# Lire les cellules de la grotte (page 1)
Invoke-RestMethod "http://localhost:8080/bodies/$zid/cells?page=0&size=20"
```

### Via MCP (outil IA)

```
list_bodies()
→ { "bodies": [{ "bodyId": "...", "name": "Astra-Prime", "divisions": 7, "tileCount": 465, ... }] }

get_body_tiles("b7eedbdc-...", page=0, size=5)
→ { "tiles": [{ "tileId": 0, "latDeg": -90.0, "terrainType": 1, "waterRatio": 0.458, ... }, ...] }

register_interior_zone("b7eedbdc-...", zone_type=0, cols=9, rows=9, parent_tile_id=0)
→ { "bodyId": "5ab9231a-...", "zoneType": 0, "cols": 9, "rows": 9, "cells": [...81 cells...] }
```
