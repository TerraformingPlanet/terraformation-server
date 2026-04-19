---

# 📘 Game Design / Technical Statement (v1)

## 🎯 Concept général

Jeu de **simulation / exploration / colonisation spatiale en temps discret (tick-based)**.

Le joueur incarne une **corporation** dont l’objectif est :

* d’étendre son influence
* de contrôler des territoires (tuiles)
* de générer du profit via production et marchés

---

## ⏱️ Système de temps

* Le jeu fonctionne en **ticks**
* À chaque tick :

  * production des bâtiments
  * consommation de ressources
  * mise à jour des marchés
  * évolution des états (population, économie)

```csharp
// Exemple conceptuel
// 1 tick = X secondes (configurable)
```

---

## 🌌 Structure de l’univers

Hiérarchie :

```
Galaxie
 └── Systèmes stellaires
      └── Corps célestes (planètes, lunes, etc.)
           └── Tuiles (grid H3)
```

* Les planètes sont représentées avec un système de grille basé sur :
  👉 H3 (hexagones géospatiaux)

Chaque tuile représente une unité exploitable du terrain.

---

## 🧩 Tuiles (Cells)

Chaque tuile possède :

* un propriétaire (corporation ou État)
* un marché local
* des ressources / caractéristiques (à définir)
* éventuellement des bâtiments

### Contrôle

Une corporation perd le contrôle d’une tuile si :

* elle ne satisfait plus certaines conditions (ex : nourriture, personnel, énergie…)

---

## 🏢 Corporations (joueurs)

Les corporations :

* possèdent de l’argent
* contrôlent des tuiles
* construisent des bâtiments
* interagissent avec les marchés
* peuvent signer des contrats avec les États

### Objectif

Maximiser :

* richesse
* contrôle territorial

---

## 🏛️ États (gouvernements + population)

Les États :

* possèdent des tuiles
* ont une population
* consomment des biens via le marché
* influencent les prix

Ils peuvent :

* proposer des **contrats** aux corporations

---

## 📜 Système de contrats

Un contrat contient :

* un objectif (ex : produire X ressources)
* une récompense (argent, influence…)

---

## 🏭 Bâtiments

Pour exploiter une tuile :

1. une corporation doit **acheter la tuile**
2. construire un bâtiment

### Modèle de production

```
Entrées (ressources)
      ↓
   Bâtiment
      ↓
Sorties (ressources / effets)
```

### Caractéristiques :

* coût de construction
* coût par tick
* production par tick
* contraintes (ex : dépendance à l’état, ressources locales…)

---

## 📈 Système économique (clé du jeu)

### Marchés

* Chaque tuile possède un **marché local**
* Les marchés sont **hiérarchiques** :

  ```
  Tuile → Planète → Système → (optionnel : inter-système)
  ```

### Fonctionnement :

* Les États consomment des biens → impact sur les prix
* Les corporations produisent/vendent → influencent les marchés
* Pour influencer un marché :
  👉 il faut posséder un bâtiment sur une tuile

---

## 🤖 IA & Modèle de langage

Un modèle de langage peut être utilisé pour :

* générer des systèmes stellaires
* aider à la prise de décision des IA
* enrichir les interactions (contrats, événements…)

⚠️ À garder contrôlé (coût + cohérence gameplay)

---

## 🧠 Inspirations

* Victoria (économie & marchés)
* Per Aspera (planète + tuiles + simulation)
* 4X / gestion



