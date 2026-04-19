# IA & Modèle de langage

## Rôle général

Un agent LLM peut contrôler une entité du jeu (État ou corporation) en interagissant avec la simulation via des **outils MCP**.

---

## Interface via MCP

- L'agent dispose d'un ensemble d'**outils MCP** pour :
  - **Lire** l'état du jeu (tuiles, marchés, ressources, relations, événements…)
  - **Prendre des décisions** (construire un bâtiment, signer un contrat, ordonner une prise de tuile…)
  - **Donner des objectifs** à une entité qu'il contrôle (ex : "prendre le contrôle de cette région", "développer l'industrie alimentaire")
- L'agent ne voit que ce que ses outils lui permettent de voir — le contexte est limité par son rôle

---

## Contexte disponible selon l'entité

- Le contexte fourni à l'agent dépend de **qui il contrôle** :
  - **État** : ses tuiles, ses bâtiments, ses marchés, ses relations avec les corporations, ses contrats actifs
  - **Corporation** : ses tuiles, ses bâtiments, ses ressources, ses contrats, les marchés accessibles
- Les informations hors de sa portée nécessitent une action (exploration, espionnage) — à définir plus précisément selon le contexte

---

## Fréquence d'interrogation

- Le LLM est hébergé localement → coût en tokens maîtrisé, tests possibles sans contrainte externe
- Deux modes à tester et équilibrer :
  - **Sur événement** : l'agent est appelé uniquement quand un événement significatif se produit (rébellion, contrat disponible, menace…)
  - **Toutes les N ticks** : l'agent est interrogé régulièrement pour réévaluer sa stratégie
- Les deux modes peuvent coexister selon l'entité ou l'importance de la décision

---

## Mémoire des agents

- Chaque entité contrôlée par un agent a sa propre **mémoire contextuelle**
- La mémoire permet à l'agent de rester cohérent dans ses décisions (ex : un État nationaliste ne se met pas soudain à privatiser)
- Types de mémoire envisagés :
  - Mémoire de **personnalité/profil** : valeurs, stratégie, type d'État/corpo
  - Mémoire **événementielle** : historique des décisions récentes, contrats en cours
  - Mémoire **relationnelle** : état des relations avec les autres entités

---

## Exemples d'utilisation

- Un agent contrôle un État → il détecte une pénurie alimentaire → il propose un contrat à une corporation agricole
- Un agent contrôle une corporation → il voit un marché sous-approvisionné → il ordonne la construction d'une usine et la prise de tuiles adjacentes
- Sur événement "seuil de tolérance dépassé" → l'agent de l'État décide ou non de nationaliser
- L'agent "maître de jeu" surveille la partie globale et peut déclencher des événements scénarisés
