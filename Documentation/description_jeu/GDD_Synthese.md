# Game Design Document — Synthèse (v1)

> Document consolidé à partir de la session de design du 19/04/2026.
> Sources : `Description_du_jeu.md` + dossier `questions/`.

---

## 1. Concept général

Jeu de **simulation / exploration / colonisation spatiale en temps discret (tick-based)**.

Le joueur incarne une **corporation** dont l'objectif est :
- d'étendre son influence territoriale
- de contrôler des tuiles pour accéder aux marchés
- de générer du profit via production, commerce et contrats

Inspirations : **Victoria** (économie & marchés), **Per Aspera** (planète + tuiles + simulation), **4X / gestion**.

---

## 2. Structure de l'univers

```
Galaxie
 └── Systèmes stellaires
      └── Corps célestes (planètes, lunes…)
           └── Tuiles (grille H3 — hexagones géospatiaux)
```

- Chaque tuile est l'unité de base exploitable
- Une tuile appartient à un **État**, une **corporation**, ou à personne (espace non colonisé)
- Les tuiles ont des **indicateurs environnementaux** : O₂, CO₂, azote, température

---

## 3. Système de temps

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

## 4. Les trois moteurs du jeu

### 4.1 Moteur économique
- Gestion des marchés : offre/demande à chaque tick
- Les bâtiments et la population consomment des ressources
- Les prix se propagent entre tuiles connectées, atténués par la distance
  - Exemple : pénurie sur tuile A → -50% sur A, -30% sur B (1 saut), -10% sur C (2 sauts)

### 4.2 Moteur écologique (= terraformation)
- La pollution est une **forme de terraformation négative**
- Une fonction continue détermine si une espèce peut survivre sur une tuile ou subir des malus
  - Si l'écart aux seuils tolérés est trop grand → mort progressive accélérée
  - Pas de seuil binaire : malus croissants selon l'écart (comme un désert ou un pôle)
- La nature évolue passivement : arbres, animaux, biodiversité dynamique
- Exemple de chaîne : déforestation → perte d'animaux → moins de conversion CO₂→O₂ → dégradation atmosphérique

### 4.3 Moteur joueur
- La corporation décide, dépense des décisions, attend les effets
- Si les ressources manquent pour une construction : passer un contrat, ou les transporter depuis un autre monde

---

## 5. Bâtiments

### Modèle général
```
Entrées (ressources + travailleurs + énergie)
        ↓
    Bâtiment
        ↓
Sorties (ressources + déchets + effets par tick)
```

### Travailleurs
- Population locale + salariés corpo (considérés comme habitants de la tuile)
- Ratio 0→100% : 100% = plein rendement, 0% = bâtiment abandonné
- Si la corpo retire ses salariés → l'État peut nationaliser

### Réseau énergétique
- Une centrale produit X énergie, distribuée aux tuiles adjacentes via des segments de réseau
- Chaque segment a une capacité maximale — construire plusieurs segments augmente la charge
- L'énergie est disponible sur le marché local

### Déchets
- S'accumulent sur la tuile à chaque tick
- Sans bâtiment de traitement → impact écologique négatif sur la faune et la flore

### Technologies et évolution
- Une technologie peut **améliorer** une entrée (ex : pioche → dynamite = +rendement, +risque) ou la **remplacer** (pioche → foreuse = moins de travailleurs)
- Upgrade à appliquer **bâtiment par bâtiment** (pas automatique)
- Crée des chaînes de production : usine de dynamite → mine améliorée

### Épuisement et reconversion
- Ressource épuisée → bâtiment inutile
- Options : **abandonner** (risque d'événements négatifs : groupe armé, ruine…) ou **reconvertir** (construire un nouveau bâtiment par-dessus, ex : mine → silo à missiles)

---

## 6. Marchés

### Hiérarchie
```
Tuile → Planète → Système stellaire → Marché global (inter-étatique, optionnel)
```

### Population et niveaux de richesse
- Distribuée en **catégories sociales** avec des besoins différents :
  - Pauvres → nourriture, vêtements de base
  - Classes moyennes → biens manufacturés
  - Riches → luxe, tourisme, voyages interplanétaires
- La richesse **évolue** : un ouvrier mieux payé monte de catégorie après X ticks
- **Migrations** possibles vers des tuiles plus attractives en cas de déséquilibre de main-d'œuvre

### Routes commerciales
1. Lancer une **expédition d'exploration** entre deux tuiles
2. Les explorateurs calculent un chemin avec modificateurs de terrain (ex : montagne = +10 ticks)
3. Construire la route physique → les deux tuiles se voient sur le marché
- Routes spatiales : même principe, infrastructure dédiée (spatioport — à préciser)

### Régulation
- **Marché national** : régulé par l'État via taxes/quotas, influençable par corruption
- **Marché global** : se crée via un organisme inter-étatique (événement aléatoire ou action volontaire)
  - Corruptible par les corporations → peut devenir une façade corporatiste (objectif de fin de partie possible)

---

## 7. Contrats

### Qui peut proposer
- États (depuis un bâtiment dédié) et corporations
- Contrats possibles : État ↔ Corporation, Corporation ↔ Corporation

### Types de diffusion
- **Public (enchères)** : plusieurs soumettent une offre, le proposeur choisit la meilleure
- **Privé (direct)** : validation bilatérale requise, pas de négociation des termes

### Types d'objectifs
- Production/livraison de ressources
- Contrôle territorial (X tuiles)
- Présence militaire (milice avec X employés)
- Exploration / transport de ressources
- Bonus de surperformance défini à la signature

### Durée et rupture
- **Durée fixe** ou **open-ended** (fourniture continue)
- Rupture possible → pénalité financière + réputation

### Récompenses et pénalités
- Récompenses : argent, influence, technologies, bonus de marché
- Pénalités : financières + réputation globale + réputation bilatérale

### Connaissance et innovations
- La connaissance **irradie passivement** avec le temps vers les autres entités
- Un bâtiment de recherche dans un État = accès rapide à ce que cet État sait déjà
- Revendable via contrat (corpo → État, corpo → corpo)

---

## 8. États

### Caractéristiques
- Possèdent des tuiles, des bâtiments de production, une population
- Ont un **type** (capitaliste, nationaliste, mixte…) qui influence leur comportement
- Ont un **taux de corruption** (passif : moins efficace ; exploitable : influençable par les corporations)
- Ont un **score de bureaucratie** (stat RPG) : délai = base × (1 + % bureaucratie)

### Seuil de tolérance
- Chaque corporation présente dans l'État a un score calculé selon sa puissance, son comportement, ses contrats
- Si le seuil est dépassé → nationalisation possible

### Nationalisation
- Processus progressif (délai variable selon bureaucratie + corruption)
- Pendant le délai : la corporation peut corrompre, négocier, activer un contrat spécial
- Au terme du délai : perte du bâtiment ou de la tuile

---

## 9. Contrôle et perte de tuiles

### Conditions de perte de contrôle
1. **Rébellion** : besoins vitaux non satisfaits → baisse de productivité → grève → rébellion
2. **Rupture de contrat** : l'État peut reprendre ses biens
3. **Seuil de tolérance dépassé** : nationalisation

### Corporation contre corporation
- Attaque possible (milices, pression économique, contrat d'exclusivité)
- Risque de dégradation de la relation avec l'État présent

### Tuile sans État
- Revendicable par construction d'une infrastructure
- Une corporation peut créer un **État vassal** (évolue selon les mêmes règles, peut gagner en autonomie)

### Conséquences
- Perte d'accès au marché local
- Perte des bâtiments (nationalisés ou détruits)
- Pénalité de réputation
- Zéro tuile dans un État = exclusion totale de son marché

---

## 10. Voyages interplanétaires

- Durée calculée à l'avance (distance + technologies + modificateurs)
- Événements aléatoires possibles pendant le trajet (piraterie, panne, opportunité)
- Un vaisseau appartient à un État ou une corporation — louable via contrat

---

## 11. IA & Agents LLM

### Rôle
- Un agent LLM peut contrôler un État ou une corporation via des **outils MCP**
- Outils : lire l'état du jeu, prendre des décisions, donner des objectifs

### Fréquence
- **Sur événement** (rébellion, contrat disponible, menace…)
- **Toutes les N ticks** (réévaluation stratégique)
- Les deux modes coexistent selon l'importance de la décision

### Contexte
- L'agent ne voit que ce que son rôle lui permet
- Informations hors portée → nécessite exploration ou espionnage

### Mémoire
- Chaque entité a sa propre mémoire contextuelle :
  - **Profil** : personnalité, valeurs, stratégie
  - **Événementielle** : historique des décisions et contrats
  - **Relationnelle** : état des relations avec les autres entités

---

## 12. Points ouverts (à traiter)

| Sujet | Question |
|---|---|
| Routes spatiales | Infrastructure spatioport à préciser |
| Espionnage | Mécanisme d'accès aux informations hors portée |
| Arbre de technologies | Structure, déblocage, diffusion |
| Conditions de victoire | Objectifs de fin de partie (richesse, contrôle, organisme global…) |
| Multijoueur | Nombre de joueurs, synchronisation des ticks |
| Génération procédurale | Quoi est généré (planètes, ressources, États initiaux…) |
| Militaire | Profondeur du système de combat / milices |
| États vassaux | Conditions d'autonomisation, rupture de vassalité |
