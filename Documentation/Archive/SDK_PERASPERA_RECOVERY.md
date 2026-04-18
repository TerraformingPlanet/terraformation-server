# Récupération SDK Per Aspera → Jeu Unity Terraformation

> **Objet** : Ce document synthétise l'analyse du SDK Per Aspera (mod BepInEx pour le jeu commercial Per Aspera, développé en parallèle) et définit précisément ce qui peut être récupéré pour accélérer le développement du jeu `E:\terraformation`. Il sert de référence avant de démarrer le chantier d'implémentation.
>
> **SDK analysé** : `F:\ModPeraspera\SDK\` + `F:\ModPeraspera\Internal_doc\`
> **Cible** : `E:\terraformation\SimulationCore\` · `DedicatedServer\` · `Game\` · `Mcp\`

---

## Contexte

Le SDK Per Aspera est un framework de modding Unity IL2CPP pour le jeu commercial *Per Aspera* (jeu de terraformation de Mars). Il a été développé pendant plusieurs mois et contient des systèmes de simulation climatique et atmosphérique matures, testés en conditions réelles de jeu.

Le jeu *Terraformation* en développement ici partage le même domaine métier (terraformation planétaire, atmosphère, habitabilité, simulation cellulaire). Le Sprint D du backlog actif requiert précisément ce que le SDK Per Aspera a déjà résolu.

**Ce qu'on récupère** : les formules physiques, les patrons de conception, les valeurs de calibration, les structures de données.

**Ce qu'on ne récupère pas** : tout ce qui est spécifique à l'architecture BepInEx/IL2CPP (patches HarmonyX, wrappers IL2CPP, interop assemblies). Aucun de ces mécanismes n'a de sens dans un projet Python/Unity natif.

---

## Inventaire du SDK Per Aspera

### Structure des projets

```
F:\ModPeraspera\SDK\
├── PerAspera.Abstractions/            # Interfaces et contrats de base
├── PerAspera.Core/                    # LogAspera, ReflectionHelpers, utilitaires
├── PerAspera.Core.IL2CppExtensions/   # Conversions IL2CPP (non récupérable)
├── PerAspera.GameAPI/                 # Accès BaseGame, Universe, Planet
├── PerAspera.GameAPI.Climate/         # ★ PRINCIPAL INTÉRÊT ★
│   ├── ClimateController.cs           # Contrôleur maître, bidirectionnel
│   ├── ResourceBasedClimate.cs        # Mappage ressources ↔ pression gaz
│   ├── TerraformingEffectsController.cs   # HeatWave, ColdSnap, effets custom
│   ├── Configuration/ClimateConfig.cs # Presets: GameBalanced / Realistic / Debug
│   ├── Simulation/ClimateSimulator.cs # Tick simulation, effet de serre
│   └── Domain/Atmosphere/
│       ├── AtmosphereGrid.cs          # Grille cellulaire atmosphérique
│       └── AtmosphereCell.cs          # État par cellule (T, P, composition)
├── PerAspera.GameAPI.Events/          # EnhancedEventBus, événements typés
├── PerAspera.GameAPI.Overrides/       # Modification runtime valeurs jeu
├── PerAspera.GameAPI.Wrappers/        # BaseGameWrapper, PlanetWrapper, etc.
└── PerAspera.ModSDK/                  # API publique unifiée
```

### Systèmes climatiques disponibles

| Composant SDK | Rôle | Maturité |
|---|---|---|
| `ClimateController` | Orchestration simulation atmosphérique + grille cellulaire | Production |
| `ClimateSimulator` | Tick de simulation, effet de serre, régions polaires/équatoriales | Production (partiel) |
| `ClimateConfig` | Presets de calibration physique (3 modes) | Production |
| `AtmosphereGrid` | Grille cellulaire atmosphérique, tick par cellule, agrégation | Production |
| `AtmosphereCell` | État individuel (T, P, composition gazeuse) | Production |
| `TerraformingEffectsController` | Effets temporaires (HeatWave, ColdSnap), overrides vanilla | Production |
| `TerraformingGraphDataProvider` | Données de progression pour visualisation temporelle | Production |
| `ResourceBasedClimate` | Mappage ressources du jeu → pression atmosphérique | Partiel (TODO internes) |

### Gaz atmosphériques modélisés

Le SDK gère CO₂, O₂, N₂, H₂O (vapeur), plus les gaz étendus du mod *MoreResources* : CH₄, Ar, Ne, He, Kr, Xe, H₂S, SO₂, NH₃.

---

## Mappages SDK → Jeu Terraformation

### Tableau de correspondance

| Composant SDK Per Aspera | Équivalent dans le jeu Terraformation | Utilité concrète |
|---|---|---|
| `ClimateSnapshot` / snapshot d'état | `AtmosphericState` (Sprint D, absent pour l'instant) | Structure à créer directement inspirée |
| `CalculateGreenhouseEffect()` | `compute_atmospheric_state()` → évolution T par tick | Formule logarithmique portée en Python |
| `CalculateHabitabilityScore()` | `compute_habitability_progress()` → score pondéré [0..1] | Remplacer la version booléenne actuelle |
| `AtmosphereGrid.Tick(deltaDays)` | `_tick_loop()` dans `runtime.py` → évolution atmosphère | Modèle d'évolution cellulaire |
| `AtmosphereGrid.SyncWithNativePlanet()` | `apply_region_progress()` → agréger cells → état région | Patron d'agrégation cellulaire |
| `TerraformingEffectsController.CreateHeatWave()` | `terraform_action_definitions()` → `TerraformAction.Heat` | Calibration `tempDelta` à 5–8K/tick |
| `TerraformingEffectsController.CreateColdSnap()` | Future action `TerraformAction.Freeze` | Symétrie chaud/froid |
| `ClimateConfig` presets | Variable d'env `CLIMATE_MODE` dans DedicatedServer | Modes debug/réaliste/équilibré |
| `TerraformingOptimizer` | Phase 7 — stratégie corporation | Calcul "X bâtiments pour Y% habitabilité" |
| `ClimateEvents` thresholds | `SimulationEventType` — nouveaux événements | `ThermalEquilibrium`, `HabitabilityThreshold` |
| Gaz étendus (CH₄, SO₂…) | `toxinRatio` → future décomposition par type de gaz | Toxicité différenciée |

### Ce qui manque actuellement dans le jeu

L'état actuel de `compute_habitability_progress()` dans `logic.py` est **purement booléen** : une cellule est habitable si `terrainType == Vegetation` ou si T ∈ [-10°C, +50°C] et `waterRatio ≥ 0.05`. Il n'y a pas de score continu, pas de notion d'atmosphère agrégée, pas de CO₂/O₂/pression au niveau région.

Le SDK Per Aspera a résolu ce problème avec un score pondéré multi-paramètres. Le Sprint D du ROADMAP demande exactement cela.

---

## Formules mathématiques concrètes récupérables

### 1. Effet de serre (source : `ClimateSimulator.cs`)

```python
# Porté depuis PerAspera.GameAPI.Climate/Simulation/ClimateSimulator.cs
# CalculateGreenhouseEffect(co2Pressure, o2Pressure, ghgPressure)

CO2_EFF_GAME_BALANCED = 1.5   # CO2GreenhouseEfficiency
H2O_EFF_GAME_BALANCED = 4.0   # H2OGreenhouseEfficiency
MAX_WARMING_K = 80.0           # MaxGreenhouseWarming

def calculate_greenhouse_effect(co2_ratio: float, h2o_factor: float = 0.01) -> float:
    """
    Température supplémentaire (Kelvin) due à l'effet de serre.
    co2_ratio : fraction CO₂ dans l'atmosphère [0..1]
    Formule logarithmique — cohérente avec la physique réelle.
    """
    co2_effect = CO2_EFF_GAME_BALANCED * math.log(1.0 + co2_ratio * 100.0) * 5.0
    h2o_effect = H2O_EFF_GAME_BALANCED * h2o_factor
    return min(co2_effect + h2o_effect, MAX_WARMING_K)
```

**Presets `ClimateConfig`** (pour variable d'env `CLIMATE_MODE`) :

| Mode | CO2eff | H2Oeff | maxWarming | Usage |
|---|---|---|---|---|
| `game_balanced` | 1.5 | 4.0 | 80 K | Défaut — jouabilité |
| `realistic` | 1.0 | 2.8 | 60 K | Simulation fidèle |
| `debug` | 5.0 | 10.0 | 200 K | Tests rapides |

### 2. Score d'habitabilité pondéré (source : agent docs SDK + `is_cell_habitable`)

```python
# Remplace la version booléenne actuelle de is_cell_habitable()
# Inspiré de CalculateHabitabilityScore() du SDK

def cell_habitability_score(cell: SimulationCellState) -> float:
    """Score continu [0..1] d'habitabilité d'une cellule."""
    # Température : optimum 15°C, plage [-10, +50]
    t = cell.temperature
    if t < -30.0 or t > 70.0:
        temp_score = 0.0
    elif -10.0 <= t <= 50.0:
        temp_score = 1.0 - abs(t - 15.0) / 35.0
    else:
        temp_score = max(0.0, 1.0 - abs(t - 15.0) / 45.0) * 0.3

    # Eau liquide
    water_score = min(1.0, cell.waterRatio / 0.3) if cell.terrainType == TerrainType.Eau else cell.waterRatio

    # Végétation = bonus fort
    veg_bonus = 1.0 if cell.terrainType == TerrainType.Vegetation else 0.0

    # Toxines
    toxin_penalty = max(0.0, 1.0 - cell.toxinLevel * 3.0)

    return (temp_score * 0.35 + water_score * 0.25 + veg_bonus * 0.25 + toxin_penalty * 0.15)
```

### 3. AtmosphericState agrégée (source : `AtmosphereGrid.SyncWithNativePlanet()`)

```python
# Porté depuis AtmosphereGrid.cs — agrégation cellulaire → état région
# Adapté : CO₂ et O₂ déduits de l'état des cellules (pas de nouveaux champs)

def compute_atmospheric_state(cells: list[SimulationCellState]) -> AtmosphericState:
    if not cells:
        return AtmosphericState()

    total = len(cells)
    avg_temp = sum(c.temperature for c in cells) / total
    avg_water = sum(c.waterRatio for c in cells) / total
    avg_toxin = sum(c.toxinLevel for c in cells) / total

    # Végétation → O₂ produit (proxy simplifié)
    veg_fraction = sum(1 for c in cells if c.terrainType == TerrainType.Vegetation) / total
    # Eau liquide → humidité atmosphérique
    water_fraction = sum(1 for c in cells
                         if c.waterClassification in (WaterClassification.OpenOcean,
                                                       WaterClassification.InlandWater,
                                                       WaterClassification.Coast)) / total
    # Toxines atmosphériques → proxy CO₂ (gaz toxiques)
    toxic_fraction = sum(1 for c in cells if c.terrainType == TerrainType.AtmosphereToxique) / total

    o2_ratio = min(0.21, veg_fraction * 0.5 + water_fraction * 0.05)
    co2_ratio = max(0.0004, toxic_fraction * 0.8 + avg_toxin * 0.3 - veg_fraction * 0.1)
    co2_ratio = min(0.96, co2_ratio)

    # Pression atmosphérique (kPa) — 101 kPa = Terre, <10 kPa = Mars initial
    atmospheric_pressure = 0.6 + co2_ratio * 50.0 + o2_ratio * 40.0 + water_fraction * 10.0

    greenhouse_delta = calculate_greenhouse_effect(co2_ratio)
    effective_temp = avg_temp + greenhouse_delta * 0.1  # effet partiel

    # Score d'habitabilité global
    scores = [cell_habitability_score(c) for c in cells]
    habitability_score = sum(scores) / total

    return AtmosphericState(
        co2Ratio=round(co2_ratio, 6),
        o2Ratio=round(o2_ratio, 6),
        atmosphericPressure=round(atmospheric_pressure, 3),
        averageTemperature=round(effective_temp, 2),
        toxinRatio=round(avg_toxin, 4),
        habitabilityScore=round(habitability_score, 4),
    )
```

### 4. Effets terraformation calibrés (source : `TerraformingEffectsController.cs`)

Le SDK calibre :
- `HeatWave` : `+5.0K × intensity` par événement
- `ColdSnap` : `-5.0K × intensity` par événement

Dans `terraform_action_definitions()` actuel, `Heat` est à `tempDelta=8.0` sur 3 ticks → 2.67K/tick. C'est cohérent avec le SDK (5K en un coup vs 8K en 3 ticks = 2.67K/tick continu).

**Aucun changement requis sur les action definitions actuelles** — elles sont déjà dans la bonne plage.

---

## Ce qui N'EST PAS récupérable

Les éléments suivants sont spécifiques à l'architecture BepInEx/IL2CPP et n'ont aucun sens dans un projet Python/Unity natif :

- **HarmonyX patches** (`[HarmonyPatch]`, `Prefix`, `Postfix`, `Transpiler`) — mécanisme de patching runtime JIT
- **BepInEx lifecycle** (`BasePlugin`, `ManualLogSource`, `Awake/OnDestroy` BepInEx)
- **IL2CPP interop** (`Il2CppString`, `Il2CppArray`, `Il2CppInterop`, `System.Type` safety rules)
- **Reflection IL2CPP** (`ReflectionHelpers.GetFieldValue`, `SafeInvoke`)
- **Wrappers d'accès jeu** (`GameApi.wrapper.basegame`, `Native.basegame`, `PlanetWrapper.GetCurrent()`)
- **EnhancedEventBus** — remplacé par `SimulationEvent` + tick loop dans ce projet
- **Tous les patches Harmony** (`PlanetClimatePatches`, `TerraformingEffectsPatches`) — dans le jeu Terraformation, la source de vérité est Python côté serveur, pas des patches runtime

---

## Plan d'implémentation

### Vue d'ensemble des dépendances

```
models.py                     ← AtmosphericState (Pydantic)
    ↓
logic.py                      ← compute_atmospheric_state() + cell_habitability_score()
    ↓
runtime.py                    ← AtmosphericState calculé en fin de open_region()
    ↓
server.py                     ← /commands/open-region retourne atmosphericState
    ↓
SimulationContracts.cs        ← struct AtmosphericState C# miroir
    ↓
SimulationContractFactory.cs  ← peupler AtmosphericState depuis RegionState
    ↓
TerraformHUD.cs               ← afficher O₂%, CO₂%, pression, score
TerraformProgressTracker.cs   ← slider depuis habitabilityScore
    ↓
Mcp/server.py                 ← tool get_atmospheric_state()
```

---

### Phase 1 — Sprint D : AtmosphericState (priorité immédiate)

**Prérequis** : Sprint C (persistance régionale) et Sprint A (hydrologie) doivent être finalisés en parallèle. AtmosphericState ne les bloque pas mais en dépend pour la qualité des données.

#### Étape 1 — `models.py` : ajouter `AtmosphericState`

Fichier : `SimulationCore/terraformation_sim/models.py`

```python
class AtmosphericState(BaseModel):
    co2Ratio: float = 0.0004          # Fraction CO₂ [0..1] — Terre ≈ 0.0004
    o2Ratio: float = 0.0              # Fraction O₂ [0..1] — Terre ≈ 0.21
    atmosphericPressure: float = 0.6  # kPa — Mars initial ≈ 0.6, Terre ≈ 101
    averageTemperature: float = -60.0 # °C — Mars initial ≈ -60°C
    toxinRatio: float = 0.0           # Fraction toxines [0..1]
    habitabilityScore: float = 0.0    # Score global habitabilité [0..1]
```

Ajouter `atmosphericState: AtmosphericState` à `RegionState` :
```python
class RegionState(BaseModel):
    ...
    atmosphericState: AtmosphericState = Field(default_factory=AtmosphericState)
```

Exporter dans `__init__.py`.

#### Étape 2 — `logic.py` : `compute_atmospheric_state()` + `cell_habitability_score()`

Fichier : `SimulationCore/terraformation_sim/logic.py`

Ajouter les deux fonctions telles que définies dans la section Formules ci-dessus. Exporter `compute_atmospheric_state` et `cell_habitability_score` dans `__init__.py`.

**Règle** : `compute_atmospheric_state([])` doit retourner un `AtmosphericState()` valide sans crash.

#### Étape 3 — `runtime.py` : peupler `atmosphericState` lors de `open_region`

Fichier : `SimulationCore/terraformation_sim/runtime.py`

Dans `_build_region_state()` (ou dans `open_region()`), après avoir généré les `cells`, appeler :
```python
region.atmosphericState = compute_atmospheric_state(cells)
```

#### Étape 4 — `server.py` : aucune modification requise

`/commands/open-region` délègue à `runtime.open_region()` qui retourne un `RegionState`. Le champ `atmosphericState` sera présent automatiquement si l'étape 3 est faite.

Vérification : `GET /commands/open-region?latitude=0.47&longitude=0.18` doit retourner un JSON avec `atmosphericState.habitabilityScore` non nul.

#### Étape 5 — `SimulationContracts.cs` : struct C# miroir

Fichier : `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs`

```csharp
[Serializable]
public struct AtmosphericState
{
    public float co2Ratio;
    public float o2Ratio;
    public float atmosphericPressure;
    public float averageTemperature;
    public float toxinRatio;
    public float habitabilityScore;
}
```

Ajouter `public AtmosphericState atmosphericState;` à `RegionState`.

**Règle SIMULATION_CONTRACTS.md** : les noms de champs sont en camelCase natif côté Python et C# — pas d'alias_generator.

#### Étape 6 — `SimulationContractFactory.cs` : propager `atmosphericState`

Fichier : `Game/Assets/Scripts/Simulation/Contracts/SimulationContractFactory.cs`

Dans `TryBuildRegionState()`, si la région vient du serveur, le champ est déjà désérialisé. Si elle est construite localement (fallback), calculer un `AtmosphericState` minimal depuis `cells` (ou laisser à zéro en attendant le serveur).

#### Étape 7 — `TerraformHUD.cs` : afficher les données atmosphériques

Fichier : `Game/Assets/Scripts/UI/TerraformHUD.cs`

Ajouter un panel "Atmosphère" dans le HUD avec :
- O₂% = `atmosphericState.o2Ratio * 100f`
- CO₂% = `atmosphericState.co2Ratio * 100f`  
- Pression = `atmosphericState.atmosphericPressure` kPa
- Score habitabilité = `atmosphericState.habitabilityScore * 100f`%

Brancher via `SetAuthoritativeRegionState()` qui reçoit déjà le `RegionState` complet.

#### Étape 8 — `TerraformProgressTracker.cs` : slider depuis `habitabilityScore`

Fichier : `Game/Assets/Scripts/World/TerraformProgressTracker.cs`

`SetAuthoritativeProgress()` existe déjà. Brancher : quand `hasAuthoritativeRegionState`, utiliser `authoritativeRegionState.atmosphericState.habitabilityScore` plutôt que le calcul local booléen.

#### Étape 9 — `Mcp/server.py` : tool `get_atmospheric_state`

Fichier : `Mcp/server.py`

```python
@mcp.tool
def get_atmospheric_state(latitude: float = 0.47, longitude: float = 0.18) -> dict:
    """
    Get the atmospheric state for a region.
    Returns co2Ratio, o2Ratio, atmosphericPressure, averageTemperature, toxinRatio, habitabilityScore.
    Does not require Unity to be running.

    Args:
        latitude: Normalized latitude [0, 1].
        longitude: Normalized longitude [0, 1].
    """
    region = _server_post("/commands/open-region", latitude=latitude, longitude=longitude)
    return region.get("atmosphericState", {})
```

#### Étape 10 — Mettre à jour `SIMULATION_CONTRACTS.md`

Ajouter `AtmosphericState` dans le tableau des structs et dans le tableau `RegionState`.

---

### Phase 2 — Tick atmosphérique (après Phase 1)

**Objectif** : l'atmosphère évolue entre les ticks selon l'effet de serre et les actions en cours.

#### Étape 11 — Enrichir `_tick_loop()` dans `runtime.py`

À chaque tick, après `process_pending_actions()`, appliquer un delta de température sur les cellules de la région active basé sur l'état atmosphérique courant :

```python
# Feedback atmosphérique simplifié — porté de ClimateSimulator.CalculateGreenhouseEffect
greenhouse_k = calculate_greenhouse_effect(
    self._world_state.region.atmosphericState.co2Ratio
)
# Appliquer 1% de l'effet par tick (progression lente et visible)
temp_delta_per_tick = greenhouse_k * 0.01
for cell in self._region_cells:
    cell.temperature += temp_delta_per_tick
```

Après cette évolution, recalculer et stocker `atmosphericState` depuis les cellules mises à jour.

#### Étape 12 — Variable d'env `CLIMATE_MODE`

Dans `server.py` / `runtime.py`, lire `os.environ.get("CLIMATE_MODE", "game_balanced")` et configurer les constantes `CO2_EFF`, `H2O_EFF`, `MAX_WARMING_K` en conséquence.

---

### Phase 3 — Événements climatiques (après Phase 2)

**Objectif** : déclencher des `SimulationEvent` quand des seuils atmosphériques sont franchis.

#### Étape 13 — Nouveaux `SimulationEventType`

Dans `models.py` :
```python
class SimulationEventType(IntEnum):
    ...
    ThermalEquilibrium = 9        # Température stable ±2K sur 10 ticks
    HabitabilityThreshold = 10   # habitabilityScore passe un palier (0.25, 0.5, 0.75, 1.0)
    AtmosphereFormed = 11         # atmosphericPressure > 10 kPa pour la première fois
```

Miroir C# dans `SimulationContracts.cs`.

#### Étape 14 — Déclencher depuis le tick

Dans `_tick_loop()`, après mise à jour de `atmosphericState`, vérifier et émettre les events.

---

### Phase 4 — Futur (Phase 7+, Corporations)

Ces éléments SDK sont pertinents mais ne bloquent pas les sprints actuels :

| Inspiration SDK | Application Phase 7 |
|---|---|
| `TerraformingOptimizer.OptimizeForTemperature()` | Conseil au joueur : "il faut X mines + Y serres pour atteindre 50% habitabilité" |
| `TerraformingOptimizer.OptimizeAll()` | Stratégie corporation multi-objectifs |
| `HabitabilityPredictor.PredictHabitabilityIn(days)` | ETA affiché dans le HUD |
| Gaz étendus (CH₄, SO₂) | Décomposer `toxinRatio` en types de gaz avec effets différents |
| `ClimateReport` | Rapport de progression consultable par les corporations |

---

## Fichiers concernés par la Phase 1

| Fichier | Modification | Taille estimée |
|---|---|---|
| `SimulationCore/terraformation_sim/models.py` | + `AtmosphericState` + champ dans `RegionState` | ~15 lignes |
| `SimulationCore/terraformation_sim/logic.py` | + `compute_atmospheric_state()` + `cell_habitability_score()` + constantes greenhouse | ~70 lignes |
| `SimulationCore/terraformation_sim/__init__.py` | + exports des nouvelles fonctions | ~6 lignes |
| `SimulationCore/terraformation_sim/runtime.py` | + appel `compute_atmospheric_state()` dans `_build_region_state()` | ~5 lignes |
| `DedicatedServer/app/server.py` | Aucune modification (aggrégation transparente) | 0 |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | + `struct AtmosphericState` + champ dans `RegionState` | ~15 lignes |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContractFactory.cs` | Mineur — propager le champ si construction locale | ~5 lignes |
| `Game/Assets/Scripts/UI/TerraformHUD.cs` | + panel atmosphère dans l'UI | ~40 lignes |
| `Game/Assets/Scripts/World/TerraformProgressTracker.cs` | + brancher habitabilityScore autoritatif | ~8 lignes |
| `Mcp/server.py` | + tool `get_atmospheric_state` | ~15 lignes |
| `Documentation/SIMULATION_CONTRACTS.md` | + ligne `AtmosphericState` dans les tableaux | ~10 lignes |

**Total estimé** : ~190 lignes nouvelles ou modifiées, réparties sur 11 fichiers.

---

## Critères de validation (Phase 1)

Reprendre les critères du Sprint D du ROADMAP :

1. `POST /commands/open-region` retourne un champ `atmosphericState` non vide avec `habitabilityScore ∈ [0, 1]`
2. `habitabilityScore` est strictement `> 0` pour le preset `Ocean` (eau + végétation → habitable)
3. `habitabilityScore` est proche de `0` pour le preset `Arid` (désert sec)
4. Le HUD affiche O₂%, CO₂%, pression atmosphérique et score sans erreur console
5. Le slider `TerraformProgressTracker` est cohérent avec `habitabilityScore` depuis les données serveur
6. `get_atmospheric_state(0.47, 0.18)` répond via MCP sans Unity ouvert
7. `compute_atmospheric_state([])` retourne `AtmosphericState()` valide sans exception
8. Les 5 presets de smoke test (`Ocean`, `Arid`, `Frozen`, `Coast`, `Basin`) passent toujours sans régression

---

## Décisions d'architecture

| Décision | Rationale |
|---|---|
| `co2Ratio` et `o2Ratio` déduits des cellules (végétation/toxines/eau) plutôt que nouveaux champs par cellule | Évite de casser les contrats `SimulationCellState` existants. Cohérent avec le modèle Python-authoritaire où la cellule modélise le sol/eau, pas l'atmosphère. |
| `AtmosphericState` ajouté uniquement à `RegionState`, pas à `ProjectionState` | Sprint D ne couvre que la région locale. La projection planétaire H3 reste serveur-autoritaire sans modification. |
| `GameBalanced` comme mode de calibration par défaut | CO2eff=1.5 offre une progression de terraformation perceptible à l'échelle du gameplay (quelques heures), pas des millions d'années réels. |
| Python est la source de vérité pour les formules | Les formules greenhouse sont dans `logic.py`, jamais duppliquées côté C# Unity. Le C# ne fait que désérialiser et afficher. |
| `cell_habitability_score()` est une nouvelle fonction parallèle à `is_cell_habitable()` | `is_cell_habitable()` reste pour la compatibilité descendante (booléen utilisé dans `compute_habitability_progress()`). Le score continu est utilisé uniquement dans `compute_atmospheric_state()`. |

---

## Références

| Fichier source SDK | Concept récupéré |
|---|---|
| `F:\ModPeraspera\SDK\PerAspera.GameAPI.Climate\Simulation\ClimateSimulator.cs` | `CalculateGreenhouseEffect()`, valeurs de calibration |
| `F:\ModPeraspera\SDK\PerAspera.GameAPI.Climate\Configuration\ClimateConfig.cs` | Presets GameBalanced / Realistic / Debug |
| `F:\ModPeraspera\SDK\PerAspera.GameAPI.Climate\Domain\Atmosphere\AtmosphereGrid.cs` | Patron d'agrégation cellulaire → état planétaire |
| `F:\ModPeraspera\SDK\PerAspera.GameAPI.Climate\TerraformingEffectsController.cs` | Calibration HeatWave (+5K), ColdSnap (-5K) |
| `F:\ModPeraspera\SDK\PerAspera.GameAPI.Climate\ClimateController.cs` | Architecture générale, pipeline activation/tick |
| `F:\ModPeraspera\SDK\.github\agents\per-aspera-sdk-coordinator.md` | Documentation `CalculateHabitabilityScore()` pondéré |

---

> **Voir aussi** :
> - [ROADMAP.md](ROADMAP.md) — Sprint D (AtmosphericState) + Phase 7 (Corporation)
> - [SIMULATION_CONTRACTS.md](SIMULATION_CONTRACTS.md) — Convention Python ↔ C#
> - [ARCHITECTURE.md](ARCHITECTURE.md) — Séparation Python serveur / Unity client
