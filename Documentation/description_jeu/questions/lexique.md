# Lexique — Terraformation & Colonisation Spatiale

> Référence rapide : termes de jeu avec leurs correspondances Python et C#.
> Source de vérité design : [Description_du_jeu.md](../Description_du_jeu.md)
> Modèles Python : `SimulationCore/terraformation_sim/models.py`
> Contrats C# : `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs`

---

## Termes de jeu

| Terme | Définition courte | §GDD | Modèle Python | Type C# |
|-------|-------------------|------|---------------|---------|
| **tick** | Unité de temps = 1 jour de jeu. À chaque tick : production, marchés, événements | §4 | `tick: int` (champ dans les modèles) | `int tick` |
| **tuile** | Hexagone H3 géospatial — unité exploitable de base. Possède terrain, ressources, bâtiments, marché local | §7 | `tileId: str` | `string tileId` |
| **corporation** | Entité joueur ou IA — argent, tuiles, bâtiments, contrats, réputation | §11 | `CorporationData` | `CorpCorporationData` |
| **état** | Entité politique — possède tuiles, population, marchés. IA par défaut, pilotable LLM | §12 | — (Phase 7.5) | — |
| **marché local** | Marché propre à une tuile — offre/demande locale, prix propagé aux tuiles adjacentes | §13 | `LocalMarketState` | `CorpLocalMarketState` |
| **marché global** | Organisme inter-étatique optionnel — agrège les marchés planétaires | §13 | `GlobalMarketState` (Phase 9.5) | `GlobalMarketState` (Phase 9.5) |
| **route commerciale** | Lien économique entre deux tuiles / ports — créée après une expédition réussie | §13 | `TradeRoute` | `CorpTradeRoute` |
| **expédition** | Unité en transit entre deux ports — explore et établit les routes | §13 | `ExpeditionUnit` | `CorpExpeditionUnit` |
| **ressource** | Matière (physique ou immatérielle) produite, consommée ou échangée sur le marché | §10 | `ResourceType` | `CorpResourceType` (Phase 9.5) |
| **réputation globale** | Score public de la corporation — visible par tous, accumulation des actions passées | §12 | `globalReputation: float` | `float globalReputation` |
| **relation bilatérale** | Score de confiance spécifique entre deux entités (Corp↔État, Corp↔Corp) | §12 | — (Phase 7.5) | — |
| **bureaucratie** | Stat d'État — ralentit toutes ses décisions. Délai = base × (1 + bureaucratie%) | §12 | — (Phase 7.5) | — |
| **corruption** | Stat d'État — passive (moins efficace) ou exploitable par les corps | §12 | — (Phase 7.5) | — |
| **nationalisation** | Processus par lequel un État reprend un bâtiment/tuile — délai = bureaucratie + corruption | §12 | — (Phase 7.5) | — |
| **habitabilityScore** | KPI environnemental global — mesure à quel point la planète est terraformée | §20 | `habitabilityScore: float` | `float habitabilityScore` |
| **sparkline** | Représentation ASCII des 10 derniers prix d'une ressource : ▁▂▃▄▅▆▇█ | §13 | `priceHistory: list[float]` | `float[] priceHistory` |
| **priceVelocity** | Taux de variation du prix entre deux ticks (détection tendance : hausse / baisse) | §13 | `priceVelocity: float` | `float priceVelocity` |

---

## ResourceType

| Valeur | Nom Python | Description | Catégorie | Bâtiment producteur |
|--------|-----------|-------------|-----------|---------------------|
| 0 | `Minerals` | Minerais bruts | Périodique | Mine |
| 1 | `Food` | Nourriture | Gathered / Processed | Ferme / Serre |
| 2 | `Energy` | Énergie électrique | Stocker | Centrale énergétique |
| 3 | `ResearchPoints` | Points de recherche | Immatériel | Laboratoire |
| 4 | `Waste` | Déchets industriels | Processed | Mine, Centrale |
| 5 | `Iron` *(Phase 9.5)* | Minerai de fer | Périodique | Mine |
| 6 | `Oxygen` *(Phase 9.5)* | Oxygène atmosphérique | Périodique | Serre, arbres |
| 7 | `Water` *(Phase 9.5)* | Eau disponible | Stocker / Périodique | Puits, électrolyseur |
| 8 | `Tech` *(Phase 9.5)* | Points technologiques | Immatériel | Laboratoire avancé |

---

## BuildingType

| Valeur | Nom Python | Nom C# | Description |
|--------|-----------|--------|-------------|
| 0 | `Mine` | `CorpBuildingType.Mine` | Extraction de minerais |
| 1 | `Farm` | `CorpBuildingType.Farm` | Production de nourriture et O₂ |
| 2 | `EnergyPlant` | `CorpBuildingType.EnergyPlant` | Production d'énergie |
| 3 | `Research` | `CorpBuildingType.Research` | Génère des ResearchPoints |
| 4 | `Road` | `CorpBuildingType.Road` | Infrastructure terrestre (Phase 9.1) |
| 5 | `SeaPort` | `CorpBuildingType.SeaPort` | Port maritime — expéditions Maritime (Phase 9.1) |
| 6 | `Spaceport` | `CorpBuildingType.Spaceport` | Port orbital — expéditions Orbital (Phase 9.1) |

---

## TradeRouteType / ExpeditionStatus

| Enum | Valeur | Description |
|------|--------|-------------|
| `TradeRouteType.Land` | 0 | Route terrestre (via Road) |
| `TradeRouteType.Maritime` | 1 | Route maritime (via SeaPort) |
| `TradeRouteType.Orbital` | 2 | Route orbitale (via Spaceport) |
| `TradeRouteActivityStatus.Active` | 0 | Route opérationnelle |
| `TradeRouteActivityStatus.Suspended` | 1 | Route suspendue |
| `ExpeditionStatus.InTransit` | 0 | Expédition en cours |
| `ExpeditionStatus.Success` | 1 | Expédition réussie — route établie |
| `ExpeditionStatus.Failed` | 2 | Expédition échouée |

---

## Conventions de code

| Convention | Description |
|-----------|-------------|
| Préfixe `Corp*` | Tous les types C# miroirs de modèles Python sont préfixés `Corp` (ex : `CorpTradeRoute` ↔ `TradeRoute`) |
| `_locked()` | Convention de nommage interne pour les méthodes du runtime qui s'exécutent sous `RLock` |
| `importlib` pattern | Les tests chargent les modules `.py` directement via `importlib.util.spec_from_file_location()`, puis les enregistrent dans `sys.modules["terraformation_sim.<name>"]` |
| `camelCase` | Tous les champs Pydantic utilisent `camelCase` (convention `model_config = ConfigDict(populate_by_name=True)`) |
| `[Serializable]` | Tous les structs/classes C# dans `SimulationContracts.cs` ont cet attribut pour `JsonUtility.FromJson<T>()` |
| `{"items":[...]}` | Les tableaux C# sont wrappés dans une classe `*List` avec un champ `items` (contrainte `JsonUtility`) |
