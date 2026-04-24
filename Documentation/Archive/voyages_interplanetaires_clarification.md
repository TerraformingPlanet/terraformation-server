# Voyages Interplanétaires — Questions de Clarification

> **Source design** : Description_du_jeu.md §16 — Voyages interplanétaires
> 
> **État implémentation** : ❓ Remplacé par Expéditions (Phase 9) ou à implémenter ?

---

## Contexte design

### Voyages de vaisseaux/expéditions
- **Durée** : calculée à partir de :
  - Distance physique (UA ou km)
  - Technologie de propulsion disponible
  - Modificateurs terrain (ex : passer par astéroïdes = +10 ticks)
- **Propriété** : vaisseaux appartiennent à un État ou corporation
- **Commodités** : louables via contrat (ex : État A loue vaisseau à Corp B)

### Événements en trajet
- **Aléatoires** : piraterie, panne moteur, opportunité de découverte
- **Narratifs** : rencontre alien surprise, tempête solaire intersidérale
- **Conséquences** :
  - Piraterie → cargo volé + malus relation
  - Panne → délai allongé + besoin réparation
  - Opportunité → ressources bonus trouvées

### Routes spatiales fixes
- Une fois créée (exploration manuelle), une route spatiale devient une **connexion permanente** entre systèmes
- Les expéditions futures emprunteraient cette route (path trouvé)
- Les routes peuvent être **bloquées** (événement type : astéroïde en orbite) ou **perdues** (technologie oubliée)

---

## Questions à clarifier

### Q1 — Relation avec Expéditions Phase 9
- [ ] Phase 9 (ExpeditionUnit, TradeRoute) couvre-t-elle les voyages interplanétaires ? Comment ?
- [ ] `ExpeditionUnit` : est-ce un conteneur de ressources transportées ou un vaisseau nommé ?
- [ ] `TradeRoute` : c'est une route permanente créée après première expédition réussie ?

### Q2 — Calcul de durée
- [ ] Formule concrète :
  - Distance (km) ÷ vitesse (km/tick) = ticks de base ?
  - Modificateurs terrain : quels sont les modificateurs possibles et leurs impacts ?
- [ ] Exemple : Terre → Mars (225M km) avec fusée tech-1 : X ticks ? Y ticks avec tech-5 ?

### Q3 — Propriété et usage
- [ ] Un vaisseau appartient-il à une corporation ou à un État ?
- [ ] Peut-il être **loué** via contrat ? (ex : État A loue à Corp B = commodités et réparations à État A)
- [ ] Peut-on en perdre la propriété (échange, destruction) ?

### Q4 — Événements en trajet
- [ ] Tirés aléatoirement à chaque tick du trajet ou au départ/arrivée seulement ?
- [ ] Probabilité : 5% par tick ? Configurable ?
- [ ] Comment affectent-ils la durée ? Immédiatement (+X ticks) ou après diagnostic à l'arrivée ?

### Q5 — Piraterie
- [ ] Peut-on être pirate ? Attaquer une expédition ennemie ?
- [ ] Y a-t-il une défense (escorte armée, blindage) ou c'est 100% aléatoire ?
- [ ] Perte cargo : totale ou partielle ? Récupérable ?

### Q6 — Routes permanentes
- [ ] Une fois créée (ex : première expédition Terre→Mars réussie), la route reste active ?
- [ ] Les futures expéditions l'utilisent automatiquement (path optimal) ?
- [ ] Comment les routes se perdent-elles ? (événement, tech oubliée, délai sans usage ?)

### Q7 — Multi-système vs local
- [ ] Voyages interplanétaires ≠ routes commerciales locales (Phase 9) ?
  - Interplanétaires : entre SYSTÈMES stellaires (Sol → Kepler-442)
  - Locales : entre CORPS d'un même système (Terre → Mars)
  - Ou c'est la même chose ?

---

## Réponses

### Q7 — Scope : intra-système uniquement (pour l'instant)

✅ **DÉCISION** : Les voyages se limitent au **système solaire** (et à la planète locale) dans les phases actuelles.
- Voyages **intra-système** (Terre → Mars, Mars → Jupiter, etc.) = `TradeRouteType.Orbital` → **déjà modélisé**
- Voyages **inter-systèmes** (Sol → Kepler-442) → **Phase 12+**, architecture à penser mais pas implémenter
- La conception doit rester **extensible** : `bodyId` dans `TradeRoute` et `ExpeditionUnit` devra devenir `systemId + bodyId` le moment venu

---

### Q1 — Relation avec Phase 9 (ExpeditionUnit / TradeRoute)

✅ **EXISTANT** :
- `TradeRoute` : route permanente entre deux tuiles (même corps), types `Land` / `Maritime` / `Orbital`
  - Champs : `fromTileId`, `toTileId`, `bodyId`, `pathTileIds`, `ownerCorpId`, `baseEfficiency`, `currentEfficiency`
  - Une route Orbital = connexion entre deux corps du même système (ex: spaceport Terre ↔ spaceport Mars)
- `ExpeditionUnit` : unité en transit sur une route, avec `ticksRemaining` / `totalTicks` / `status`

✅ **MANQUANT à ajouter** :
- `cargo: dict[ResourceType, float]` sur `ExpeditionUnit` — pour savoir ce qui est transporté
- `ownerCorpId` ou `ownerStateId` sur `ExpeditionUnit` — pour distinguer État vs Corp

---

### Q2 — Calcul de durée

✅ **DÉCISION** : `totalTicks` est calculé à la création de l'expédition selon :
```
totalTicks = ceil(distanceUA / speedFactor × techMultiplier)
```
- `distanceUA` : distance entre les deux corps (paramètre du système solaire)
- `speedFactor` : vitesse de base du type de vaisseau
- `techMultiplier` : réduit avec niveau technologique de propulsion (à définir)
- Modificateurs terrain (astéroïdes, etc.) → `+X ticks` ajoutés lors de la création

Exemple indicatif (à calibrer) :
- Terre → Mars (~1.5 UA moyen) avec tech-1 : ~10 ticks
- Terre → Mars avec tech-3 : ~4 ticks

---

### Q3 — Propriété et usage

✅ **DÉCISION** :
- Un vaisseau (ExpeditionUnit) appartient à une **corporation OU un État** (`ownerCorpId` étendu en `ownerEntityId`)
- Louable via **contrat** : l'État A prête sa route spatiale, la Corp B fournit le vaisseau (cf. exemple Space Lille dans `contrats.md`)
- Destruction possible (événement piraterie/panne grave) → vaisseau retiré de la simulation

---

### Q4 — Événements en trajet

✅ **DÉCISION** : Les événements utilisent le système `EventData` existant (Phase 8).
- Tirés **aléatoirement chaque tick** pendant le transit (pas seulement au départ/arrivée)
- Probabilité faible par tick (ex: 3%) — configurable
- Effets immédiats sur l'expédition :
  - Panne → `ticksRemaining += X` (délai)
  - Piraterie → perte partielle de `cargo`
  - Découverte → bonus ressources à l'arrivée

---

### Q5 — Piraterie

✅ **DÉCISION** : Piraterie comme **événement aléatoire** pour l'instant (pas d'action joueur active).
- Attaque active entre joueurs (escortes, interception) → **Phase 12+**
- Perte cargo : **partielle** (ex: 20-50% du cargo volé), jamais totale
- Pas de récupération du cargo perdu (simplification MVP)

---

### Q6 — Routes permanentes

✅ **DÉCISION** : Conforme au modèle `TradeRoute` existant.
- Route créée après **première expédition réussie** entre deux spaceports → `TradeRoute` persistée
- Les expéditions futures utilisent automatiquement la route (path pré-calculé)
- Route **suspendue** (`TradeRouteActivityStatus.Suspended`) si : spaceport détruit, événement bloquant
- Route **perdue** : uniquement si les deux spaceports sont détruits (pas de "technologie oubliée" pour l'instant)
