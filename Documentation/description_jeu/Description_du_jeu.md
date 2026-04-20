# Description du jeu — Terraformation & Colonisation Spatiale

> **Source de vérité unique pour le design du jeu.**
> C'est ici que les décisions de design sont posées, discutées et stockées.
> Les fichiers `questions/` sont des annexes thématiques détaillées qui complètent ce document.
> `GDD.md` est un miroir archivé — seul ce fichier fait foi.

---

## Sommaire

| § | Section | Annexe thématique |
|---|---------|-------------------|
| [§1](#1-vision--concept-central) | Vision & Concept Central | — |
| [§2](#2-inspirations) | Inspirations | — |
| [§3](#3-structure-de-lunivers) | Structure de l'univers | — |
| [§4](#4-système-de-temps) | Système de temps | [exemple_tour_de_jeu.md](questions/exemple_tour_de_jeu.md) |
| [§5](#5-les-trois-moteurs-du-jeu) | Les trois moteurs du jeu | — |
| [§6](#6-système-de-vues-unity-3-niveaux) | Système de Vues Unity | — |
| [§7](#7-tuiles--terrain) | Tuiles & Terrain | — |
| [§8](#8-relief--hydrologie) | Relief & Hydrologie | — |
| [§9](#9-bâtiments) | Bâtiments | [exemples_batiments.md](questions/exemples_batiments.md) |
| [§10](#10-ressources) | Ressources | [resourceType.md](questions/resourceType.md) |
| [§11](#11-corporations) | Corporations | — |
| [§12](#12-états--gouvernements) | États & Gouvernements | [perte_de_controle_tuile.md](questions/perte_de_controle_tuile.md) |
| [§13](#13-marchés) | Marchés | [marche_local.md](questions/marche_local.md) |
| [§14](#14-contrats) | Contrats | [contrats.md](questions/contrats.md) |
| [§15](#15-contrôle-et-perte-de-tuiles) | Contrôle et perte de tuiles | [perte_de_controle_tuile.md](questions/perte_de_controle_tuile.md) |
| [§16](#16-voyages-interplanétaires) | Voyages interplanétaires | — |
| [§17](#17-événements) | Événements | — |
| [§18](#18-ia--agents-llm) | IA & Agents LLM | [ia_modele_langage.md](questions/ia_modele_langage.md) |
| [§19](#19-multijoueur) | Multijoueur | — |
| [§20](#20-conditions-de-victoire) | Conditions de Victoire | — |
| [§21](#21-questions-ouvertes--points-à-designer) | Questions ouvertes | — |

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

---

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
  - Construire un bâtiment → délai long (déterminé par la capacité de construction de la tuile)
  - Terraformer → très long

### File de planification (decision queue)

Chaque entité active (corporation joueur, état, agent IA) dispose d'une **file ordonnée de décisions planifiées**.

- La file est **réordonnée librement** par le joueur (drag & drop dans le HUD) ou par l'agent LLM lors de son cycle
- Elle est **persistante** : elle survit à la déconnexion du joueur et aux redémarrages serveur
- À chaque tick, les décisions dont les **conditions d'entrée sont satisfaites** (ressources disponibles, prérequis remplis) se déclenchent dans l'ordre
- Une décision **bloquée** (ressources manquantes, prérequis non remplis) reste en tête de file sans consommer de quota — elle ne saute pas
- Les décisions **en cours d'exécution** (ex : chantier multi-ticks) occupent un slot actif jusqu'à leur résolution

**Structure d'une entrée de file :**

| Champ | Rôle |
|-------|------|
| `type` | Type d'action (`build`, `sign_contract`, `terraform`, `set_tolerance`, etc.) |
| `targetId` | Tuile ou entité cible |
| `params` | Paramètres spécifiques à l'action |
| `enqueuedTick` | Tick d'ajout à la file |
| `startTick` | Tick de début d'exécution (`null` si encore en attente) |
| `resolvesTick` | Tick estimé de résolution (calculé au `startTick`) |
| `status` | `pending` / `in_progress` / `done` / `blocked` / `suspended` |

**Intégration LLM :** l'agent LLM remplit la file lors de son cycle (toutes les N ticks ou sur événement).
Cela lui permet de **planifier une stratégie sur plusieurs ticks** sans être interrogé à chaque tick.
La mémoire `AgentMemory` peut stocker le plan courant pour contextualiser les décisions futures.

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
- **Sous-vue Plan Tangent** (toggle) — projette les tuiles visibles sur un plan tangent à la sphère, centré sur la dernière tuile cliquée. Seules les tuiles dans un cône ~±41° autour du focus sont affichées. La projection se re-centre dynamiquement si la caméra s'éloigne du focus de plus de 5°. Une animation sphère → plan (0.6 s) est jouée à l'entrée.
- **Clic sur une tuile** → ouverture de la Vue Locale sur la région correspondante
- **Escape** → retour Vue Système Solaire

### Vue 3 — Locale (niveau micro)
- Caméra orthographique top-down sur la grille hexagonale
- Le MapRegion chargé correspond à la zone cliquée sur la projection
- Pan (clic droit drag) + zoom dans les bornes de la région
- **Escape** → retour Vue Planétaire

### Navigation résumée

```
[Vue Solaire]  ──clic planète──►  [Vue Planétaire]  ──clic projection──►  [Vue Locale]
               ◄────Escape────    [Vue Planétaire]  ◄──────Escape────  [Vue Locale]
```

---

## 7. Tuiles & Terrain

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

### Classes d'eau

| Classe | Description gameplay |
|---|---|
| Océan ouvert | Masse d'eau dominante, connectée à grande échelle |
| Côte | Transition terre/eau, zone favorable aux infrastructures littorales |
| Eau intérieure | Lac ou mer intérieure formé dans un bassin fermé |
| Sec | Zone sans eau significative, typique des reliefs drainants |
| Gelé | Surface dominée par le gel, typique des pôles et hauts reliefs froids |

---

## 9. Bâtiments

### Modèle général
```
Entrées (ressources + travailleurs + énergie)
        ↓
    Bâtiment
        ↓
Sorties (ressources produites + déchets + effets par tick)
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
| **Entreprise de Bâtiment (EB)** | **Produit des points de construction par tick** |

### Construction et chantiers

Inspiré de Victoria 3 : chaque tuile possède **deux files de construction indépendantes** alimentées par la même capacité de construction (`constructionCapacity`), mais avec des logiques et des acteurs différents.

---

#### Capacité de construction (`constructionCapacity`)

Produite par le bâtiment **Entreprise de Bâtiment (EB)** — fonctionne comme une mine dont l'output est de la puissance de chantier :

```
Entrées : travailleurs + outils + matières premières
        ↓
    Entreprise de Bâtiment (EB)
        ↓
Output : +N points de construction / tick  (ex : +30 pts/tick)
```

La capacité totale de la tuile est la **somme** de toutes les EB actives. Plusieurs EB coexistent et cumulent leur output.

**EB de fortune (spawn automatique à la migration) :**
- Quand une population migre sur une tuile, elle crée spontanément une EB de fortune
- Entrées : villageois + outils basiques (pioche, hache…) — ressources propres des habitants
- Output : faible capacité (ex : +5 pts/tick) — représente "on se construit des abris"
- C'est un vrai bâtiment EB avec de vraies entrées, pas un bonus magique
- Peut être remplacée par une EB normale construite par l'entité propriétaire

Une tuile **sans population et sans EB** a `constructionCapacity = 0`.

---

#### File 1 — File de l'État / Corporation (`stateConstructionQueue`)

> Gérée par le **joueur ou l'agent LLM**, propriétaire de la tuile.

- Contient les chantiers **décidés explicitement** par l'entité propriétaire (via la file de planification)
- Bâtiments stratégiques : mines, centrales, laboratoires, EB améliorées, QG…
- Seul le propriétaire de la tuile peut y ajouter des entrées
- L'entrée passe en `in_progress` dès le premier tick de consommation de points
- Réordonnable librement (drag & drop HUD ou agent LLM)

---

#### File 2 — File de la Population (`popConstructionQueue`)

> Gérée **autonomement** par la population locale, sans intervention du joueur.

- La population analyse les **signaux du marché local** : ressource manquante, prix élevé, besoin non satisfait
- Elle décide elle-même de construire les bâtiments dont **elle a besoin** : maisons, petits ateliers, commerces…
- Utilise ses **propres ressources** (achetées sur le marché local ou stockées)
- Le joueur **ne contrôle pas** cette file — il peut l'observer mais pas la modifier directement
- La population peut construire une EB de fortune via cette file quand elle migre sur une nouvelle tuile

**Interaction entre les deux files :**
- Les deux files se **partagent** la `constructionCapacity` disponible de la tuile
- La répartition dépend de la **politique de l'État** propriétaire de la tuile :

| Orientation politique | Part État/Corp | Part Population | Effet |
|----------------------|---------------|-----------------|-------|
| Libérale | faible (ex : 20%) | forte (ex : 80%) | Le marché construit ce dont il a besoin, l'État dirige peu |
| Mixte (défaut) | 50% | 50% | Équilibre planification / initiative privée |
| Dirigiste / Nationaliste | forte (ex : 80%) | faible (ex : 20%) | L'État contrôle la construction, la population subit |

- La politique est un paramètre de l'entité État, modifiable via une décision (avec délai bureaucratique)
- Une corporation propriétaire d'une tuile sans État dessus applique une politique libérale par défaut

---

#### Mécanisme de débordement (commun aux deux files)

À chaque tick, pour chaque file :
1. Les points alloués sont consommés contre le premier chantier de la file
2. Si terminé (points accumulés ≥ coût) → `done`, le **surplus déborde sur le chantier suivant** dans la même tick
3. Ce mécanisme continue jusqu'à épuisement des points alloués

**Exemple (file État, EB 30 pts/tick, 60% alloués = 18 pts/tick) :**
- File : [EB normale (coût 90 pts), Mine (coût 60 pts)]
- Tick 1→5 : EB reçoit 18 pts/tick (90 pts → terminée au tick 5)
- Tick 5 : 0 pts résiduels → Mine commence au tick 6

---

#### Chantier interrompu (changement de propriétaire)

Si la tuile change de propriétaire pendant un chantier **de la file État** :
- Le chantier passe en état **`suspended`** — progression conservée, matériaux déjà consommés perdus
- Le nouveau propriétaire peut **reprendre** ou **abandonner** (remise à zéro)
- La progression partielle (`partialProgress`) est visible dans l'état de la tuile

Les chantiers **de la file Population** ne sont pas affectés par le changement de propriétaire — la population continue à construire pour elle-même.

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

> Détail complet : `questions/exemples_batiments.md`

---

## 10. Ressources

### Rôle d'une ressource

Une ressource peut jouer trois rôles dans l'économie du jeu :
- **Input** : consommée par un bâtiment ou une population pour fonctionner
- **Output** : produite par un bâtiment, un événement naturel ou un organisme vivant (ex : O₂ par les arbres)
- **Gathered** : collectée directement dans l'environnement sans transformation (ex : baies, minéraux de surface)

### Catégories

| Catégorie | Description | Exemples |
|---|---|---|
| **Périodique** | Molécules ou éléments du tableau périodique | Fer (Fe), Oxygène (O₂), Eau (H₂O), CO₂ |
| **Polymère** | Matériaux synthétiques — liste extensible selon les phases | Plastique, fibre composite |
| **Processed** | Produits transformés par un bâtiment | Tuyau, planche, composant électronique |
| **Gathered** | Collecté dans la nature, sans transformation industrielle | Baies, roches de surface, champignons |
| **Stocker** | Ressources dont la valeur est leur disponibilité immédiate | Énergie électrique, eau en réservoir |
| **Immatériel** | Ressources non physiques influençant l'économie et la progression | Points de science, réputation |

### Ressources tradables (marché)

Les ressources qui circulent sur les marchés locaux et planétaires :

| Ressource | Catégorie | Rôle principal | Bâtiment producteur |
|---|---|---|---|
| Minerals | Périodique | Output / Gathered | Mine |
| Food | Gathered / Processed | Output | Ferme / Serre |
| Energy | Stocker | Output | Centrale énergétique |
| ResearchPoints | Immatériel | Output | Laboratoire |
| Waste | Processed | Output (sous-produit) | Mine, Centrale |
| Iron | Périodique | Output | Mine (minerai de fer) |
| Oxygen | Périodique | Output | Serre, arbres (terraformation) |
| Water | Stocker / Périodique | Gathered / Output | Puits, électrolyseur |
| Tech | Immatériel | Output | Laboratoire avancé |

> Les catégories Polymère, Processed et Gathered seront enrichies progressivement selon les phases de développement.
> Détail des types de ressources : `questions/resourceType.md`

---

## 11. Corporations

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

## 12. États & Gouvernements

### Caractéristiques
- Possèdent des tuiles, bâtiments de production, population
- **Type** (capitaliste, nationaliste, mixte…) → influence le comportement et le seuil de tolérance
- **Taux de corruption** : passif (moins efficace) ou exploitable par les corporations
- **Bureaucratie** (stat RPG) : délai des décisions = base × (1 + % bureaucratie)
- Contrôlés par la simulation IA, pilotables par un **agent LLM**

### Seuil de tolérance & Nationalisation
- Chaque corpo présente a un score calculé (puissance, comportement, contrats)
- Dépassement du seuil → nationalisation progressive (délai = bureaucratie + corruption)
- Pendant le délai : la corpo peut corrompre, négocier, activer un contrat spécial

> Détail complet : `questions/perte_de_controle_tuile.md`

---

## 13. Marchés

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

### Régulation
- **Marché national** : régulé par l'État via taxes/quotas, influençable par corruption
- **Marché global** : organisme inter-étatique optionnel, corruptible par les corporations

> Détail complet : `questions/marche_local.md`

---

## 14. Contrats

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

> Détail complet : `questions/contrats.md`

---

## 15. Contrôle et perte de tuiles

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

> Détail complet : `questions/perte_de_controle_tuile.md`

---

## 16. Voyages interplanétaires

- Durée calculée à l'avance (distance + technologies + modificateurs terrain)
- Événements aléatoires possibles pendant le trajet (piraterie, panne, opportunité)
- Vaisseau appartient à un État ou une corporation — louable via contrat

---

## 17. Événements

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

## 18. IA & Agents LLM

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

> Détail complet : `questions/ia_modele_langage.md`

---

## 19. Multijoueur

- **Mode** : Asynchrone temps réel (monde persistant côté serveur)
- **Compétition + Coopération** : même bourse et même planète partagées
- **Monde persistant** : tourne même quand tout le monde est déconnecté
- **Classement** : Score global = crédits + territoires + score d'influence

---

## 20. Conditions de Victoire

- **Court terme** : Être #1 au classement
- **Long terme** : Atteindre un score de terraformation global (planète viable) en premier
- **Coopératif** : La planète devient habitable si toutes les corpos atteignent un seuil combiné
- **Fin de partie potentielle** : Contrôler l'organisme inter-étatique corrompu

---

## 21. Questions ouvertes & Points à designer

> C'est ici que les décisions non encore tranchées sont listées. Quand une décision est prise, elle est déplacée dans la section correspondante ci-dessus.

| Sujet | Question | Statut |
|---|---|---|
| Routes spatiales | Infrastructure spatioport à préciser | ❓ Ouvert |
| Espionnage | Mécanisme d'accès aux informations hors portée | ❓ Ouvert |
| Arbre de technologies | Structure, déblocage, diffusion | ❓ Ouvert |
| Multijoueur | Nombre de joueurs, synchronisation des ticks | ❓ Ouvert |
| Génération procédurale | Quoi est généré au démarrage (planètes, ressources, États initiaux…) | ❓ Ouvert |
| Militaire | Profondeur du système de combat / milices | ❓ Ouvert |
| États vassaux | Conditions d'autonomisation, rupture de vassalité | ❓ Ouvert |
| Quota de décisions | Valeur exacte, coût différencié par type d'action ? | ❓ Ouvert |
| Marché global | Formation uniquement par événement ou aussi par action joueur ? | ❓ Ouvert |
