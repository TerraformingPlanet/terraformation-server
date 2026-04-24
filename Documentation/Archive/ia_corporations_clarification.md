# IA Corporations — Questions de Clarification

> **Source design** : Description_du_jeu.md §11 — Corporations → Types de Corporations
> 
> **État implémentation** : ✅ Agents LLM États (Phase 8.5) | ❌ Bots Corpos = Phase 11 (TODO)

---

## Contexte design

### Trois profils IA de corporations

1. **Expansionniste**
   - Objectif : maximiser territorium (nombre de tuiles)
   - Stratégie : claim tuiles au maximum, peu de chantiers, focus construction militaire
   - Réaction : attaque si menacée, cherche à dominer map
   - Décision : rapide et agressive (peu de planification)

2. **Économiste**
   - Objectif : maximiser crédits (marché + production)
   - Stratégie : chaînes production longues, marché local dominant, peu de combats
   - Réaction : négocie plutôt qu'attaque, corrompt États amis
   - Décision : réfléchie, planification économique (5-10 ticks)

3. **Militariste / Saboteur**
   - Objectif : dominer ou déstabiliser
   - Stratégie : équipement militaire, espionnage, sabotage, alliances temporaires
   - Réaction : attaque préventive si menace détectée, sabote concurrents
   - Décision : impulsive et tactique (court terme)

### Réactions autonomes
- Aux **événements** (rébellion, tempête, découverte, compétiteur agressif)
- Aux **fluctuations marché** (pénurie de ressource, prix boom)
- Aux **actions autres corpos** (claim limit, placement bâtiment, commerce bloc)

---

## Questions à clarifier

### Q1 — Implémentation vs Agents LLM
- [ ] Utiliser les **agents LLM existants** (Phase 8.5) réadaptés pour Corpos ?
  - Agent = LLM + mémoire + outils
  - Profil = system prompt différent (Expansionniste vs Économiste)
  - Ou implémenter une **FSM déterministe** (pas de LLM, juste regles) ?
  
- [ ] Si FSM : où et quand les décisions se prennent ?
  - Tous les N ticks (ex : tous les 5 ticks) ?
  - Sur événement ?
  - Asynchrone (bot calcule en background) ?

### Q2 — Stratégie par profil
- [ ] Expansionniste : comment décide-t-elle quelle tuile claimer ?
  - Tuile adjacente au territoire existant ?
  - Tuile random ou stratégique (ressource rare) ?
  - Ratio claim/constructions : agressif ou modéré ?

- [ ] Économiste : comment construit-elle ses chaînes production ?
  - Recherche la tuile "idéale" (ex : riche en fer près d'eau) ?
  - Trial & error ou algorithme d'optimisation ?

- [ ] Militariste : quand attaque-t-elle exactement ?
  - Si tuile ennemie adjacente et elle a la force ?
  - Préemptif ou réactif après attaque reçue ?

### Q3 — Intégration avec le système
- [ ] Les bots Corpos utilisent-elles les mêmes endpoints que joueurs humains ?
  - `POST /game/corporations/{id}/claim-hex`
  - `POST /game/corporations/{id}/buildings`
  - `POST /game/corporations/{id}/expeditions`
  - Ou endpoints séparés (`/game/bot/...`) ?

- [ ] Ont-elles les mêmes ressources/handicaps que joueurs ?
  - Même quota de décisions/jour ?
  - Même coût construction ?

### Q4 — Mémoire et apprentissage
- [ ] Le bot se souvient-il de ses décisions passées ?
  - Pour ajuster stratégie (ex : "claim a échoué 3 fois, essayer ailleurs")
  - Ou décisions toujours fraîches (sans mémoire) ?

- [ ] Peut-il modifier sa stratégie en cours de partie ?
  - "J'étais expansionniste mais je suis ruiné, devenir économiste"
  - Ou profil fixe à création ?

### Q5 — Nombre et difficulté
- [ ] Combien de bots Corpos par partie ? 2 ? 4 ? 8 ?
- [ ] Niveaux de difficulté ?
  - Easy : décisions lentes, pas de coordination, easily beaten
  - Normal : réactionnel rapide, decent strategy
  - Hard : planification 10+ ticks, adaptation constante

### Q6 — Interaction joueur-bot
- [ ] Bot peut-il déclarer la guerre ? Négocier paix ? Nouer alliance temporaire ?
- [ ] Joueur peut-il lui proposer contrat ? Bot peut-il refuser / rénégocier ?
- [ ] Bot peut-il corrompre un État pour écraser un joueur ? Comment ?

### Q7 — Relation avec agents LLM États
- [ ] Bot Corpo différent d'Agent LLM État ?
  - États : contrôlent les regles, les taxes, les tolérances
  - Corpos : accumulent crédits, contrôlent tuiles, font commerce
  - Peuvent-elles interagir ? (Estado taxe Corpo IA, Corpo corrompt État IA)

---

## Réponses

### Q1 — Architecture IA : FSM + LLM hybride

✅ **DÉCISION** : Architecture **deux couches** :

**Couche 1 — FSM déterministe (tick-by-tick)**
Gère les décisions routinières à chaque tick selon des règles codées par profil :
- Expansionniste : `si tuile adjacente libre ET credits > seuil → enqueue claim`
- Économiste : `si prix ressource > seuil_boom → augmenter production de cette ressource`
- Militariste : `si corpo ennemie adjacente ET force_ratio > 1.2 → enqueue attaque`

Rapide, prévisible, pas de coût API. C'est le **comportement de fond** du bot.

**Couche 2 — Agent LLM (décisions stratégiques)**
Déclenché sur **événements clés** (pas chaque tick) pour prendre des décisions à haute valeur :
- Réordonner la **file de construction** (priorités stratégiques)
- Déclarer la **guerre** ou signer la **paix**
- Proposer/accepter/refuser un **contrat**
- Modifier les **seuils de tolérance** de la FSM (ex: "je deviens plus agressif si mes crédits dépassent X")
- Émettre des **règles** que la FSM respecte jusqu'à la prochaine intervention LLM

**Relation entre les deux couches :**
```
LLM (stratège)     → configure paramètres FSM + file + seuils
FSM (exécutant)    → applique les règles tick par tick dans les limites fixées par le LLM
```
Le LLM ne prend PAS chaque micro-décision — il gouverne la FSM.

---

### Q2 — Décisions LLM spécifiques aux bots Corpo

✅ **DÉCISION** : Extension de `AgentActionType` pour les Corporations :

```python
# Existant (États) :
SetTolerance, ProposeContract, TriggerNationalization

# À ajouter (Corporations) :
ReorderConstructionQueue   # réorganise la file de territoire
DeclareWar                 # déclaration offensive contre entité
ProposePeace               # proposition de cessez-le-feu
SetFSMThreshold            # modifie un seuil de la FSM (ex: aggressiveness)
SetFSMRule                 # ajoute/retire une règle comportementale
AdjustExpansionTarget      # change la tuile/zone cible d'expansion
```

**Exemple — LLM Expansionniste décide d'accélérer :**
> "Mes crédits sont à 8000 et j'ai 3 tuiles libres adjacentes. Je réordonne la file : claim les 3 tuiles avant les constructions. Et je monte le seuil d'aggressivité de 0.5 → 0.8."

→ LLM émet `ReorderConstructionQueue` + `SetFSMThreshold(aggressiveness=0.8)`
→ FSM exécute en conséquence jusqu'à la prochaine intervention

---

### Q3 — Endpoints

✅ **DÉCISION** : Les bots utilisent les **mêmes endpoints** que les joueurs humains.
- Pas d'endpoints `/bot/...` séparés
- Le serveur ne distingue pas humain vs bot au niveau API
- Différence uniquement côté orchestration : les bots sont déclenchés par le runtime, les humains par requêtes réseau

---

### Q4 — Mémoire

✅ **DÉCISION** : Réutilisation de `AgentMemory` (Phase 8.5), étendu aux Corporations.
- `entityType: "corporation"` (au lieu de `"state"`)
- `recentDecisions` : historique des dernières décisions LLM (max 5)
- `relationshipNotes` : mémoire des relations avec autres entités
- Profil FSM (Expansionniste / Économiste / Militariste) = **fixe à la création**, mais les **seuils** peuvent évoluer via LLM

---

### Q5 — Nombre et difficulté

✅ **DÉCISION** :
- **2 à 4 bots** par partie au lancement
- Difficulté = fréquence d'intervention LLM + qualité des seuils FSM initiaux :
  - Easy : FSM seule, pas de LLM, seuils conservateurs
  - Normal : LLM déclenché tous les 10 ticks ou sur événements
  - Hard : LLM déclenché tous les 3 ticks + mémoire longue + adaptation de profil

---

### Q6 + Q7 — Interactions joueur ↔ bot & rapport avec agents États

✅ **DÉCISION** :
- Bot Corpo peut déclarer la guerre, proposer un contrat, corrompre un État (via `ProposeContract` sur un État IA)
- Joueur peut proposer un contrat à un bot Corpo → le LLM bot évalue et accepte/refuse/rénégocie
- État IA (existant Phase 8.5) et Corpo IA (nouveau) sont **entités distinctes** mais interagissent via les mêmes mécanismes (contrats, taxes, tolérance, nationalisation)
- État IA peut taxer une Corpo IA → Corpo IA réagit via FSM/LLM
