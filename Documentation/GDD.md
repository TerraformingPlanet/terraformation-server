# Game Design Document — Terraformation & Colonisation Spatiale

> Document de référence unique pour le design du jeu.
> Notes de travail détaillées par thème : `Documentation/description_jeu/questions/`

---

## 1. Vision & Concept Central

Jeu de **simulation / exploration / colonisation spatiale en temps discret (tick-based)**, multijoueur asynchrone.

Le joueur incarne une **corporation** dont l'objectif est :
- d'étendre son influence territoriale
- de contrôler des tuiles pour accéder aux marchés
- de générer du profit via production, commerce et contrats
- de terraformer des mondes hostiles pour les rendre habitables

La planète est un monde mort. Des corporations (joueurs et IA) débarquent, s'emparent de territoires hexagonaux, construisent des infrastructures et modifient progressivement l'environnement — tout en cherchant à écraser économiquement leurs concurrents.

Le monde tourne **en temps réel sur un serveur dédié**, même quand les joueurs sont déconnectés. Chaque joueur se connecte quand il le peut, prend ses décisions, et revient plus tard voir l'évolution.

## 2. Inspirations

| Jeu | Ce qu'on emprunte |
|---|---|
| Victoria 3 | Économie dynamique, production en chaîne, mobilité sociale, marché mondial |
| Per Aspera | Planète + tuiles + simulation de terraformation |
| Hearts of Iron IV | Tempo de jeu, progression en temps réel, événements |
| Crusader Kings 3 | Intrigues, événements narratifs, rivalités entre entités |
| Civilization VI | Grille hexagonale, types de terrain, amélioration de cases |
| Stellaris | Exploration spatiale, découvertes alien, colonisation |

---

---

## 3. Structure de l'univers

```
Galaxie
 └── Systèmes stellaires
      └── Corps célestes (planètes, lunes…)
           └── Tuiles (grille H3 — hexagones géospatiaux)
```

- Chaque tuile est l'unité de base exploitable
- Une tuile appartient à un **État**, une **corporation**, ou à personne (espace non colonisé)
- Les planètes sont représentées avec une grille **H3** (hexagones géospatiaux hiérarchiques)

---

## 4. Système de temps

- **1 tick = 1 jour** (valeur de référence, ajustable pour l'équilibrage)
- À chaque tick : production des bâtiments, consommation des ressources, mise à jour des marchés, évolution de la population et de l'écologie

### File de décisions (énergie d'action)
- Un joueur dispose d'un quota de **décisions par jour** (ex : 10), rechargé chaque tick
- Toutes les décisions ont le même coût — ajustable pour l'équilibrage
- Les décisions ont un **délai d'effet variable** selon leur nature :
  - Signer un contrat → quasi-immédiat
  - Construire un bâtiment → délai long (réunir ressources, passer le mot)
  - Terraformer → très long

---

## 5. Les trois moteurs du jeu

### 5.1 Moteur économique
- Gestion des marchés : offre/demande à chaque tick
- Les bâtiments et la population consomment des ressources
- Les prix se propagent entre tuiles connectées, atténués par la distance

### 5.2 Moteur écologique (= terraformation)
- La pollution est une **forme de terraformation négative**
- Chaque tuile a des **indicateurs environnementaux** : O₂, CO₂, azote, température
- Une fonction continue détermine si une espèce peut survivre ou subir des malus (pas de seuil binaire — malus croissants selon l'écart)
- La nature évolue passivement : arbres, animaux, biodiversité dynamique
- Exemple de chaîne : déforestation → perte d'animaux → moins de conversion CO₂→O₂ → dégradation atmosphérique

### 5.3 Moteur joueur
- La corporation décide, dépense des décisions, attend les effets
- Si les ressources manquent : passer un contrat, ou les transporter depuis un autre monde

---

## 6. Système de Vues Unity (3 niveaux)

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

## 7. Tuiles & Terrain

### Grille Hexagonale

- La planète est représentée par une grille d'hexagones H3 (coordonnées axiales)
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
- **Température** (°C), **O₂/CO₂/azote** (%), **Humidité / eau disponible**
- **Richesse minérale** (fer, rares), **Énergie ambiante** (solaire, géothermique)
- **Altitude locale** et rôle topographique (crête, pente, bassin, chenal)
- **Classe hydrologique** : océan ouvert, côte, eau intérieure, sec, gelé

---

## 8. Relief & Hydrologie

- Une case basse se remplit plus facilement qu'une case haute si de l'eau arrive depuis l'amont
- Une cuvette peut former un **lac** ou une **mer intérieure** si l'eau s'y accumule sans échappatoire
- Une zone basse connectée à une masse d'eau ouverte devient **côtière** puis **océanique**
- Aux pôles ou dans les régions froides, l'eau disponible peut devenir **eau gelée / glace dominante**
- La vue locale doit rester cohérente avec la vue projetée (océanique → marine, aride → sèche, gelée → glace)

### Classes d'eau

| Classe | Description gameplay |
|---|---|
| Océan ouvert | Masse d'eau dominante, connectée à grande échelle |
| Côte | Transition terre/eau, zone favorable aux infrastructures littorales |
| Eau intérieure | Lac ou mer intérieure formé dans un bassin fermé |
| Sec | Zone sans eau significative, typique des reliefs drainants |
| Gelé | Surface dominée par le gel, typique des pôles et hauts reliefs froids |

### État actuel de l'implémentation
- Classes topographiques calculées : **crête, pente, bassin, chenal, source**
- Eau locale classée en **océan ouvert, côte, eau intérieure, sec, gelé**
- Rivières suivant un **champ d'écoulement pré-calculé**
- HUD local exposant classe hydrologique, relief, accumulation de flux, voisin aval

---

## 9. Bâtiments

### Modèle général
```
Entrées (ressources + travailleurs + énergie)
        ↓
    Bâtiment
        ↓
Sorties (ressources + déchets + effets par tick)
```

| Bâtiment | Fonction |
|---|---|
| Mine | Extraction de minerais par tick |
| Ferme / Serre | Production O₂ + nourriture |
| Raffinerie | Transformation ressources brutes |
| Centrale | Production d'énergie |
| Laboratoire | Génère des points de tech, irradie la connaissance |
| Quartier Général | Augmente le score d'influence |
| Bureau administratif | Permet à l'État de proposer des contrats |
| Bâtiment de traitement | Neutralise les déchets accumulés |

### Travailleurs
- Population locale + salariés corpo (considérés comme habitants de la tuile)
- Ratio 0→100% : 100% = plein rendement, 0% = bâtiment abandonné
- Si la corpo retire ses salariés → l'État peut nationaliser

### Réseau énergétique
- Une centrale produit X énergie, distribuée aux tuiles adjacentes via segments de réseau limitrophes
- Chaque segment a une capacité maximale — plusieurs segments augmentent la charge
- L'énergie est disponible sur le marché local

### Déchets
- S'accumulent sur la tuile à chaque tick
- Sans bâtiment de traitement → impact écologique négatif (faune, flore)

### Technologies et évolution
- Une technologie peut **améliorer** une entrée (ex : pioche → dynamite = +rendement, +risque) ou la **remplacer** (pioche → foreuse = moins de travailleurs)
- Upgrade à appliquer **bâtiment par bâtiment** — crée des chaînes de production
- La connaissance **irradie passivement** avec le temps vers les autres entités

### Épuisement et reconversion
- Ressource épuisée → bâtiment inutile → **abandonner** (risque d'événements négatifs) ou **reconvertir** (construire par-dessus)

### Actions de Terraformation
- Chauffer l'atmosphère, irriguer (glace → eau), planter (O₂), miner, neutraliser toxines
- Chaque action a un **coût en ressources** et un **délai en ticks**

---

## 10. Corporations

### Structure d'une Corporation
- **Nom & logo** (couleur distinctive)
- **Solde en crédits**, hexagones possédés, bâtiments construits
- **Score global** (crédits + territoire + influence)
- **Réputation globale** (publique) + **relation bilatérale** par paire (Corp ↔ État, Corp ↔ Corp)

### Types de Corporations
- **Joueurs humains** — connectés de façon asynchrone
- **Corpos IA** — contrôlées par simulation, pilotables par agent LLM
  - Stratégie expansionniste, économiste, militariste / sabotage

### Claim de territoire
- Réclamer un hex libre en y construisant une infrastructure
- Créer un **État vassal** à partir de tuiles entièrement contrôlées (évolue selon les mêmes règles, peut gagner en autonomie)

---

## 11. États & Gouvernements

### Caractéristiques
- Possèdent des tuiles, bâtiments de production, population
- **Type** (capitaliste, nationaliste, mixte…) → influence le comportement et le seuil de tolérance
- **Taux de corruption** : passif (moins efficace) ou exploitable par les corporations
- **Bureaucratie** (stat RPG) : délai des décisions = base × (1 + % bureaucratie)
- Contrôlés par la simulation IA, pilotables par un **agent LLM** (décisions stratégiques + réactions événementielles)

### Seuil de tolérance & Nationalisation
- Chaque corpo présente a un score calculé (puissance, comportement, contrats)
- Dépassement du seuil → nationalisation progressive (délai = bureaucratie + corruption)
- Pendant le délai : la corpo peut corrompre, négocier, activer un contrat spécial

---

## 12. Marchés

### Hiérarchie
```
Tuile → Planète → Système stellaire → Marché global (inter-étatique, optionnel)
```

### Prix : offre et demande dynamique
- Propagation à chaque tick entre tuiles connectées, **atténuée par la distance**
  - Exemple : pénurie tuile A → -50% sur A, -30% sur B (1 saut), -10% sur C (2 sauts)

### Population et niveaux de richesse
- Distribuée en **catégories sociales** (pauvres → classes moyennes → riches) avec besoins différents
- La richesse **évolue** : un ouvrier mieux payé monte de catégorie après X ticks
- **Migrations** possibles vers des tuiles plus attractives en cas de déséquilibre

### Ressources tradables
- Fer, O₂, Eau, Énergie, Tech, Nourriture

### Routes commerciales
1. Lancer une **expédition d'exploration** entre deux tuiles
2. Chemin calculé avec modificateurs terrain (ex : montagne = +10 ticks)
3. Construire la route physique → les tuiles se voient sur le marché
- Routes spatiales : même principe, infrastructure spatioport (à préciser)

### Régulation
- **Marché national** : régulé par l'État via taxes/quotas, influençable par corruption
- **Marché global** : organisme inter-étatique optionnel (événement ou action volontaire), corruptible par les corporations

---

## 13. Contrats

### Qui peut proposer
- États (depuis un bâtiment dédié) et corporations — contrats État ↔ Corp et Corp ↔ Corp

### Types de diffusion
- **Public (enchères)** : plusieurs soumettent une offre, le proposeur choisit la meilleure
- **Privé (direct)** : validation bilatérale, pas de négociation des termes

### Types d'objectifs
- Production/livraison de ressources, contrôle territorial, présence militaire, exploration
- Bonus de surperformance défini à la signature

### Durée, rupture, récompenses
- Durée fixe ou open-ended (fourniture continue), rupture possible → pénalité financière + réputation
- Récompenses : argent, influence, technologies, bonus de marché

---

## 14. Contrôle et perte de tuiles

### Conditions de perte
1. **Rébellion** : besoins vitaux non satisfaits → baisse productivité → grève → rébellion
2. **Rupture de contrat** : l'État peut reprendre ses biens
3. **Seuil de tolérance dépassé** : nationalisation

### Corporation contre corporation
- Attaque possible (milices, pression économique, contrat d'exclusivité)
- Risque de dégradation de la relation avec l'État présent

### Conséquences
- Perte d'accès au marché local, perte des bâtiments, pénalité de réputation
- Zéro tuile dans un État = exclusion totale de son marché

---

## 15. Voyages interplanétaires

- Durée calculée à l'avance (distance + technologies + modificateurs terrain)
- Événements aléatoires possibles pendant le trajet (piraterie, panne, opportunité)
- Vaisseau appartient à un État ou une corporation — louable via contrat

---

## 16. Événements

Des événements se déclenchent par tirage pondéré à chaque tick serveur, ou sur condition :

| Événement | Effet |
|---|---|
| Rencontre alien | Découverte d'une structure → bonus ou malus selon choix |
| Tempête solaire | Dommages sur les bâtiments exposés |
| Découverte minière | Un hex révèle un gisement exceptionnel |
| Crise économique | Chute brutale du prix d'une ressource |
| Sabotage corpo | Une corpo attaque une infrastructure |
| Épidémie biologique | Ralentit la production d'une zone terraformée |
| Rébellion populaire | Besoins vitaux non satisfaits → perte de tuile |
| Migration | Déséquilibre de main-d'œuvre → déplacement de population |
| Convention inter-étatique | Formation d'un organisme de marché global |

---

## 17. IA & Agents LLM

### Rôle
- Un agent LLM peut contrôler un État ou une corporation via des **outils MCP**
- Outils : lire l'état du jeu, prendre des décisions, donner des objectifs

### Fréquence
- **Sur événement** (rébellion, contrat disponible, menace…) ou **toutes les N ticks**
- LLM hébergé localement → coût maîtrisé

### Mémoire par entité
- **Profil** : personnalité, valeurs, stratégie
- **Événementielle** : historique des décisions et contrats
- **Relationnelle** : état des relations avec les autres entités

---

## 18. Multijoueur

- **Mode** : Asynchrone temps réel (monde persistant côté serveur)
- **Compétition + Coopération** : même bourse et même planète partagées
- **Monde persistant** : tourne même quand tout le monde est déconnecté
- **Classement** : Score global = crédits + territoires + score d'influence

---

## 19. Conditions de Victoire

- **Court terme** : Être #1 au classement
- **Long terme** : Atteindre un score de terraformation global (planète viable) en premier
- **Coopératif** : La planète devient habitable si toutes les corpos atteignent un seuil combiné
- **Fin de partie potentielle** : Contrôler l'organisme inter-étatique corrompu

---

## 20. Points ouverts (à designer)

| Sujet | Question |
|---|---|
| Routes spatiales | Infrastructure spatioport à préciser |
| Espionnage | Mécanisme d'accès aux informations hors portée |
| Arbre de technologies | Structure, déblocage, diffusion |
| Multijoueur | Nombre de joueurs, synchronisation des ticks |
| Génération procédurale | Quoi est généré au démarrage (planètes, ressources, États initiaux…) |
| Militaire | Profondeur du système de combat / milices |
| États vassaux | Conditions d'autonomisation, rupture de vassalité |
