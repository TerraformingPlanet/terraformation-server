# Skill — game-design-ref

## Quand utiliser ce skill

Chaque fois qu'une question de design est posée sur Terraformation — mécanique de jeu, comportement d'une entité, règles économiques, États, réputation, contrats, bâtiments, marchés, IA — **avant toute implémentation**, consulter les fichiers ci-dessous pour cadrer la réponse sur les décisions de design déjà prises.

Ce skill est la référence canonique pour répondre aux questions de conception avant de toucher au code.

---

## Fichiers de référence

### Fichier principal
| Fichier | Contenu |
|---------|---------|
| `Documentation/description_jeu/Description_du_jeu.md` | **SOURCE DE VÉRITÉ** — concept, tick system, univers, tuiles, corps, états, ressources, bâtiments, marchés, IA, points ouverts. Sections 1–21 exhaustives. Sommaire cliquable en tête du fichier. |

### Questions thématiques (chacune = un aspect du design approfondi)
| Fichier | Sujet |
|---------|-------|
| `Documentation/description_jeu/questions/contrats.md` | Contrats (qui peut proposer, types, objectifs, durée, rupture, réputation, nationalisation, connaissance) |
| `Documentation/description_jeu/questions/marche_local.md` | Marchés (hiérarchie H3, offre/demande, propagation des prix, routes, corruption, marché global) |
| `Documentation/description_jeu/questions/perte_de_controle_tuile.md` | Perte de contrôle d'une tuile (rébellion, nationalisation, processus, délai bureaucratie, fenêtre réaction) |
| `Documentation/description_jeu/questions/exemples_batiments.md` | Bâtiments (modèle entrée/sortie, mine de charbon, travailleurs, énergie, déchets, reconversion, technologie) |
| `Documentation/description_jeu/questions/exemple_tour_de_jeu.md` | Tour de jeu (tick=1 jour, quota décisions, 3 moteurs : économique/écologique/joueur, bureaucratie, voyages) |
| `Documentation/description_jeu/questions/ia_modele_langage.md` | IA LLM (MCP tools, contexte par entité, fréquence N ticks ou événement, mémoire profil/événementielle/relationnelle) |
| `Documentation/description_jeu/questions/lexique.md` | Lexique termes de jeu + correspondances Python/C# (tick, tuile, corp, ResourceType, BuildingType, TradeRoute, conventions code) |

---

## Décisions de design clés à retenir

### Entités fondamentales
- **Corporation** : argent, tuiles, bâtiments, marchés, contrats → objectif = richesse + territoire
- **État** : tuiles, population, marchés, contrats avec corps → IA par défaut, optionnellement piloté par LLM
- **Tuile** : appartient à corp ou État (ou personne si non colonisée). Possède marché local, population, ressources, bâtiments

### Réputation (Phase 7.5)
- **Réputation globale** : score public visible par tous — mauvais payeur = connu partout
- **Relation bilatérale** : score spécifique par paire (Corp ↔ État, Corp ↔ Corp) — on peut être globalement fiable mais détesté d'un État
- Les deux coexistent et évoluent séparément

### États — caractéristiques
- **Type** : capitaliste (seuil tolérance élevé), nationaliste (seuil bas) — influence décisions de nationalisation
- **Corruption** :
  - Passive : État moins efficace, contrats moins intéressants
  - Exploitable : une corp peut corrompre (réduire taxes, éviter nationalisation, avantages)
- **Bureaucratie** : délai sur toutes les décisions d'État. Délai = base × (1 + bureaucratie%). Peut être réduit via corruption/contrats
- Tuiles contrôlées : un État = ensemble de tileIds (pas nécessairement une planète entière)

### Nationalisation (Phase 7.5)
- Déclencheur : corp dépasse le seuil de tolérance de l'État (puissance économique, influence territoriale, comportement)
- Délai = bureaucratie + corruption de l'État (variable N ticks)
- Pendant le délai, la corp peut :
  1. Corrompre des fonctionnaires → ralentir/annuler la procédure
  2. Activer un contrat spécial → négocier une issue
  3. Retirer ses salariés et actifs stratégiques
- Après délai : corp perd le bâtiment ou la tuile (pas de rachat — seule la corruption/contrat l'évite)
- Conséquences : perte accès marché local, perte bâtiments, pénalité réputation bilatérale + globale

### Contrats État ↔ Corp
- États peuvent proposer des contrats (depuis un bâtiment dédié type "bureau administratif")
- Objectifs possibles : livraison ressources, contrôle territorial, présence militaire, exploration
- Récompenses : argent, influence, accès technologies, bonus marché

### Connaissances / Innovation
- Irradie passivement avec le temps (autres corps/États l'obtiennent progressivement)
- Construire un bâtiment connaissance dans un État = accès rapide à ce que l'État possède
- Vendable/donnable via contrat (outil diplomatique)

### Scoreboard
- KPI : richesse (crédits), contrôle territorial (nb tuiles), `habitabilityScore` (KPI environnemental)
- Visible par tous

---

## Protocole d'utilisation

1. La question porte sur une mécanique de jeu ? → lire le fichier thématique correspondant ci-dessus
2. Question transversale ? → lire `Description_du_jeu.md` en premier
3. Contradiction entre ce skill et le GDD ? → `Description_du_jeu.md` fait foi (source principale). `GDD.md` est un miroir archivé non maintenu.
4. Nouvelle décision de design prise en session → la noter dans `Documentation/description_jeu/questions/` dans le fichier thématique approprié, ou créer un nouveau fichier si thème absent
5. Nouveau terme technique introduit en implémentation → l'ajouter dans `questions/lexique.md` (terme, définition, §GDD, modèle Python, type C#) avant de fermer la phase
