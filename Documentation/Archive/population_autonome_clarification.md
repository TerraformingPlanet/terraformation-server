# Population Autonome & Migrations — Questions de Clarification

> **Source design** : Description_du_jeu.md §9, §13 — Bâtiments, Marchés
> 
> **État implémentation** : ✅ `SocialClass` existe | ❓ Mobilité, migrations, EB fortune = ?

---

## Contexte design

### Population & catégories sociales
- Distribuée en **Poor** / **Middle** / **Rich**
- Chaque classe a **besoins différents** → influence demande marché
- Chacune **consomme ses propres ressources** (nourriture, énergie, logement, loisir)
- Les **salaires évoluent** selon l'économie locale → mobilité sociale

### Mobilité sociale
- **Poor → Middle** : après X ticks de salaire élevé, monte de classe
- **Middle → Rich** : après X ticks bien rémunéré, devient riche
- **Inverse** : perte emploi ou baisse salaire → descente sociale
- Effet : création de demande de produits de luxe (Rich) vs basiques (Poor)

### Migrations
- Population peut **migrer vers tuiles adjacentes** plus attractives :
  - Meilleur emploi local (salaire plus haut)
  - Ressources moins chères
  - Meilleure sécurité / infrastructure
- Migration a un **délai** et un **coût** (ex : 5 ticks, 10 crédits/habitant)
- Population qui quitte → tuile devient moins productive

### EB de fortune
- Quand population migre vers tuile **sans bâtiments** :
  - Crée spontanément une **EB de fortune** (entrée : villageois + outils basiques)
  - Très faible capacité (ex : +5 pts/tick)
  - Représente : "on se construit des abris"
- **C'est un vrai bâtiment EB** avec vraies entrées, pas un bonus magique
- Peut être remplacée par une EB normale construite par corpo propriétaire

---

## Questions à clarifier

### Q1 — Structure données population
- [ ] Où sont les données population réelles dans `ClaimedTile.population` ?
  - Nombre par classe (poorCount, middleCount, richCount) ?
  - Ou nombre total + % par classe ?
  - Ou objet détaillé avec salaires, emploi, satisfaction ?

### Q2 — Besoin/Consommation par classe
- [ ] Chaque classe consomme-t-elle différemment ?
  - Poor : nourriture basique, énergie pour habitat simple ?
  - Rich : produits de luxe, services, énergie accrue ?
- [ ] Où implémenté ? `logic/market.py` ?

### Q3 — Mobilité sociale
- [ ] Est-elle implémentée ? `apply_social_mobility()` — qu'y a-t-il dedans vraiment ?
- [ ] Quels sont les paramètres ?
  - Salaire seuil pour passer Middle ?
  - Délai (X ticks) ou immédiat après franchissement ?
  - Y a-t-il un malus si perte d'emploi ?

### Q4 — Migrations inter-tuiles
- [ ] Migrations implémentées ou TODO ?
- [ ] Comment décide-t-elle ? Calcul attractivité tuile adjacente (emploi + prix ressources) ?
- [ ] Délai : combien de ticks ? Y a-t-il des ressources bloquées pendant migration ?

### Q5 — EB de fortune
- [ ] Implémentée ?
- [ ] Comment détecte-t-on "pop arrive sur tuile sans bâtiments" ?
- [ ] L'EB est-elle détruite quand corpo construit une EB "normale" ? Ou coexistent-elles ?

### Q6 — Départ population (tuile abandonnée)
- [ ] Si population part (migration ou disparition) :
  - Qu'arrive-t-il aux bâtiments existants ? Restent productifs sans travailleurs ?
  - Que devient l'EB de fortune ?

### Q7 — Équilibre prix/salaire
- [ ] Comment la pop obtient-elle du travail ? Y a-t-il un marché du travail ou c'est implicite ?
- [ ] Si no jobs sur tuile → pop quitte automatiquement ? Ou reste en chômage (malus satisfaction) ?

---

## Réponses

### Q1 — Structure données population

✅ **EXISTANT** : `ClaimedTile.population = list[PopulationTier]` où `PopulationTier = {socialClass, count}`.
- Trois classes : `Poor`, `Middle`, `Rich`

✅ **DÉCISION — Revenu moyen par classe :**
Chaque classe sociale a un **revenu moyen** (`avgIncome: float`) enregistré dans `PopulationTier`, qui varie chaque tick en fonction des actions sur la tuile.

```
PopulationTier:
  socialClass: SocialClass     # Poor / Middle / Rich
  count: int                   # nombre de personnes
  avgIncome: float             # revenu moyen de cette classe sur cette tuile
```

**Mécanique :**
- Revenu moyen = fonction de l'emploi disponible sur la tuile (`workerRatio × salaire du bâtiment`)
- Si `workerRatio` faible (chômage élevé) → `avgIncome` chute → consommation marché réduite
- Si une corporation construit une usine (Mine, Farm...) et emploie des travailleurs → `workerRatio` monte → `avgIncome` augmente → demande marché locale croît

**Exemple :**
- Tuile avec 1000 Poor, 50% chômage, `avgIncome = 5 cr/tick` → faible consommation de `Food`
- Une Corp construit une Mine (emploie 500 Poor) → `workerRatio = 0.5 → 1.0` → `avgIncome = 5 → 20 cr/tick`
- → La tuile consomme 4× plus de `Food` et commence à générer de la demande d'`Energy`

**Mobilité sociale** : dépend du `avgIncome` (seuils à définir plus tard).

---

### Q3 — Mobilité sociale

✅ **EXISTANT** : `apply_social_mobility(tile, employment_ratio)` dans `logic/market.py`
- `Poor → Middle` : taux proportionnel à `employment_ratio`
- `Middle → Poor` : pression chômage `(1 - employment_ratio)`
- `Middle → Rich` : seulement si `employment_ratio >= threshold` (prospérité)
- Appliqué chaque tick via `runtime.py` ligne ~358
- Pas de délai (immédiat par tick) — la granularité du tick fait office de délai naturel

---

### Q4 — Migrations inter-tuiles : deux mécanismes distincts

✅ **DÉCISION** : Les migrations fonctionnent via **deux couches indépendantes** :

**Couche 1 — Porosité naturelle (tuiles limitrophes)**
- Toutes tuiles limitrophes ont un **micro-flux passif** de population chaque tick
- `flux = baseMigration × (pop_source - pop_cible) / pop_source` (flux vers le moins peuplé)
- Indépendant des routes, indépendant de l'attractivité économique
- Représente la diffusion naturelle : frontaliers, pendulaires, mouvements spontanés

**Couche 2 — Migration économique (via routes)**
- Une **route** entre deux tuiles active un flux migratoire **dirigé** par l'attractivité
- `flux_route = routeCapacity × attractivityDelta` où `attractivityDelta = f(emploi, salaire, ressources)`
- La pop migre **vers la tuile la plus attractive** le long de la route
- La route peut être terrestre (Road), maritime (SeaPort), spatiale (Spaceport)
- Représente la migration intentionnelle : travailleurs qui cherchent de l'emploi

**Séparation claire :**
- Porosité = fond permanent, non contrôlable
- Migration route = flux stratégique, contrôlable (l'État peut ouvrir/fermer une route)

---

### Q5 — EB de fortune

✅ **DÉCISION** : L'EB de fortune est une **structure passive spontanée** créée par la population sur une tuile gouvernée sans bâtiment de construction.

**Principe :**
- Si une tuile a de la population mais **aucun bâtiment EB** → la pop construit d'elle-même avec les matériaux disponibles localement
- Entrées requises : `Wood` (rondin de bois) + outils basiques (abstrait)
- Capacité très faible : ex. `+5 pts constructionCapacity/tick` (vs une EB normale à `+30`)
- Représente : cabanes, abris rudimentaires, chantiers artisanaux
- **N'est pas construite via la file** — apparaît automatiquement si conditions remplies (pop > seuil + Wood disponible sur marché local)

**Cycle de vie :**
- Créée automatiquement si : `population > 0` ET `Wood sur marché local > seuil minimal` ET `aucune EB existante`
- Détruite (remplacée) dès qu'une EB normale est construite par l'entité propriétaire
- Si la pop quitte la tuile → EB de fortune disparaît aussi

---

### Q2 + Q7 — Consommation par classe & marché du travail

✅ **DÉCISION** : Système d'emploi **à la Victoria 3** — chaque bâtiment requiert un quota de population d'une classe sociale spécifique.

**Principe :**
- Chaque bâtiment a un champ `employmentSlots: dict[SocialClass, int]` (quota par classe)
- Chaque tick, le bâtiment **prélève** des travailleurs dans la population de la tuile
- `workerRatio = min(1.0, popDisponible / quotaRequis)`
- Si `workerRatio < 1.0` → **carence** → production réduite proportionnellement

**Exemple — Mine niveau 1 :**
```
Mine (niv 1):
  employmentSlots: {Poor: 50}
  production: Minerals × workerRatio
  → Si tuile a 30 Poor disponibles : workerRatio = 0.6 → production à 60%
```

**Exemple — Laboratoire de recherche :**
```
Research:
  employmentSlots: {Middle: 20, Rich: 5}
  → Requiert des cols blancs + chercheurs senior
```

**Carence → opportunité de migration :**
- Si `workerRatio < seuil_carence` (ex: < 0.7) → la tuile émet un **signal d'attractivité** élevé
- Ce signal amplifie le flux migratoire entrant via les routes (couche 2)
- Crée une boucle naturelle : bâtiment sous-peuplé → attire des migrants → se remplie progressivement

**Consommation différenciée par classe (Q2) :**
- `Poor` : consomme `Food` + `Energy` basique (logement simple)
- `Middle` : consomme `Food` + `Energy` + `Tech` (confort)
- `Rich` : consomme `Food` + `Energy` + `Tech` + produits de luxe (à définir)
- → Géré via `compute_population_demand()` avec pondération par classe et count

✅ **DÉCISION** :
- Si pop part (migration, désastre) → bâtiments restent mais `workerRatio` chute → production diminue proportionnellement
- EB de fortune disparaît (plus personne pour la maintenir)
- Bâtiments formels (Mine, Farm, etc.) restent en place mais inactifs jusqu'au retour de travailleurs
