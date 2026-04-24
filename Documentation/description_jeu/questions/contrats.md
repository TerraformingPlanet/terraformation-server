# Système de contrats

## Qui peut proposer un contrat ?

- Les **États** proposent des contrats depuis un bâtiment dédié (ex : bureau administratif)
- Les **corporations** peuvent également proposer des contrats
- Les contrats peuvent exister entre **État ↔ Corporation** et **Corporation ↔ Corporation**

## Types de diffusion

- **Public (enchères)** : plusieurs corporations soumettent une offre, le proposeur choisit la meilleure
- **Privé (direct)** : contrat envoyé à une corporation spécifique, validation bilatérale requise
- Pas de négociation des termes — le proposeur calibre son offre dès le départ

## Types d'objectifs

- Production / livraison de ressources
- Contrôle territorial (X tuiles sur une lune / planète)
- Présence militaire (milice avec X employés sur une tuile)
- Exploration (découvrir une planète, rapporter des ressources)
- Bonus de surperformance : défini à la signature, déclenché si l'objectif est dépassé

## Durée et rupture

- **Durée fixe** : délai défini à la signature (ex : 20 ticks pour livrer X tonnes)
- **Open-ended** : fourniture continue, actif jusqu'à complétion ou rupture
- Un contrat peut être rompu en cours → pénalité financière + réputation

## Récompenses et pénalités

- Récompenses variées : argent, influence, accès à des technologies, bonus de marché
- Pénalité d'échec : financière + réputation (globale et bilatérale)

## Réputation

- **Réputation globale** : score public visible par tous (mauvais payeur = connu partout)
- **Relation bilatérale** : score spécifique par paire (Corporation ↔ État, Corporation ↔ Corporation)
- Les deux coexistent : on peut être globalement fiable mais détesté par un État spécifique

## Nationalisation

- Un État peut **nationaliser** les bâtiments et tuiles d'une corporation s'il la juge trop puissante ou hostile
- La décision dépend du **type d'État** (un État capitaliste sera peu enclin, un État nationaliste très enclin)
- Perdre toutes ses tuiles dans un État = perte d'accès à son marché
- Le **taux de corruption** de l'État influence ses décisions :
  - **Passive** : un État corrompu est moins efficace, propose de moins bons contrats
  - **Exploitable** : une corporation peut corrompre un État (réduire les taxes, éviter la nationalisation, obtenir des avantages) avec un coût et un risque

## États et IA

- Les États sont contrôlés par la simulation (IA)
- Un **agent LLM** peut intervenir de deux façons :
  - **A — Décisions stratégiques** : nationalisation, politique économique, lancement de contrats majeurs
  - **B — Réactions événementielles** : déclenchées par un événement (corporation trop puissante, contrat raté, crise)
- En dehors de ces interventions, l'IA standard gère le comportement de l'État

## Connaissance et innovations

- La connaissance **irradie passivement** avec le temps — les autres corporations et les États l'obtiennent progressivement
- Installer un bâtiment de type "connaissance" dans un État = accès rapide à tout ce que cet État possède déjà
- Une corporation peut **revendre une connaissance** à un État ou à une autre corporation via contrat
- Une corporation peut **donner des bonus** à un État (ex : amélioration agricole, technologie médicale) — outil diplomatique

---

## Exemples

### Exemple 1 — Contrat de connaissance agricole (Corp ↔ État)

Une corporation développe une variété de blé plus productive dans son laboratoire. Elle propose un contrat **privé** à un État voisin : fourniture de nourriture en échange de crédits et d'influence. L'État accepte et commence à recevoir les livraisons. Progressivement, la connaissance agricole **irradie** vers cet État et ses voisins — mais la corporation garde un avantage temporaire grâce à sa maîtrise opérationnelle.

**Ce que ça illustre :** contrat de livraison de ressources, réputation bilatérale Corp↔État, diffusion passive de connaissance.

---

### Exemple 2 — Route commerciale interplanétaire (État ↔ Corp)

**Contexte :** La France (État, Terre) souhaite ouvrir une route commerciale entre l'Europe et MarsCity pour rapprocher leurs marchés. Elle possède une route spatiale Terre→Mars mais n'a pas de spaceport privé sur Mars.

**Le contrat :** La France propose un contrat **public (enchères)** ouvert aux corporations disposant d'un spaceport sur Mars. **Space Lille** remporte l'enchère.

**Termes du contrat :**
- Space Lille : fournit l'accès à son **spaceport** sur Mars + gestion logistique des rotations
- France : fournit la **route spatiale** Terre→Mars + les vaisseaux de transport initiaux
- Objectif : maintenir X rotations/tick pendant N ticks
- Récompense : crédits/tick versés à Space Lille + bonus d'influence pour la France sur MarsCity

**Effets en jeu une fois la route active :**
- Une **demande d'ergol** apparaît sur le marché local (ex : 30 unités/vaisseau/rotation)
- Une **demande de fret** (vaisseaux de transport) est générée sur le marché interplanétaire
- Les **prix** des ressources échangées convergent progressivement entre les deux marchés (propagation hiérarchique : Terre ← route → Mars)
- Si Space Lille ne maintient pas les rotations → rupture de contrat → pénalité financière + malus réputation bilatérale France↔Space Lille

**Ce que ça illustre :** contrat État↔Corp avec enchère publique, dépendance aux ressources infra (ergol, vaisseaux), effet marché d'une route commerciale, risque de rupture.