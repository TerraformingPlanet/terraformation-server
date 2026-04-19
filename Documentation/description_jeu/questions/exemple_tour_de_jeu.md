# Exemple de tour de jeu

## Unité de temps

- **1 tick = 1 jour** (valeur de référence, ajustable pour l'équilibrage)
- Le jeu avance tick par tick, en temps discret

## File de décisions (énergie d'action)

- Un joueur dispose d'un quota de **décisions par jour** (ex : 10), qui se recharge chaque tick
- Toutes les décisions ont le même coût pour l'instant — prévu d'être ajustable pour l'équilibrage
- Les décisions ne prennent pas effet immédiatement : un délai simule la **hiérarchie d'exécution**
  - Signer un contrat → effet quasi-immédiat (décision directe)
  - Construire un bâtiment → délai plus long (il faut "passer le mot", réunir les ressources, etc.)
  - Le délai est variable selon le type d'action

---

## Les trois moteurs du jeu

### 1. Moteur économique
- Gestion des marchés : ajout et consommation de ressources
- Les bâtiments consomment des ressources à chaque tick
- La population consomme des biens via les marchés locaux
- Les prix évoluent selon l'offre et la demande

### 2. Moteur écologique (= terraformation)
- La pollution est une forme de terraformation négative — elle impacte les mondes au même titre que les rendre viables
- Chaque tuile a des **indicateurs environnementaux** : O₂, CO₂, azote, température
- Une fonction détermine si une espèce peut survivre sur une tuile, ou si elle subit des malus (comme un désert ou un pôle sur Terre)
- Si les conditions s'éloignent trop des seuils tolérés, l'espèce meurt progressivement — plus l'écart est grand, plus la disparition est rapide
- La nature évolue passivement : arbres qui poussent, animaux qui naissent/meurent, biodiversité dynamique
- Les bâtiments ont un impact écologique (pollution, déforestation…)
- Exemple : un État coupe des forêts → perte d'animaux → moins de conversion CO₂→O₂ → dégradation atmosphérique

### 3. Moteur joueur (décisions des corporations)
- Une corporation décide de construire un bâtiment
  - Elle peut payer l'État pour construire avec ses ressources
  - Ou apporter elle-même les ressources nécessaires
  - Si les ressources manquent : passer un contrat avec l'État ou une autre corporation pour les obtenir, ou les transporter depuis un autre monde
  - Quand toutes les ressources sont réunies, le bâtiment se construit sur X ticks

---

## Voyages interplanétaires

- La durée d'un trajet est **calculée à l'avance** selon la distance, les technologies disponibles et des modificateurs
- Pendant le décompte du trajet, des **événements aléatoires** peuvent survenir (piraterie, panne, opportunité…)
- Un vaisseau peut appartenir à un État ou une corporation
- Il est possible de **louer un vaisseau** via un contrat

---

## Bureaucratie

- La bureaucratie est une **caractéristique de l'État** (comme une stat RPG)
- Une décision de l'État prend X ticks de base, augmentés d'un pourcentage selon le niveau de bureaucratie
- Les corporations peuvent influencer cette stat (corruption, contrats d'influence…)
- Impact stratégique : un État très bureaucratique réagit lentement aux crises économiques ou écologiques
  - Exemple : un État veut nationaliser une corporation → le délai de bureaucratie laisse du temps pour corrompre un fonctionnaire, activer un contrat spécial et éviter la nationalisation
- Certaines décisions critiques (ex : réponse à une menace directe) peuvent bypasser partiellement la bureaucratie

