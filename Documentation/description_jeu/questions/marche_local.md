# Marché local : fonctionnement

## Structure hiérarchique

Les marchés suivent la hiérarchie H3 du monde :

```
Tuile → Planète → Système stellaire → Marché global (inter-étatique, optionnel)
```

Deux tuiles connectées par une route voient leurs prix s'influencer mutuellement.

---

## Prix : offre et demande dynamique

- Les prix sont déterminés par l'offre et la demande à chaque tick
- La population locale **consomme** passivement les ressources du marché local
- L'État possède des tuiles avec des bâtiments de production (fermes, usines…) qui alimentent le marché
- Les corporations produisent et vendent sur le marché local via leurs bâtiments

### Propagation des prix
- L'impact se propage **à chaque tick** entre tuiles connectées, **atténué par la distance**
  - Exemple : pénurie sur tuile A → -50% sur A, -30% sur tuile B reliée (1 saut), -10% sur C (2 sauts)
- Sans route entre deux tuiles, aucune propagation

---

## Population et niveaux de richesse

- La population d'une tuile est distribuée en **catégories sociales** (pauvres, classes moyennes, riches, etc.)
- Chaque catégorie a des besoins différents :
  - Pauvres → nourriture, vêtements de base
  - Classes moyennes → biens manufacturés, confort
  - Riches → luxe, tourisme, voyages interplanétaires
- La richesse d'un individu **évolue dans le temps** :
  - Un ouvrier de mine (mal payé) qui trouve un poste en usine (mieux payé) voit son niveau de vie augmenter
  - Après un certain nombre de ticks à un niveau supérieur, il change de catégorie sociale
  - Une partie de la catégorie supérieure peut progresser encore vers la suivante

### Mobilité sociale et migrations
- Si une corporation construit des usines et recrute massivement, la richesse locale augmente
- En cas de manque de main-d'œuvre sur une tuile, des **migrations** peuvent se produire depuis des tuiles voisines (événement déclenché)
- Les populations peuvent se déplacer vers des tuiles plus attractives (emploi, conditions de vie)

---

## Routes commerciales

- Une route doit être **explorée puis construite**
- Processus :
  1. Un État ou une corporation lance une **expédition d'exploration** entre deux tuiles éloignées
  2. Les explorateurs trouvent un chemin — sa durée de trajet est calculée selon le terrain
     - Exemple : montagne → +10 ticks de trajet par case traversée
  3. Une fois le chemin trouvé, on peut construire la route/chemin physique
- Sans route construite, les deux tuiles ne se voient pas sur le marché

### Routes spatiales
- Fonctionnent sur le même principe mais entre planètes/systèmes
- Nécessitent probablement une infrastructure dédiée (spatioport) — à préciser

---

## Régulation des marchés

### Marché national
- Régulé par l'État via taxes et quotas
- Le niveau de corruption de l'État influence l'efficacité de cette régulation
- Une corporation peut corrompre l'État pour ignorer les taxes ou obtenir des avantages commerciaux

### Marché global (inter-étatique)
- N'existe pas par défaut — se crée via un **organisme inter-étatique**
- Formation :
  - **A)** Événement aléatoire si plusieurs États ont un niveau de relation suffisant
  - **B)** Un État ou un joueur déclenche activement une "convention internationale" (action coûteuse)
  - **C)** Les deux selon le contexte — peut aussi être initié par un agent LLM
- Les corporations peuvent tenter de **corrompre cet organisme** pour influencer les règles commerciales mondiales
- Si complètement corrompu → devient une façade au service des corporations (objectif de fin de partie possible)

---

## Modèle d'implémentation actuel — Marché par territoire (2026-04-20)

> **Décision d'architecture** : le marché local est organisé par **territoire connexe** H3, pas par corporation ou par tuile individuelle.

### Territoire connexe

- Un territoire est une **composante connexe** de tuiles H3 appartenant à la même entité (corp ou État) sur le même corps céleste.
- Deux tuiles sont connexes si elles sont voisines selon `h3.grid_disk(tile_id, 1)`.
- `territory_id = "{owner_entity_id}::{min(tile_ids)}"` — déterministe et stable.

### LocalMarketState par territoire

Chaque territoire connexe possède un `LocalMarketState` distinct avec :

| Champ | Description |
|-------|-------------|
| `territoryId` | identifiant unique du territoire |
| `ownerEntityId` | corp_id ou state_id propriétaire |
| `tileIds[]` | toutes les tuiles H3 du territoire |
| `listings[]` | prix calculés à chaque tick |
| `taxRate` | taux de taxe fixé par l'État |
| `connectivity` | 0.0–1.0, multiplie l'offre effective |
| `tickComputed` | tick de dernière mise à jour |

### Tick marché

À chaque tick :
1. Pour chaque entité → `compute_territories()` (BFS H3) → liste de composantes connexes
2. Pour chaque composante → création ou mise à jour d'un `LocalMarketState`
3. Offre = offre brute × `connectivity`
4. Purge des territoires obsolètes (entité n'a plus ces tuiles)

### API

| Endpoint | Rôle |
|----------|------|
| `GET /game/market` | lister tous les marchés |
| `GET /game/market/entity/{entity_id}` | marchés d'une entité (list) |
| `GET /game/market/by-tile/{tile_id}` | marché du territoire contenant la tuile |

---

## Routes commerciales — Design (décidé 2026-04-20)

### Types de route

| Type | Prérequis port A | Prérequis port B | Portée |
|------|-----------------|-----------------|--------|
| **Land** | `BuildingType.Road` | `BuildingType.Road` | Même corps céleste |
| **Maritime** | `BuildingType.SeaPort` | `BuildingType.SeaPort` | Même corps, tuiles côtières |
| **Orbital** | `BuildingType.Spaceport` | `BuildingType.Spaceport` | Corps différents |

### Modèles

**`TradeRoute`**
- `id`, `routeType` (Land/Maritime/Orbital)
- `fromTileId`, `toTileId`, `bodyId`
- `pathTileIds: list[str]` — tuiles traversées (mémorisées à la réussite de l'expédition)
- `ownerCorpId` — corp initiatrice
- `knownByEntityIds: list[str]` — propagation de connaissance au fil du temps
- `status` : Active / Suspended
- `baseEfficiency: float` — 1.0 à la création
- `currentEfficiency: float` — recalculé chaque tick selon l'état des tuiles du path
- `portMalusFrom: float`, `portMalusTo: float` — malus si port absent/démoli

**`ExpeditionUnit`**
- `id`, `ownerCorpId`
- `fromPortTileId`, `toPortTileId`, `bodyId`
- `routeType` (Land/Maritime/Orbital)
- `ticksRemaining: int`
- `pathTileIds: list[str]` — chemin calculé au départ (BFS H3 ou orbital direct)
- `status` : InTransit / Success / Failed
- `isPhantom: bool` — True pour les routes spatiales temporaires

### Cycle de vie d'une route

```
1. Corp construit un port (Road / SeaPort / Spaceport) sur une tuile
2. Corp lance une Expédition depuis ce port vers un autre port connu
3. ExpeditionUnit créée → tick-based (pattern identique à SpaceTravel)
4. Pendant le voyage (chaque tick) :
   - Événements probabilistes selon terrain des tuiles traversées
   - Malus : toxin, inondation, gel → ralentissement ou risque d'échec
   - Bonus : météo favorable, tech → réduction ticksRemaining
5a. SUCCÈS → TradeRoute créée et persistée, pathTileIds mémorisé
5b. ÉCHEC  → EventType.ExpeditionLost, aucune route créée
6. Route Active → propagation de prix à chaque tick :
   Land     → 70 % de l'écart de prix comblé
   Maritime → 85 %
   Orbital  → 50 %
```

### Propagation de connaissance (ownership progressif)

- La route appartient à la corp initiatrice (`ownerCorpId`)
- Si la route aboutit sur un territoire appartenant à une autre entité :
  - Chaque tick de transit incrémente un compteur `knowledgeTicks`
  - Après `KNOWLEDGE_TRANSFER_TICKS` (ex. 10 ticks), l'entité cible est ajoutée à `knownByEntityIds`
  - L'entité cible peut alors utiliser la route comme si c'était la sienne

### Port démoli

- La route passe en `status = Suspended` (non supprimée)
- `portMalusFrom` ou `portMalusTo` appliqué sur `currentEfficiency`
- Route se réactive automatiquement si le port est reconstruit

### Efficacité dynamique (tick)

```
currentEfficiency = baseEfficiency
pour chaque tile dans pathTileIds :
  si tile.toxinLevel > 0.5  → efficiency -= 0.10
  si tile.waterRatio > 0.90 → efficiency -= 0.05
  si tile.temperature < -40 → efficiency -= 0.05
currentEfficiency = clamp(efficiency - portMalusFrom - portMalusTo, 0.1, 1.0)
```

### Waypoints / escales (différé Phase 10+)

- Architecture prévoit `pathTileIds` comme liste de segments (Earth → SpaceStation → Moon → Mars)
- Non implémenté Phase 9 — route directe uniquement
- Orbital Phase 9 : route point-à-point sans escale intermédiaire

### Propagation de prix entre marchés connectés

```
pour chaque route Active :
  market_A = LocalMarketState du fromTileId
  market_B = LocalMarketState du toTileId
  attenuation = routeType.attenuation × currentEfficiency
  pour chaque ResourceType :
    ecart = price_A - price_B
    market_A.price -= ecart × attenuation × 0.5
    market_B.price += ecart × attenuation × 0.5
```
