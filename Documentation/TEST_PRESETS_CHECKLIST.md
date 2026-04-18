# Checklist de Validation - Presets Terraformation

## Objet

Cette checklist definit ce que chaque preset de debug est cense verifier, et quels resultats doivent etre observes a minima.

Le but est de disposer d'une base stable pour le debug manuel, puis pour les futurs outils MCP et smoke tests.

## Regles communes

Pour chaque preset, verifier:

1. la vue attendue s'ouvre correctement
2. aucune erreur console bloquante n'apparait
3. le rendu visuel correspond au type de preset
4. les stats affichees par le debug panel et le HUD racontent la meme histoire
5. l'ouverture locale conserve la logique du preset autant que possible sans ecrasement absurde

Quand le bridge HTTP local est disponible, ajouter systematiquement:

6. `GET /debug/state` repond avant le lancement du preset
7. `GET /debug/projection` raconte la meme histoire que le rendu planete
8. `GET /debug/local` raconte la meme histoire que le HUD local
9. `GET /debug/console` ne contient pas d'erreur bloquante masquee

## Ocean

### Objectif

Verifier qu'un scenario oceanique produit une projection majoritairement marine et une region locale fortement humide ou ouverte.

### Projection attendue

- majorite nette de cellules `OpenOcean`
- peu de terrain rocheux visible
- temperature non figee en glace hors cas polaire

### Verification HTTP minimale

1. `GET /debug/launch-preset?preset=Ocean`
2. `GET /debug/projection`
3. `GET /debug/open-region?lat=0.50&lon=0.50`
4. `GET /debug/local`

### Local attendu

- eau moyenne elevee
- beaucoup de `OpenOcean`, `InlandWater` ou `Coast`
- peu de `Dry`
- peu ou pas de relief rocheux dominant

### Echec typique

- projection marron ou essentiellement rocheuse
- local majoritairement sec
- preset sans effet visible

## Arid

### Objectif

Verifier qu'un scenario aride limite fortement l'eau libre et les faux positifs hydrologiques.

### Projection attendue

- terrain surtout rocheux ou mineral
- peu ou pas de masses d'eau ouvertes
- eventuelle glace seulement sur zones froides extremes

### Verification HTTP minimale

1. `GET /debug/launch-preset?preset=Arid`
2. `GET /debug/projection`
3. `GET /debug/open-region?lat=0.52&lon=0.52`
4. `GET /debug/local`

### Local attendu

- eau moyenne faible
- tres peu de `OpenOcean` et `InlandWater`
- peu de rivieres
- `Dry` largement dominant

### Echec typique

- lacs trop frequents
- rivieres majeures en plein desert
- preset visuellement trop humide

## Frozen

### Objectif

Verifier qu'un scenario froid produit de l'eau gelee et des biomes froids coherents.

### Projection attendue

- zones froides bien visibles
- part significative de cellules type glace ou eau gelee

### Verification HTTP minimale

1. `GET /debug/launch-preset?preset=Frozen`
2. `GET /debug/projection`
3. `GET /debug/open-region?lat=0.20&lon=0.50`
4. `GET /debug/local`

### Local attendu

- temperature moyenne basse
- `FrozenWater` frequent
- vegetation tres limitee
- eau liquide reduite dans les zones les plus froides

### Echec typique

- trop d'eau liquide
- terrain rocheux sec partout sans gel
- preset proche d'un aride froid au lieu d'un gel coherent

## Coast

### Objectif

Verifier une vraie transition mer -> cote -> terre.

### Projection attendue

- bande ou zones de `OpenOcean`
- presence visible de cellules `Coast`
- terre distincte juste apres la zone littorale

### Verification HTTP minimale

1. `GET /debug/launch-preset?preset=Coast`
2. `GET /debug/projection`
3. `GET /debug/open-region?lat=0.47&lon=0.18`
4. `GET /debug/local`

### Local attendu

- melange lisible entre eau, cote et terre proche
- eau moyenne intermediaire
- plus de `Coast` que dans Ocean ou Basin
- vegetation ou roche proche du rivage selon temperature et humidite

### Echec typique

- aucune difference avec Ocean
- aucune cellule `Coast`
- projection integralement marron ou integralement bleue

## Basin

### Objectif

Verifier une cuvette ou eau interieure, accumulation et exutoire potentiel sont plausibles.

### Projection attendue

- noyau d'eau interieure visible
- couronne de transition vers la terre
- pas de lecture ocean ouvert uniforme

### Verification HTTP minimale

1. `GET /debug/launch-preset?preset=Basin`
2. `GET /debug/projection`
3. `GET /debug/open-region?lat=0.57&lon=0.58`
4. `GET /debug/local`

### Local attendu

- presence de `InlandWater`
- bassins identifies dans les stats
- eventuels exutoires ou chenaux autour de la cuvette
- eau moyenne intermediaire a forte selon le noyau

### Echec typique

- rendu equivalent a `None`
- rendu equivalent a `Ocean`
- aucun bassin ou aucune eau interieure dans les stats locales

## ProjectionOnly

### Objectif

Verifier uniquement la projection et la navigation planete sans ouverture locale immediate.

### Projection attendue

- vue planete stable
- regeneration projection et water level fonctionnels
- clic sur la projection possible ensuite vers une region locale

### Verification HTTP minimale

1. `GET /debug/state`
2. lancer le preset dedie si disponible
3. `GET /debug/projection`
4. `GET /debug/state`

### Echec typique

- projection ne se recharge pas
- le preset n'influence rien
- le state courant est perdu lors du reload

## Flows de validation minimum

### Flow A - Sanity check preset

1. ouvrir le preset
2. verifier le rendu projection
3. lire le resume projection si disponible
4. ouvrir une region locale representative
5. lire le resume local
6. noter succes ou echec

### Flow B - Regression de navigation

1. lancer preset
2. passer de Planet a Local
3. revenir avec `ESC`
4. verifier que le preset visuel et le water level n'ont pas disparu sans raison

### Flow C - Verification debug panel

1. lancer preset
2. ouvrir le debug panel
3. lire les stats de region
4. selectionner une cellule representative
5. comparer panneau debug et HUD

## Mesures a relever idealement

Quand l'outillage sera complet, relever au minimum:

- nombre de cellules `OpenOcean`
- nombre de cellules `Coast`
- nombre de cellules `InlandWater`
- nombre de cellules `FrozenWater`
- nombre de cellules `Dry`
- nombre de bassins
- nombre de chenaux
- nombre de rivieres
- eau moyenne
- temperature moyenne
- flux max

## Utilisation future

Cette checklist servira de base a:

- la validation manuelle
- les rapports de debug AI
- les futurs outils MCP `LaunchPreset`, `GetProjectionSummary`, `GetLocalSummary`, `RunSmokeTest`

---

## Sprint A — Critères spécifiques de validation

Critères à vérifier manuellement après les fixes du Sprint A (debug hydrologie, faux positifs Coast, déversement bassin).

### SA-1 : Coast — Pas de faux positifs en zone polaire

**Preset recommandé** : Frozen  
**Région cible** : `lat=0.10&lon=0.50` (pôle froid)

**Critères à respecter** :
- Aucune cellule `Coast` dans une zone entièrement `FrozenWater`
- Les cellules `FrozenWater` adjacentes à d'autres cellules `FrozenWater` ne déclenchent pas de `Coast`
- Un hex de type `Basin` ne doit jamais apparaître comme `Coast`, même s'il borde un `OpenOcean`
- Le nombre de cellules `Coast` dans `/debug/local` doit être 0 si la région est entièrement gelée

**Vérification console** :
```
GET /debug/launch-preset?preset=Frozen
GET /debug/open-region?lat=0.10&lon=0.50
GET /debug/local
```
→ champ `coastCells` doit être 0 ou très faible

**Échec typique** :
- `coastCells > 0` dans une région polaire sans `OpenOcean` visible
- Des `Basin` identifiés comme `Coast` dans les stats

---

### SA-2 : Coast — Présence correcte en zone littorale réelle

**Preset recommandé** : Coast  
**Région cible** : `lat=0.47&lon=0.18`

**Critères à respecter** :
- `coastCells > 0` dans les stats locales
- Les cellules `Coast` bordent toutes au moins un `OpenOcean`
- Les cellules `Coast` bordent toutes au moins un hex `Dry` ou non-aquatique
- Aucun `Basin` n'apparaît en `Coast`

**Vérification console** :
```
GET /debug/launch-preset?preset=Coast
GET /debug/open-region?lat=0.47&lon=0.18
GET /debug/local
```
→ `coastCells > 0` et cohérent avec `openOceanCells`

---

### SA-3 : Basin — Déversement et chaînage d'exutoire

**Preset recommandé** : Basin  
**Région cible** : `lat=0.57&lon=0.58`

**Critères à respecter** :
- Au moins un `Basin` présent dans les stats (`basinCells > 0`)
- Au moins une cellule avec exutoire (`overflowCells > 0`) si la région est correctement hydratée
- En mode debug panel : ajuster le slider eau d'une cellule `Basin` à +0.8, puis "Apply" → la cellule voisine aval doit augmenter en eau (visible via un second clic sur la cellule aval)
- Le `InlandWater` ne doit pas déborder en `OpenOcean` si le bassin reste fermé topographiquement

**Vérification console** :
```
GET /debug/launch-preset?preset=Basin
GET /debug/open-region?lat=0.57&lon=0.58
GET /debug/local
```
→ `basinCells > 0`, `overflowCells > 0`, `inlandWaterCells > 0`

**Échec typique** :
- `overflowCells == 0` alors que les bassins ont de l'eau
- Un bassin très chargé ne déverse pas vers son voisin même après Application directe

---

### SA-4 : DebugHydrologyPanel — Interaction complète

**Preset** : N'importe lequel avec vue locale

**Critères à respecter** :
1. Ouvrir le panel (`F10`) → status label se met à jour avec les stats actuelles
2. Sélectionner une cellule en cliquant dessus → `RefreshPanel` met à jour le label sélection
3. Ajuster les sliders Eau et Température → les labels `Eau Δ` et `Temp Δ` se mettent à jour en temps réel
4. Cliquer "Apply" → le mesh change de couleur immédiatement (pas besoin de régénérer)
5. Cliquer "Régénérer Local" → la grille entière se recalcule et les stats se mettent à jour
6. En vue Planète : le slider "Niveau d'eau" déclenche un rechargement de la projection en temps réel
7. En vue Planète : entrer lat/lon valides et cliquer "Ouvrir Région" → transition vers la vue locale

**Échec typique** :
- Les boutons ne répondent pas (problème de raycast)
- Le status label reste sur "Vue=SolarSystem" même après avoir ouvert une région
- Appuyer "Apply" sans cellule sélectionnée → message d'erreur explicite visible dans le status label

---

### SA-5 : Cohérence générale — Pas de régression sur les autres presets

Après les fixes, relancer chaque preset existant et vérifier que les stats locales restent dans les plages attendues.

| Preset | `openOceanCells` | `coastCells` | `inlandWaterCells` | `dryCells` | `frozenWaterCells` |
|--------|-----------------|-------------|-------------------|-----------|-------------------|
| Ocean  | dominant        | présents    | faibles           | minoritaires | 0 sauf pôles |
| Arid   | 0 ou infimes    | 0 ou infimes | 0 ou infimes     | dominant  | 0 sauf froid |
| Frozen | variables       | faibles     | faibles           | faibles   | dominant     |
| Coast  | présents        | max relatif | faibles           | présents  | 0 sauf froid |
| Basin  | faibles         | faibles     | max relatif       | présents  | 0 sauf froid |