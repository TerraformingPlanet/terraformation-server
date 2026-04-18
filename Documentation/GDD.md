# Game Design Document — Terraformation & Colonisation Spatiale

## Vision

Un jeu de gestion/simulation multijoueur asynchrone en vue top-down 3D sur une grille hexagonale où des corporations s'affrontent et coopèrent pour terraformer une planète hostile, dominer une bourse commune et devenir la corporation numéro 1.

Inspiré de : **Victoria 3 / Hearts of Iron / Crusader Kings 3**

---

## Concept Central

La planète est un monde mort. Des corporations (joueurs et IA) débarquent, s'emparent de territoires hexagonaux, construisent des infrastructures et modifient progressivement l'environnement pour le rendre habitable — tout en cherchant à écraser économiquement leurs concurrents.

Le monde tourne **en temps réel sur un serveur dédié**, même quand les joueurs sont déconnectés. Chaque joueur se connecte quand il le peut, prend ses décisions, et revient plus tard voir l'évolution.

---

## Système de Vues (3 niveaux)

Le jeu propose trois niveaux de vue imbriqués. La navigation se fait par **clic** et **retour contextuel** dans une seule scène, sans écran de chargement.

### Vue 1 — Système Solaire (niveau macro)

- Caméra orbit perspective
- Chaque corps céleste = une sphère colorée avec son cercle d'orbite (LineRenderer)
- **Clic sur une planète** → ouverture de la Vue Planétaire projetée

### Vue 2 — Planète (niveau méso)

La vue planétaire propose deux sous-vues basculées par un toggle :

- **Sous-vue Globe** (défaut) — sphère Goldberg 3D en perspective orbit. Hover highlight + clic sur une tuile la mémorise comme focus de la prochaine sous-vue.
- **Sous-vue Plan Tangent** (toggle) — projette les tuiles visibles sur un plan tangent à la sphère, centré sur la dernière tuile cliquée. Seules les tuiles dans un cône ~±41° autour du focus sont affichées (aucune distorsion Mercator aux bords). La projection se re-centre dynamiquement si la caméra s'éloigne du focus de plus de 5°. Une animation sphère → plan (0.6 s) est jouée à l'entrée. Une minimap (Mercator en arrière-plan, couche `MinimapOnly` invisible à la caméra principale) reste disponible.
- **Clic sur une tuile** → ouverture de la Vue Locale sur la région correspondante (inchangé)
- **Escape** → retour Vue Système Solaire

### Vue 3 — Locale (niveau micro)

- Caméra orthographique top-down sur la grille hexagonale
- Le `MapRegion` chargé correspond à la zone cliquée sur la projection (latitude/longitude)
- Cette vue montre un **extrait détaillé** du même astre, pas une carte indépendante
- Pan (clic droit drag) + zoom dans les bornes de la région
- **Escape** → retour Vue Planétaire

### Navigation résumée

```
[Vue Solaire]  ──clic planète──►  [Vue Planétaire]  ──clic projection──►  [Vue Locale]
               ◄────Escape────    [Vue Planétaire]  ◄──────Escape────  [Vue Locale]
```

### Relation entre données et vues

- Les données d'un astre sont les **paramètres source** qui définissent son monde : atmosphère, géologie, rayon, seed, couches, paramètres de génération.
- La vue planétaire affiche une **projection estimée** de l'ensemble du globe à basse résolution.
- La vue locale affiche une **région détaillée** de ce même globe, reconstruite depuis la latitude et la longitude choisies.

---

## Gameplay

### Grille Hexagonale

- La planète est représentée par une grille d'hexagones (coordonnées axiales)
- Chaque hexagone a un **type de terrain** et des **propriétés environnementales**
- Les joueurs cliquent sur les hexagones pour interagir
- Le relief local influence la circulation de l'eau, la formation des bassins, les côtes et les rivières

### Types de terrain

| Terrain | Description |
|---|---|
| Roche | Sol brut, peu de ressources |
| Glace | Source d'eau potentielle |
| Atmosphère toxique | Doit être neutralisée avant construction |
| Eau | Après dégel de la glace |
| Végétation | Terrain terraformé, O₂ produit |
| Métal | Riche en minerais |

### Propriétés par hexagone

Chaque hex possède des valeurs dynamiques :
- **Température** (°C)
- **Taux d'oxygène** (%)
- **Humidité / eau disponible**
- **Richesse minérale** (fer, rares)
- **Énergie ambiante** (solaire, géothermique)
- **Altitude locale** et rôle topographique (crête, pente, bassin, chenal)
- **Classe hydrologique** : océan ouvert, côte, eau intérieure, sec, gelé

### Relief & hydrologie

- Une case basse se remplit plus facilement qu'une case haute si de l'eau arrive depuis l'amont
- Une montagne ou une crête draine l'eau vers les hex voisins plus bas
- Une cuvette peut former un **lac** ou une **mer intérieure** si l'eau s'y accumule sans échappatoire immédiate
- Une zone basse connectée à une masse d'eau ouverte devient **côtière** puis **océanique** selon sa connectivité
- Aux pôles ou dans les régions froides, l'eau disponible peut devenir **eau gelée / glace dominante**
- La vue locale doit rester cohérente avec la vue projetée :
  - case projetée océanique → région locale majoritairement marine
  - case projetée aride → région locale très sèche
  - case projetée gelée → région locale dominée par la glace ou l'eau gelée

### État actuel de l'implémentation hydrologique

- Le relief local calcule déjà des classes topographiques lisibles : **crête, pente, bassin, chenal, source**
- L'eau locale est déjà classée en **océan ouvert, côte, eau intérieure, sec, gelé**
- Les rivières suivent un **champ d'écoulement pré-calculé** au lieu de recalculer une pente locale différente à chaque pas
- Le HUD local expose déjà les informations de debug utiles : classe hydrologique, classe de relief, accumulation de flux, voisin aval
- Le rendu local colore déjà légèrement les hex selon leur état hydrologique, sans remplacer le biome source

### Ce qui reste à pousser côté gameplay

- Le **débordement des bassins** n'est pas encore simulé : un bassin fermé retient aujourd'hui l'eau mais n'ouvre pas encore un exutoire crédible
- La distinction **côte vs océan** repose encore sur une heuristique locale simple, pas sur une connectivité globale robuste
- Les futures actions de terraformation devront pouvoir exploiter explicitement ces classes d'eau et de relief

### Classes d'eau ciblées

| Classe | Description gameplay |
|---|---|
| Océan ouvert | Masse d'eau dominante, connectée à grande échelle, pas d'occupation terrestre locale significative |
| Côte | Transition terre/eau, zone favorable aux infrastructures littorales futures |
| Eau intérieure | Lac ou mer intérieure formé dans un bassin ou un chenal fermé |
| Sec | Zone sans eau significative, typique des reliefs drainants ou régions arides |
| Gelé | Eau ou surface dominée par le gel, typique des pôles et hauts reliefs froids |

### Actions de Terraformation

- Chauffer l'atmosphère
- Irriguer (convertir glace → eau)
- Planter (végétaliser, produire O₂)
- Miner
- Neutraliser toxines

Chaque action a un **coût en crédits/ressources** et un **temps de progression** (ticks).

### Impact du relief sur le gameplay futur

- Les lacs et mers intérieures deviennent des points d'intérêt économiques et logistiques
- Les côtes créent des régions mixtes plus riches mais plus complexes à aménager
- Les chaînes montagneuses créent des barrières naturelles et modifient les trajectoires de ruissellement
- Les régions très basses et humides peuvent devenir plus favorables à l'irrigation et à la végétation
- Les régions hautes, sèches ou gelées demandent davantage d'investissement de terraformation

---

## Corporations

### Structure d'une Corporation

- **Nom & logo** (couleur distinctive)
- **Solde en crédits**
- **Hexagones possédés** (territoire)
- **Bâtiments construits**
- **Score global** (crédits + territoire + influence)

### Types de Corporations

- **Joueurs humains** — connectés de façon asynchrone
- **Corpos IA (NPC)** — remplissent le monde et concurrencent les joueurs
  - Stratégie expansionniste
  - Stratégie économiste
  - Stratégie militariste / sabotage

### Bâtiments

| Bâtiment | Fonction |
|---|---|
| Mine | Extraction de minerais par tick |
| Serre | Production O₂ + nourriture |
| Raffinerie | Transformation ressources brutes → crédits |
| Centrale | Production d'énergie |
| Laboratoire | Génère des points de tech |
| Quartier Général | Augmente le score d'influence |

### Claim de territoire

- Un joueur peut **réclamer un hex libre** pour un coût en crédits
- Les hexagones d'une corpo ennemie ne peuvent pas être réclamés directement (sabotage ou rachat)

---

## Économie & Bourse Commune

### Ressources tradables

- Fer, O₂, Eau, Énergie, Tech, Nourriture

### Mécanique de marché

- **Prix dynamiques** : fluctuent selon l'offre et la demande globale (toutes corpos confondues)
- Chaque tick, le serveur recalcule les prix selon les volumes échangés
- Les corpos peuvent passer des **ordres d'achat/vente** (order book simplifié)
- Les corpos IA participent aussi au marché et influencent les prix

### Objectif économique

Faire fructifier sa corpo, acheter bas, vendre haut, investir dans des infrastructures rentables.

---

## Événements Aléatoires

Des événements se déclenchent aléatoirement (tirage pondéré par tick serveur) :

| Événement | Effet |
|---|---|
| Rencontre du 3ème type | Découverte d'une structure alien → bonus ou malus selon choix |
| Tempête solaire | Dommages sur les bâtiments exposés |
| Découverte minière riche | Un hex révèle un gisement exceptionnel |
| Crise économique | Chute brutale du prix d'une ressource |
| Sabotage corpo | Une corpo IA (ou joueur) attaque une infrastructure |
| Épidémie biologique | Ralentit la production d'une zone terraformée |
| Contact diplomatique alien | Ouvre un arbre d'événements sur plusieurs tours |

---

## Multijoueur

- **Mode** : Asynchrone temps réel (monde persistant côté serveur)
- **Compétition + Coopération** : Les joueurs sont en compétition pour le classement mais partagent la même bourse et la même planète
- **Monde persistant** : tourne même quand tout le monde est déconnecté
- **Classement** : Score global = crédits + territoires + score d'influence

---

## Conditions de Victoire

- Short term : Être #1 au classement
- Long term : Atteindre un score de terraformation global (planète viable) en premier
- Coopératif : La planète devient habitable si toutes les corpos atteignent un seuil de terraformation combiné

---

## Inspirations

| Jeu | Ce qu'on emprunte |
|---|---|
| Victoria 3 | Économie dynamique, production en chaîne, marché mondial |
| Hearts of Iron IV | Tempo de jeu, progression en temps réel, événements |
| Crusader Kings 3 | Intrigues, événements narratifs, rivalités entre entités |
| Civilization VI | Grille hexagonale, types de terrain, amélioration de cases |
| Stellaris | Exploration spatiale, découvertes alien, colonisation |
