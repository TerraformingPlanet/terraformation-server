# Perte de contrôle d'une tuile

## Propriété d'une tuile

- Une tuile appartient à un **État** ou une **corporation**
- Une tuile non colonisée (espace profond, planète vierge) n'appartient à personne

---

## Conditions de perte de contrôle

### Par rébellion de la population
- Si les besoins vitaux ne sont pas satisfaits (nourriture, salaire, conditions de vie), la population réagit progressivement :
  1. Baisse de productivité
  2. Grève
  3. Rébellion → la corporation est chassée de la tuile
- Déclenchement automatique par le moteur de simulation, sans intervention de l'État

### Par rupture de contrat avec l'État
- Si la corporation rompt un contrat, l'État peut décider de reprendre ses tuiles et bâtiments en guise de pénalité

### Par seuil de tolérance de l'État
- L'État calcule un **score de tolérance** pour chaque corporation présente sur son territoire
- Facteurs : puissance économique, influence territoriale, comportement (contrats respectés, pollution, etc.)
- Si la corporation dépasse le seuil → l'État peut déclencher une nationalisation
- Le type d'État et son taux de corruption influencent ce seuil (État capitaliste = seuil élevé, État nationaliste = seuil bas)

---

## Processus de reprise par l'État

- La transition n'est pas instantanée — elle dépend de la **bureaucratie** et de la **corruption** de l'État
- L'État envoie des fonctionnaires → délai de X ticks (variable) → prise de contrôle effective
- Pendant ce délai, la corporation peut :
  - Corrompre des fonctionnaires pour ralentir ou annuler la procédure
  - Activer un contrat spécial pour négocier une issue
  - Retirer ses salariés et actifs stratégiques
- Au bout du délai : la corporation perd le bâtiment ou la tuile

---

## Corporation contre corporation

- Une corporation peut **attaquer une autre corporation** pour revendiquer une tuile ou un bâtiment
- Si un État est présent sur la tuile, l'attaque peut lui déplaire → dégradation de la relation avec cet État
- L'attaque peut passer par :
  - Un conflit militaire direct (milices)
  - Un rachat forcé via pression économique
  - Un contrat d'exclusivité passé avec l'État pour évincer la concurrence

---

## Tuile sans État (espace non colonisé)

- Une corporation peut **réclamer une tuile libre** en y construisant une infrastructure
- Une corporation peut également **créer un État vassal** à partir de tuiles qu'elle contrôle entièrement
  - Cet État vassal lui est subordonné mais évolue selon les mêmes règles (bureaucratie, tolérance, corruption)
  - Avec le temps et de l'influence, un État vassal peut gagner en autonomie

---

## Conséquences pour la corporation

- Perte d'accès au marché local de la tuile
- Perte des bâtiments (nationalisés ou détruits selon le contexte)
- Pénalité de réputation (globale et bilatérale)
- Si toutes les tuiles d'un État sont perdues → exclusion totale du marché de cet État


