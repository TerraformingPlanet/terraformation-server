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
| [§15.1](#151-contrôle-orbital--points-de-lagrange) | Contrôle orbital & Points de Lagrange | — |
| [§16](#16-voyages-interplanétaires) | Voyages interplanétaires | — |
| [§17](#17-événements) | Événements | — |
| [§18](#18-ia--agents-llm) | IA & Agents LLM | [ia_modele_langage.md](questions/ia_modele_langage.md) · [gameplay_llm.md](questions/gameplay_llm.md) |
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
           ├── Orbite (5 tuiles spéciales — Points de Lagrange L1-L5)
           └── Surface (grille H3 — hexagones géospatiaux)
```

- Chaque tuile de surface est l'unité de base exploitable
- Une tuile appartient à un **État**, une **corporation**, ou à personne (espace non colonisé)
- Les planètes sont représentées avec une grille **H3** (hexagones géospatiaux hiérarchiques)
- Chaque corps céleste a également **5 tuiles orbitales** (Points de Lagrange) contrôlables séparément

### Contrôle d'un corps céleste

Un corps céleste est considéré comme **contrôlé** par une entité si elle satisfait les deux conditions simultanément :
1. **Contrôle orbital** : détenir L1 **et** L2 (= 50% du contrôle orbital, seuil minimum)
2. **Contrôle de surface** : posséder 51% des tuiles H3 du corps

Si les deux conditions sont remplies par des entités différentes → **conflit ouvert** : aucune n'obtient le bonus de contrôle.

---

## 3.1 Contrôle orbital — Points de Lagrange

> Référence réelle : [Points de Lagrange (Wikipedia)](https://fr.wikipedia.org/wiki/Point_de_Lagrange)

Chaque corps céleste en orbite autour d'un astre génère **5 points d'équilibre gravitationnel** (Points de Lagrange). Chacun est une **tuile orbitale** qu'une corpo ou un État peut chercher à contrôler en y déployant une station.

Les Points de Lagrange jouent un double rôle :
1. **Waypoints d'exploration et de voyage** — les `ExpeditionUnit` de type `Orbital` transitent par les points de Lagrange pour rejoindre un corps cible
2. **Positions stratégiques** — les contrôler permet de taxer, bloquer ou faciliter le passage

### Table de contrôle orbital

| Points détenus | % contrôle orbital | Effet |
|---|---|---|
| L1 **ou** L2 | 50% | Seuil minimum — taxation de passage possible |
| L1 + L2 + (L4 **ou** L5) | 75% | Blocus + bonus diplomatique complet |
| L1 + L2 + L4 + L5 + L3 | 100% | Contrôle orbital total |

> L1 et L2 encadrent directement le corps céleste (côté étoile et côté opposé). L4/L5 sont stables à 60° — points d'ancrage de longue durée. L3 est le plus difficile à tenir (côté étoile opposé).

### Exploration et voyage spatial

- Toute `ExpeditionUnit` de type `Orbital` part d'un **Spaceport** et transite par les points de Lagrange du corps cible
- Si un point de Lagrange est **occupé par une station ennemie**, l'expédition peut être :
  - **Taxée** : perd une fraction de son `cargo` (péage)
  - **Bloquée** : retournée à l'origine si blocus actif (L1 + L2 détenus par le même ennemi)
- Un point de Lagrange allié est un **relais** : réduit le coût d'expédition vers le corps (bonus d'efficacité)

### Bâtiments orbitaux par type de point

| Point | Bâtiments possibles | Rôle |
|---|---|---|
| **L1** | Station + Ascenseur spatial | Accès direct à la surface, transit rapide cargo↔orbite |
| **L2** | Station + Observatoire | Blocus côté obscur, bonus exploration système |
| **L4 / L5** | Station de relais, dépôt de ressources | Position stable, ravitaillement expéditions |
| **L3** | Poste avancé | Surveillance, renseignement sur le système entier |

> **Ascenseur spatial (L1 uniquement)** : bâtiment avancé qui élimine le coût d'expédition surface→orbite pour les routes commerciales `Orbital` contrôlées par la même entité. Réduit drastiquement le coût de colonisation du corps.

### Taxation de passage

Un point de Lagrange avec une **station active** peut percevoir des taxes sur les `ExpeditionUnit` qui le traversent :
- Le propriétaire fixe un `passageTaxRate` (0% à 100%) par point
- Les entités avec un **contrat de libre passage** ou une **alliance** sont exemptées
- Recette versée à chaque tick en `Credits` dans les stocks de la corpo propriétaire
- Le taux est un levier de négociation diplomatique : baisser les taxes pour attirer des partenaires, les monter pour étouffer un concurrent

### Points de Lagrange comme tuiles

- Chaque point L1-L5 est une tuile spéciale : `tileType = LagrangePoint`
- Accessible uniquement via `ExpeditionUnit` de type `Orbital` (pas de caravane terrestre)
- Ne génère pas de ressources passives (pas de terrain, pas de population)
- Peut être prise par une expédition hostile si le propriétaire n'y maintient pas de défense
- Une tuile Lagrange sans station = point de passage libre, non taxé

---

## 4. Système de temps

- **1 tick = 1 jour** (valeur de référence, ajustable pour l'équilibrage)
- À chaque tick : production des bâtiments, consommation des ressources, mise à jour des marchés, évolution de la population et de l'écologie

### File de planification (decision queue)

Chaque action passe par une **file persistante par territoire** — il n'y a pas de quota de décisions par jour.

#### File par territoire (pas globale)

La file n'est **pas globale par entité** — elle est **par gouvernement/territoire**.

- Un groupe de tuiles **limitrophes** appartenant à la même entité partage **une seule file** avec le **cumul de leurs `constructionCapacity`**
- Si un territoire se fragmente (perte d'une tuile de connexion) → **deux files distinctes** avec chacune sa propre capacité
- Incitation à l'expansion **contiguë** : un empire compact construit plus vite qu'un empire fragmenté

**Structure d'une entrée de file :**

| Champ | Rôle |
|-------|------|
| `type` | Type d'action (`build`, `claim`, `sign_contract`, `terraform`, etc.) |
| `targetId` | Tuile ou entité cible |
| `params` | Paramètres spécifiques à l'action |
| `enqueuedTick` | Tick d'ajout à la file |
| `startTick` | Tick de début d'exécution (`null` si encore en attente) |
| `resolvesTick` | Tick estimé de résolution |
| `status` | `pending` / `in_progress` / `done` / `blocked` / `suspended` |

La file est **persistante en PostgreSQL** — survit aux restarts serveur et aux déconnexions.

#### Claim par caravane

`claim` n'est pas immédiat — il nécessite l'envoi d'une **unité de colonisation** :
- Tuile sans gouvernement (peut avoir une population existante) → colonisable
- La caravane transporte une **population de base** et met du temps à arriver (distance + infrastructure)
- À l'arrivée : si la tuile est libre → colonisation réussie ; si occupée → conquête requise
- L'entrée reste `in_progress` dans la file pendant le trajet

#### Délais par type d'action

| Action | Délai |
|--------|-------|
| Signer un contrat | quasi-immédiat |
| Construire un bâtiment | `ceil(coût / constructionCapacity)` ticks |
| Claim (caravane) | distance / vitesse de l'unité |
| Terraformer | très long (plusieurs ticks) |

**Intégration LLM :** l'agent LLM remplit la file lors de son cycle (toutes les N ticks ou sur événement), permettant de **planifier une stratégie sur plusieurs ticks**. Pour les bots Corpo IA, la FSM gère les décisions routinières et le LLM intervient sur les décisions stratégiques (réordonner la file, déclarer la guerre, modifier les seuils).

---

## 5. Les trois moteurs du jeu

### 5.1 Moteur économique
- Gestion des marchés : offre/demande à chaque tick
- Les bâtiments et la population consomment des ressources
- Les prix se propagent entre tuiles connectées, atténués par la distance

### 5.2 Moteur écologique (= terraformation)
- La pollution est une **forme de terraformation négative**
- Chaque tuile a des **indicateurs environnementaux** : O₂, CO₂, azote, température, humidité
- Une fonction continue détermine si une espèce peut survivre — **pas de seuil binaire** mais des malus croissants selon l'écart aux conditions optimales

#### Biodiversité par espèce

`vegetationDensity`, `wildlifeDensity` et `microbialDensity` sont des **collections par espèce** (pas des scalaires) :

```
vegetationDensity:  dict[str, float]  # ex: {"grass": 0.6, "forest": 0.3}
wildlifeDensity:    dict[str, float]  # ex: {"herbivore": 0.4, "predator": 0.1}
microbialDensity:   dict[str, float]  # ex: {"plankton": 0.5, "cyanobacteria": 0.8}
```

Chaque espèce a ses **seuils de conditions** (min/max par paramètre) et un taux de croissance logistique :
- Conditions dans la plage optimale → croissance passive chaque tick
- Conditions hors seuil → décroissance

**Succession écologique émergente :** les cyanobactéries tolèrent peu d'O₂ → elles le produisent → les forêts deviennent possibles → les herbivores apparaissent. L'ordre de terraformation n'est pas scripté, il émerge naturellement.

#### Biodiversité → marché

Chaque espèce est une **structure passive de marché** : elle met des ressources sur le marché local chaque tick proportionnellement à sa densité.
- `forest` (0.6) → X unités de `Wood` / tick sur le marché local
- `wildlife_herbivore` (0.4) → Y unités de `Meat` / tick
- `plankton` (0.8) → contribue à l'O₂ atmosphérique + Z unités de `Biomass`

La ressource se renouvelle si la densité est maintenue. Si la demande dépasse la production → signal prix → incitation à replanter / réduire le prélèvement.

#### Habitabilité

`habitabilityScore` (0.0→1.0) intègre les conditions abiotiques **et** la biodiversité :
- Planète vierge (densités = 0) → malus même si O₂/temp sont OK
- Biodiversité diversifiée → bonus
- < 0.3 : invivable, population refuse de migrer
- 0.3→0.7 : viable avec malus (baisse salaires, médecine à l'importation)
- > 0.7 : acceptable, population stable et mobile

Une tuile dégradée est toujours **récupérable** par terraformation — le jeu est centré sur la réparation, pas la destruction permanente.

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

### Emploi par bâtiment

Chaque bâtiment requiert un quota de population d'une **classe sociale spécifique** (`employmentSlots`) :
- `workerRatio = min(1.0, popDisponible / quotaRequis)`
- Si `workerRatio < 1.0` → **carence** → production réduite proportionnellement
- Carence persistante → signal d'attractivité élevé → amplifie le flux migratoire entrant

| Bâtiment | Classe requise | Quota (exemple) |
|---|---|---|
| Mine niv.1 | Poor | 50 |
| Farm | Poor | 30 |
| EnergyPlant | Poor + Middle | 20 + 5 |
| Research | Middle + Rich | 20 + 5 |

### Construction et chantiers

#### Capacité de construction (`constructionCapacity`)

Produite par le bâtiment **Entreprise de Bâtiment (EB)** :

```
Entrées : travailleurs + outils + matières premières
        ↓
    Entreprise de Bâtiment (EB)
        ↓
Output : +N points de construction / tick  (ex : +30 pts/tick)
```

La capacité totale d'un territoire = **somme des EB de toutes les tuiles contiguës** (voir §4 — file par territoire).

**EB de fortune :**
- Apparaît **automatiquement** sur une tuile peuplée sans EB formelle
- Conditions : `population > 0` ET `Wood` disponible sur le marché local ET aucune EB existante
- Entrées : `Wood` (rondin) + outils basiques
- Output : +5 pts/tick (vs +30 pour une EB normale)
- Représente les abris et chantiers artisanaux de la population
- Disparaît quand une EB normale est construite ou quand la population quitte la tuile

#### File de construction (file unique par territoire)

- **Une seule file** par territoire contigu (pas de file Population séparée)
- La population contribue via la **demande marché** (pas via une file autonome) :
  - Population croissante → plus de demande de `Food`, `Wood`, `Energy`
  - Signal prix → incite l'entité propriétaire à construire les bâtiments manquants
- Réordonnable librement (joueur, drag & drop HUD, ou agent LLM)

#### Mécanisme de débordement

À chaque tick :
1. Les points sont consommés contre le premier chantier de la file
2. Si terminé → `done`, le **surplus déborde sur le chantier suivant** dans le même tick
3. Continue jusqu'à épuisement des points du tick

**Exemple (territoire, capacité = 30 pts/tick) :**
- File : [EB normale (coût 90 pts), Mine (coût 60 pts)]
- Ticks 1→3 : EB reçoit 30 pts/tick → terminée au tick 3
- Tick 3 : 0 pts résiduels → Mine commence au tick 4

#### Chantier interrompu (changement de propriétaire)

- Construction `in_progress` sur une tuile perdue → **perdue** (pas de remboursement)
- Constructions `pending` dans la file → conservées pour le territoire résiduel

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
- **Corpos IA** — architecture hybride FSM + LLM (voir ci-dessous)
  - Profils : Expansionniste, Économiste, Militariste / Saboteur

### Corporations IA — Architecture FSM + LLM

Les bots Corpo utilisent deux couches complémentaires :

**Couche 1 — FSM déterministe (tick-by-tick)**
Gère les décisions routinières selon des règles codées par profil :
- Expansionniste : `si tuile adjacente libre ET credits > seuil → enqueue claim`
- Économiste : `si prix ressource > boom → augmenter production`
- Militariste : `si corpo ennemie adjacente ET force_ratio > 1.2 → enqueue attaque`

États FSM : `Idle`, `Expanding`, `Building`, `Trading`, `Raiding`

**Couche 2 — Agent LLM (décisions stratégiques)**
Déclenché sur événements clés (pas chaque tick) :
- Réordonner la **file de construction**
- Déclarer la **guerre** ou signer la **paix**
- Proposer / accepter / refuser un **contrat**
- Modifier les **seuils de tolérance** de la FSM

> Le LLM gouverne la FSM, il ne la remplace pas. La FSM exécute dans les limites fixées par le LLM.

Les bots utilisent les **mêmes endpoints API** que les joueurs humains. Profil fixe à la création, seuils FSM ajustables par le LLM. La création d'une corpo IA est réservée à l'admin ou au GM (`is_ai=True`).

### Claim de territoire
- Envoyer une **caravane de colonisation** vers une tuile sans gouvernement
- La caravane transporte une population de base — elle prend du temps à arriver
- Tuile occupée → conquête requise
- Créer un **État vassal** à partir de tuiles entièrement contrôlées

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

### Population et demande marché

La population génère une **demande minimale** proportionnelle à sa taille et sa classe sociale :

| Classe | Consomme |
|---|---|
| Poor | `Food` + `Energy` basique |
| Middle | `Food` + `Energy` + `Tech` |
| Rich | `Food` + `Energy` + `Tech` + produits de luxe |

Chaque classe a un **revenu moyen** (`avgIncome`) qui varie selon l'emploi disponible sur la tuile :
- `workerRatio` élevé → `avgIncome` monte → consommation augmente
- 50% chômage → `avgIncome` faible → faible demande de marché
- Corp construit une usine, emploie 500 Poor → `avgIncome` ×4 → la tuile consomme 4× plus de `Food`

**Mobilité sociale** : `Poor → Middle → Rich` selon `avgIncome` sur plusieurs ticks (seuils à calibrer).

### Écologie et marché

Les espèces naturelles sont des **structures passives de marché** :
- `forest` → produit `Wood` / tick sur le marché local
- `wildlife` → produit `Meat` / tick
- Surexploitation → signal prix → incitation à replanter (autorégulation)

### Migrations

Deux mécanismes distincts :
- **Porosité naturelle** : micro-flux passif entre tuiles limitrophes à chaque tick
- **Migration économique** : flux dirigé via routes, amplifié par l'écart d'attractivité (emploi, salaires, ressources)

### Routes commerciales
1. Lancer une **expédition** entre deux tuiles
2. Chemin calculé avec modificateurs terrain
3. Route établie → `TradeRoute` persistante → tuiles connectées sur le marché
4. Route active → génère de la demande d'ergol et de fret sur le marché

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

**Scope actuel : intra-système solaire** (Terre ↔ Mars, etc.). Les voyages inter-systèmes sont Phase 12+.

### Modèles existants
- `TradeRoute` : connexion permanente entre deux spaceports (`TradeRouteType.Orbital`)
- `ExpeditionUnit` : unité en transit avec `ticksRemaining`, `cargo`, `status`

### Durée
```
totalTicks = ceil(distanceUA / speedFactor × techMultiplier)
```
Modificateurs terrain (astéroïdes, etc.) → `+X ticks` à la création.

### Propriété et usage
- Vaisseaux appartiennent à une corporation **ou** un État
- Louables via **contrat** (ex : État fournit la route, Corp fournit le spaceport)
- Destruction possible sur événement grave

### Événements en trajet
- Tirés aléatoirement chaque tick (~3% de probabilité)
- Piraterie → perte partielle de cargo
- Panne → `ticksRemaining += X`
- Découverte → ressources bonus à l'arrivée

### Routes permanentes
- Créée après première expédition réussie entre deux spaceports
- Suspendue si un spaceport est détruit
- Perdue si les deux spaceports sont détruits

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

> Détail architecture : `questions/ia_modele_langage.md`  
> Features, design & discussion : `questions/gameplay_llm.md`

---

## 19. Multijoueur

- **Mode** : Asynchrone temps réel (monde persistant côté serveur)
- **Monde persistant** : tourne même quand tout le monde est déconnecté
- **Relations libres** : les joueurs peuvent être adversaires, partenaires ou neutres — pas de camps forcés

### Colonisation
- Une tuile sans gouvernement peut avoir une **population existante** (gens sans État)
- Pour la revendiquer : envoyer une **caravane** (pop de base embarquée)
- Tuiles limitrophes → micro-flux migratoire naturel dès la colonisation
- Pour croissance rapide : établir une **route** entre la nouvelle tuile et le territoire existant → flux migratoire amplifié

### Classement (leaderboard)
```
score = credits + (claimedTiles × 100) + (globalReputation × 50)
```
- Rafraîchi chaque tick, top 10 visible
- Pas de condition de victoire — pure simulation continue
- Les corporations peuvent aller en crédits négatifs mais restent dans la simulation

---

## 20. Conditions de Victoire

**Il n'y a pas de condition de victoire — le jeu est une simulation continue sans fin.**

- Pas de « game over », pas d'état final gagné/perdu
- Les corporations peuvent aller en crédits négatifs mais restent dans la simulation
- La compétition s'exprime via le **leaderboard** (voir §19)
- La coopération et les alliances émergent naturellement — elles ne sont pas imposées

> Les modes coopératif (terraformation globale partagée) et inter-étatique sont envisagés en Phase 12+ (polish).

---

## 21. Questions ouvertes & Points à designer

> C'est ici que les décisions non encore tranchées sont listées. Quand une décision est prise, elle est déplacée dans la section correspondante ci-dessus.

| Sujet | Question | Statut |
|---|---|---|
| Routes spatiales | Infrastructure spatioport à préciser | ❓ Ouvert |
| Présence alien | Types d'entités alien : pop hostile, empire galactique, mégastructure — modèle `StateData` alien ou type dédié ? | ❓ Ouvert |
| Points de Lagrange — blocus | Qu'est-ce que le blocus bloque exactement ? Toutes les ExpeditionUnit ? Seulement les commerciales ? | ❓ Ouvert |
| Points de Lagrange — bâtiments | Types de bâtiments orbitaux (station, ascenseur spatial, observatoire, dépôt) — détail Phase 12 | 🔄 Différé |
| Points de Lagrange — taxation | `passageTaxRate` configurable par contrat ou forfait ? Taxation partielle du cargo ou seulement en crédits ? | ❓ Ouvert |
| Points de Lagrange — lunes | Les lunes ont-elles leurs propres points de Lagrange ou partagent-elles ceux de leur planète parente ? | ❓ Ouvert |
| Espionnage | Mécanisme d'accès aux informations hors portée | ❓ Ouvert |
| Arbre de technologies | Structure, déblocage, diffusion | ❓ Ouvert |
| Multijoueur | Nombre de joueurs, synchronisation des ticks | ❓ Ouvert |
| Génération procédurale | Quoi est généré au démarrage (planètes, ressources, États initiaux…) | ❓ Ouvert |
| Militaire | Profondeur du système de combat / milices | ❓ Ouvert |
| États vassaux | Conditions d'autonomisation, rupture de vassalité | ❓ Ouvert |
| Quota de décisions | Valeur exacte, coût différencié par type d'action ? | ❓ Ouvert |
| Marché global | Formation uniquement par événement ou aussi par action joueur ? | ❓ Ouvert |
