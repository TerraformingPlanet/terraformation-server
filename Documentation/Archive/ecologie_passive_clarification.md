# Écologie Passive — Questions de Clarification

> **Source design** : Description_du_jeu.md §5.2 — Moteur écologique (terraformation)
> 
> **État implémentation** : ✅ `habitabilityScore` | ❓ Arbres, animaux, biodiversité = ?

---

## Contexte design

### Principes
- **Pas de seuil binaire** : fonction continue de malus selon écart environnemental
- **Évolution passive** : nature évolue d'elle-même, même sans actions humaines
- **Chaînes causales** : déforestation → perte animaux → moins O₂ → dégradation atmo

### Indicateurs par tuile
- Température (°C)
- Atmosphère : O₂, CO₂, azote, eau, autres
- Albédo (réflectivité)
- Altitude, relief
- **Biodiversité** : densité faune, densité flore / végétation
- **Classe hydrologique** : océan, côte, lac, sec, gelé

### Événements écologiques
- **Arbres** : plantés artificiellement (terraformation) ou croissance passive si conditions OK
- **Animaux** : apparaissent si habitat cohérent (température, eau, végétation OK)
- **Épidémie biologique** (Phase 8 / Événements) : ralentit production si zone terraformée mal entretenue
- **Déboisement forcé** : enlève arbres rapidement (action terraformation) → perte tempo O₂ et biodiversité

### Fonction habitabilité continue
- Input : température, O₂, eau, ressources disponibles, présence animaux/arbres
- Output : score 0.0→1.0
- Effets :
  - < 0.3 : invivable, population refuse migration
  - 0.3→0.7 : viable mais avec malus (baisse salaires, moins travail, médecine à l'importation)
  - > 0.7 : acceptable, pop stable et mobile

---

## Questions à clarifier

### Q1 — Données biodiversité
- [ ] Où sont les champs `vegetationDensity` et `wildlifeDensity` dans `GoldbergTileState` ?
  - Valeurs [0.0, 1.0] ?
  - Impactées par terraformation et écologie passive ?
- [ ] Comment changent-elles chaque tick ?

### Q2 — Croissance passive d'arbres
- [ ] Conditions pour qu'arbres se créent naturellement (pas d'action humaine) :
  - Température > X°C ?
  - O₂ > X% ?
  - Humidité > X% ?
  - Quelqu'un doit les planter d'abord ou croissance vraiment autonome ?
- [ ] Taux de croissance : +0.01/tick ? +0.1/tick ?

### Q3 — Faune sauvage
- [ ] Conditions pour qu'animaux apparaissent :
  - Arbres/végétation > X% ?
  - Herbivores consomment-ils la végétation (réduction densité) ?
  - Prédateurs consomment-ils herbivores ?
  - Chaîne trophique implémentée ou simplifié ?
- [ ] Effets positifs faune : conversion O₂/CO₂ meilleure ? Contrôle prairies ?

### Q4 — Chaîne causale déforestation
- [ ] Exemple concret du design :
  - Tuile avec 100% forêt, 20 animaux/km², O₂ production stable
  - Action humaine : enlever 50% forêt → perte 70% animaux
  - Effect : moins d'animaux → moins O₂ production → baisse O₂ atmo
  - Timeline : immédiat ou sur plusieurs ticks ?
- [ ] Où est ce code ? `logic/ecology.py` ? Existe-t-il ?

### Q5 — Fonction habitabilité détail
- [ ] Formule actuelle de `habitabilityScore` dans `compute_atmospheric_state()` :
  - Prend en compte faune/flore ou seulement O₂/CO₂/temp/eau ?
  - Y a-t-il malus si faune=0 (planète morte) ?
- [ ] Comment évolue le score si je plante 10 arbres ? Immédiat +0.1 ou graduel ?

### Q6 — Régression écologie
- [ ] Peut-on "tuer" une tuile écologiquement ? (habitabilityScore → 0.0)
  - Pollution max ? Température extrême ? Pas d'eau ?
  - Peut-on la "ressusciter" ou c'est permanent ?
- [ ] Épidémie (événement) : comment affecte-t-elle la tuile exactement ?

### Q7 — Interaction population-écologie
- [ ] Population peut migrer si habitabilityScore < 0.3 — où c'est implémenté ?
- [ ] Population consomme-t-elle l'environnement (bois pour chauffage, eau potable) ou c'est abstrait ?

---

## Réponses

### Q1 + Q2 + Q3 — Modèle biodiversité par espèce

✅ **DÉCISION** : `vegetationDensity` et `wildlifeDensity` ne sont **pas des scalaires** — ce sont des **collections par espèce**.

**Structure :**
```
vegetationDensity: dict[str, float]   # ex: {"grass": 0.6, "forest": 0.3, "algae": 0.1}
wildlifeDensity: dict[str, float]     # ex: {"herbivore": 0.4, "predator": 0.1}
# Pour l'océan :
microbialDensity: dict[str, float]    # ex: {"plankton": 0.5, "cyanobacteria": 0.8}
```

Chaque espèce a ses propres **seuils de conditions** (min/max par paramètre environnemental).

**Modèle de croissance/décroissance :**
- Chaque tick, pour chaque espèce : on vérifie si les conditions locales sont dans la plage acceptable
- Plus les conditions sont **proches de l'optimum** → plus la croissance est rapide
- Si les conditions sont **hors seuil** (trop froid, trop peu d'O₂, etc.) → décroissance
- Croissance = logistique bornée [0.0, 1.0]

**Exemple — Cyanobactérie (terraformation océanique) :**
```
cyanobacteria:
  conditions:
    temperature: [5°C, 40°C]      # min survivable, max survivable
    o2_percent: [0%, 30%]         # tolère peu d'O₂ (pionnier)
    water: required               # tuile océan/côte obligatoire
  growth_rate: +0.02/tick si conditions OK
  o2_production: +0.001% atmo/tick par unité de densité
  decay_rate: -0.05/tick si température hors seuil
```

**Exemple — Forêt (terraformation terrestre) :**
```
forest:
  conditions:
    temperature: [0°C, 35°C]
    o2_percent: [15%, 40%]
    water: [0.3, 1.0]             # humidité minimale
  growth_rate: +0.005/tick si conditions OK
  o2_production: +0.002% atmo/tick par unité de densité
  decay_rate: -0.02/tick si sécheresse ou température extrême
```

---

### Q4 — Chaîne causale (simplifiée, pas de Lotka-Volterra)

✅ **DÉCISION** : Pas de prédation explicite entre espèces pour le MVP. Chaque espèce réagit **directement aux conditions abiotiques** (temp, O₂, eau, CO₂). Les espèces se renforcent indirectement via leurs effets sur l'environnement (ex: forêt produit O₂ → permet l'apparition d'herbivores).

**Exemple chaîne causale déforestation :**
1. Action humaine : `forest` density 0.8 → 0.3 (coupe)
2. Tick suivant : O₂ production de la tuile chute (moins de forêt)
3. Sur N ticks : O₂ atmosphérique local baisse si pas compensé ailleurs
4. Si O₂ passe sous seuil min des herbivores → `herbivore` density commence à décroître
5. Si habitabilityScore < 0.3 → pop refuse de migrer vers la tuile

Timeline : effets **graduels** sur plusieurs ticks, pas instantanés.

---

### Q6 — Peut-on "tuer" une tuile ?

✅ **DÉCISION** : Non — une tuile n'est jamais **irrémédiablement** morte.
- Le but du jeu étant la **terraformation**, toute tuile dégradée peut être récupérée si les conditions sont rétablies
- Le seul cas de `habitabilityScore ≈ 0` **permanent** est une planète dont les conditions de base sont définitivement hostiles (trop proche d'une étoile, volcanisme extrême, atmosphère irréparable) — c'est une contrainte **planétaire**, pas liée à l'action du joueur
- Les dégâts causés par les joueurs (pollution, déforestation) sont toujours réversibles via terraformation

---

### Q7 — Population & consommation de l'environnement → via le marché

✅ **DÉCISION** : La consommation de l'environnement est **abstraite via le marché**.

**Principe :** Une forêt (ou un banc de plancton, un troupeau d'animaux) = une **structure passive** qui met des ressources sur le marché local chaque tick, proportionnellement à sa densité.

**Exemples :**
- `forest` (density 0.6) → met X unités de `Wood` sur le marché local/tick (auto-renouvelable jusqu'à sa densité max)
- `wildlife_herbivore` (density 0.4) → met Y unités de `Meat`/`Hides` sur le marché local/tick
- `plankton` (density 0.8) → contribue à l'O₂ atmosphérique + met Z unités de `Biomass` sur le marché

**Auto-renouvellement :**
- La ressource se renouvelle si la densité de l'espèce est maintenue (conditions OK)
- Si la ressource est **surexploitée** (demande marché > production) → signal prix → incitation à replanter / réduire prélèvement
- La densité ne décroît pas directement à cause de la demande marché — c'est le signal prix qui régule (abstraction)

**Avantage :** Pas besoin de tracker la consommation écologique case par case — le marché fait le travail de régulation.
