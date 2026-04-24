# Files de Construction Double — Questions de Clarification

> **Source design** : Description_du_jeu.md §9 — Bâtiments → Construction et chantiers
> 
> **État implémentation** : ❓ Implémentation partiellement visible, à clarifier

---

## Contexte design

**Deux files de construction indépendantes** (inspirée Victoria 3) :

- **File 1 — État/Corporation** : chantiers décidés explicitement par le joueur via Decision Queue
  - Réordonnable via HUD
  - Exemples : mines, centrales, laboratoires, EB améliorées, QG

- **File 2 — Population** : bâtiments construits **autonomement** par la population locale
  - Basée sur signaux marché (ressource manquante, prix élevé)
  - Exemples : maisons, petits ateliers, commerces
  - Population utilise ses propres ressources (achetées marché local)

**Partage de capacité** :
- Commune : `constructionCapacity` (produite par Entreprise de Bâtiment)
- Répartition selon **orientation politique** de l'État :
  - Libérale (20% État / 80% Pop)
  - Mixte défaut (50% / 50%)
  - Dirigiste (80% État / 20% Pop)

**Débordement** : si File 1 termine avec surplus de points → déborde sur chantier suivant (même tick)

**Interruption** : changement de propriétaire → chantier File 1 passe `suspended` (progression conservée)

---

## Questions à clarifier

### Q1 — État de l'implémentation
- [ ] Les deux files sont-elles implémentées en code ? Où ?
- [ ] Ou y a-t-il une seule file (État) et la Population ne construit-elle rien encore ?

### Q2 — Politique d'orientation
- [ ] L'orientation politique (libérale/mixte/dirigiste) est-elle implémentée dans `StateData` ?
- [ ] Comment change-t-elle ? Décision directe du joueur ou événement ?

### Q3 — Autonomie population
- [ ] Quel algorithme la population utilise-t-elle pour décider de construire ?
  - Simple : "ressource manquante sur marché local → construit bâtiment producteur" ?
  - Complexe : analyse offre/demande, prévision prix, cache pour X ticks ?
- [ ] Où est ce code ? `logic/market.py` ou ailleurs ?

### Q4 — Entreprise de Bâtiment (EB)
- [ ] L'EB est-elle actuellement implémentée comme bâtiment normal (`BuildingType.ConstructionCompany`) ?
- [ ] Comment calcule-t-elle `constructionCapacity` ? Via ses inputs (travailleurs, outils) ?
- [ ] **EB de fortune** : quand la population migre, crée-t-elle automatiquement une EB basique locale ?

### Q5 — Débordement de points
- [ ] Si File État a 18 pts/tick alloués et Mine coûte 60 pts :
  - Tick 1 : EB (90 pts) reçoit 18 → 18 total
  - Tick 2 : EB reçoit 18 → 36 total
  - Tick 3 : EB reçoit 18 → 54 total
  - Tick 4 : EB reçoit 18 → 72 total → termine, 12 pts résiduels débordent sur Mine ?
- [ ] Ou le débordement est-il ignoré (perte) ?

### Q6 — Suspension et reprise
- [ ] Quand propriétaire change et chantier suspend : 
  - Nouveau proprio peut le reprendre ou abandonner (remise à zéro) ?
  - Combien de ressources a-t-on perdu ? (ex : 72 pts d'EB = ?kg de fer)

### Q7 — Population construction vs État
- [ ] Si Population construit une Maison (File 2) et État en même temps construit une Mine (File 1) :
  - Maison coûte 30 pts, Mine coûte 60 pts, capacité 40 pts/tick, split 50%-50%
  - File État reçoit 20 pts → Mine avance (20/60)
  - File Pop reçoit 20 pts → Maison termine (20/30), 10 pts débordent sur suivant ?

---

## Réponses — Audit de l'implémentation réelle

### Q1 — État de l'implémentation
❌ **Les deux files n'existent pas.** Le système de construction actuel est **instantané** :
- `construct_building(corp_id, body_id, tile_id, building_type)` crée le bâtiment immédiatement sans délai
- Vérification : pas déjà le même type sur la tuile, tuile appartient à la corpo
- Aucun concept de `constructionCapacity`, de chantier multi-ticks, ni de file
- Le type `ConstructionCompany` (Entreprise de Bâtiment) **n'existe pas** dans l'enum `BuildingType`
- `BuildingType` actuel : `Mine`, `Farm`, `EnergyPlant`, `Research`, `Road`, `SeaPort`, `Spaceport` (7 types)

### Q2 — Politique d'orientation
❌ **Pas implémentée.**
- `StateData` a `bureaucracy`, `corruptionRate`, `toleranceThreshold`, `taxRate` mais aucune notion de `constructionOrientation` ou répartition libérale/dirigiste

### Q3 — Autonomie population
✅ **DÉCISION — La population pilote la demande marché, pas la construction directe.**
- La population **ne construit pas** de bâtiments elle-même
- Sa taille génère une **demande minimale automatique** sur le marché local :
  - Population croissante → demande en nourriture augmente
  - Population croissante → demande en matériaux de construction (BTP) augmente pour simuler le logement
  - Idem pour vêtements, énergie, eau selon la taille et classe sociale
- **C'est le marché qui révèle le besoin**, pas une file autonome de la population
- À implémenter : `compute_population_demand()` doit tenir compte de la taille totale, pas seulement des classes

### Q4 — Entreprise de Bâtiment (EB)
✅ **DÉCISION — EB simplifiée via `constructionCapacity` de tuile**
- Pas besoin de `BuildingType.ConstructionCompany` explicite
- Chaque tuile possède une **valeur de capacité de construction** (ex : 120 pts/tick)
- Cette valeur reflète implicitement les ressources et main-d'œuvre locales
- Détail d'initialisation (comment est calculée cette valeur) → à définir en Phase future

### Q5 — Capacité de construction et timing
✅ **DÉCISION — Construction multi-ticks selon `constructionCapacity` de la tuile**
- La construction **n'est pas instantanée** — elle dépend de la capacité de la tuile
- Règle : `ticksRequired = ceil(buildingCost / constructionCapacity)`
- Exemple : capacité tuile = 120 pts/tick, bâtiment = 60 pts → **1 tick** (instantané dans ce cas)
- Exemple : capacité tuile = 30 pts/tick, bâtiment = 120 pts → **4 ticks**
- Surplus de capacité non utilisée **déborde sur le chantier suivant dans la même tick**
- Un chantier passe par des statuts : `pending` → `in_progress` (avec `progressPoints`) → `done`

### Q6 — Suspension et changement de propriétaire
✅ **DÉCISION — Constructions en cours perdues, bâtiments terminés conservés**
- Changement de propriétaire → chantiers **en cours sont annulés et perdus** (pas de remboursement)
- Les **bâtiments déjà construits restent sur la tuile** (le nouveau propriétaire en hérite)
- Si changement d'État : toutes les tuiles passent sous le nouvel État
- Si des tuiles appartenaient à une corporation : le nouvel État peut décider de **nationaliser** → malus diplomatique + réputation pour la corpo

### Q7 — Files et bâtiments hors-file
✅ **DÉCISION — Une seule file (État/Corporation), structures "légères" hors file**
- Pas de file séparée pour la population
- La population est **assimilée à l'État** pour la construction : une maison construite par la pop compte comme un bâtiment d'État
- **Seules les structures importantes passent par la file** : routes, fermes, usines, mines, centrales, laboratoires
- Les constructions "légères" (logements, petits ateliers) sont considérées hors file — elles se résolvent au tick suivant sans occuper de slot dans la queue
---

## Écart design ↔ implémentation (mis à jour)

| Élément design | État réel | Décision |
|---------------|-----------|----------|
| Construction instantanée | ✅ Actuel | ❌ À remplacer par multi-ticks |
| `constructionCapacity` par tuile | ❌ Inexistant | ✅ À ajouter |
| File de chantiers (État/Corp) | ❌ Inexistant | ✅ À ajouter (structures importantes seulement) |
| File Population autonome | ❌ Inexistant | ❌ **Abandonnée** — pop pilote la demande marché |
| Population génère demande minimale marché | ❌ Inexistant | ✅ À implémenter |
| EB (`BuildingType.ConstructionCompany`) | ❌ Inexistant | ❌ **Abandonnée** — remplacée par `constructionCapacity` |
| Orientation politique (libérale/dirigiste) | ❌ Inexistant | ❌ **Abandonnée** — une seule file État |
| Perte chantier en cours sur changement propriétaire | ❌ Inexistant | ✅ À implémenter |
| Nationalisation avec malus diplo + réputation | ❌ Inexistant | ✅ À implémenter (partiel : réputation existe) |
| Bâtiments construits conservés après changement | ❌ Non géré | ✅ Comportement attendu |
| `SocialClass` Poor/Middle/Rich | ✅ Modèle existe | ✅ Conservé |
| `apply_social_mobility()` | ✅ Implémenté | ✅ Conservé |
| `workerRatio` sur bâtiment (0→1) | ✅ Implémenté | ✅ Conservé |
