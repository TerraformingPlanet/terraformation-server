# Decision Queue — Questions de Clarification

> **Source design** : Description_du_jeu.md §4 — Système de temps → File de planification (decision queue)
> 
> **État implémentation** : ❌ Pas visible en code actuellement

---

## Contexte design

Une **file de décisions persistante** (inspirée Victoria 3) :
- Réordonnée librement par le joueur (drag & drop HUD) ou agent LLM
- **Persistante** : survit déconnexion et restart serveur
- À chaque tick, les décisions dont les **conditions d'entrée sont satisfaites** se déclenchent
- Structure : `type`, `targetId`, `params`, `enqueuedTick`, `startTick`, `resolvesTick`, `status`
- Statuts : `pending` / `in_progress` / `blocked` / `suspended` / `done`
- **Quota d'actions** : ~10 décisions/jour, rechargé chaque tick
- Délais variables selon type : signature contrat (immédiat), bâtiment (long), terraformation (très long)

---

## Questions à clarifier

### Q1 — Priorité & MVP
- [ ] La Decision Queue est-elle **Phase 10** ou **après Phase 12** (polish) ?
- [ ] Y a-t-il un MVP simplifié (ex : pas de réordonneur HUD, file linéaire d'abord) ?

### Q2 — Implémentation actuelle des actions
- [ ] Les actions actuelles (**claim**, **construct**, **sign_contract**, **terraform**) passent-elles par une file ou sont-elles directes/immédiates ?
- [ ] Existe-t-il un système de blocage si ressources manquent (ex : cannot construct tant que pas assez de fer) ?

### Q3 — Quota de décisions
- [ ] Chaque joueur a-t-il un quota rechargeable (ex : 10/jour) ou c'est illimité ?
- [ ] Le quota s'applique à toutes les actions ou seulement à certaines (ex : construction seule) ?

### Q4 — Persistance
- [ ] Faut-il sauvegarder la file en PostgreSQL ou peut-elle rester en mémoire serveur (perdue au restart) ?
- [ ] La file doit-elle survivre à la perte d'une tuile (ex : chantier suspendu) ?

### Q5 — Intégration agents LLM
- [ ] Les agents LLM (États/Corpos IA) remplissent-ils la file à chaque cycle, ou agissent-ils directement ?
- [ ] Comment gérer les conflits : deux entités veulent la même tuile, laquelle passe en premier ?

### Q6 — Délais d'exécution
- [ ] Comment calculer `resolvesTick` ? Formule fixe ou dynamique (ex : selon constructionCapacity) ?
- [ ] Exemple concret : construire une Mine coûte 90 points, EB produit 30/tick → 3 ticks ? Et si EB devient inactif ?

---

## Réponses

### Q1 — Priorité & MVP

✅ **DÉCISION** : La Decision Queue est implémentée **maintenant** (pas reportée à Phase 12).
Pas de MVP simplifié obligatoire — on peut partir directement sur la version complète.

---

### Q3 — Quota de décisions

✅ **DÉCISION : Quota ABANDONNÉ.**
Le quota (~10 décisions/jour) avait été conçu comme anti-spam, mais la file elle-même constitue le frein naturel :
- L'entité peut enregistrer autant d'entrées qu'elle veut dans la file
- La capacité de construction par tick est la vraie contrainte limitante
- Pas besoin d'un compteur supplémentaire

---

### Structure des files — par territoire (décision clé)

✅ **DÉCISION** : La file n'est **pas globale par entité** — elle est **par gouvernement/territoire**.

**Règle :** Un groupe de tuiles **limitrophes** appartenant à la même entité (État ou Corporation) partage **une seule file** avec le **cumul de leurs `constructionCapacity`**.

**Exemple :**
- Entité A possède 10 tuiles contiguës, chacune avec `constructionCapacity = 30`
- → Ces tuiles forment **1 territoire** → **1 file** avec une capacité cumulée de **300 points/tick**
- Si les tuiles se divisent en 2 groupes non contigus → **2 files distinctes**, chacune avec sa propre capacité cumulée

**Conséquences de design :**
- **Incitation à l'expansion contiguë** : plus le territoire est compact, plus la construction est rapide
- **Défragmentation stratégique** : conquérir une tuile reliant deux groupes peut fusionner deux files → accélération
- **Perte de tuile** : si la contiguïté est brisée, les files se fractionnent (les constructions `in_progress` sont suspendues ou perdues selon position)

**Modèle de données suggéré :**
```
TerritoryQueue:
  id: str (ex: "entity_id::territory_hash")
  entityId: str
  tileIds: list[str]          # tuiles contiguës membres
  constructionCapacity: int   # somme des capacités des tuiles membres
  queue: list[DecisionEntry]  # file ordonnée
```

---

### Q4 — Persistance

✅ **DÉCISION** : La file est **persistante en PostgreSQL**.
- Survit aux restarts serveur et aux déconnexions joueur
- Si une tuile quitte le territoire (perte, vente, conquête) :
  - Construction `in_progress` sur cette tuile → **perdue** (pas de remboursement, cf. `construction_files_clarification.md`)
  - Constructions `pending` restantes → **conservées** dans la file du territoire résiduel

---

### Q2 — Implémentation des actions (claim / construct)

✅ **DÉCISION** : `construct` passe par la file de territoire. `claim` **n'est pas immédiat** — il nécessite une **unité de colonisation**.

**Règles du claim :**
- Une tuile **sans gouvernement** peut avoir une population existante (des gens y vivent sans État)
- Pour la revendiquer, l'entité envoie une **unité de colonisation** vers la tuile cible
- L'unité prend du temps à arriver (délai selon distance / infrastructure disponible)
- À l'arrivée :
  - Tuile libre (sans gouvernement) → **colonisation** réussie, la tuile intègre le territoire de l'entité
  - Tuile occupée par une autre entité → **conquête** requise (conflit, coût, risque de perte de l'unité)
- `claim` passe donc par la file avec un statut `in_progress` pendant le trajet de l'unité

**Population initiale de la tuile colonisée :**
- La caravane de colonisation **transporte une population de base** avec elle
- À l'arrivée, la tuile reçoit cette population minimale (ex: quelques centaines de `Poor`)
- Croissance naturelle ensuite, mais **lente** si la tuile est isolée

**Croissance via flux migratoire :**
- Deux tuiles **limitrophes** ont toujours un **micro-flux naturel** passif entre elles (diffusion démographique de base)
- Une **route** entre deux tuiles **amplifie** ce flux (multiplicateur à définir, ex: ×5 ou ×10)
- Sans route sur tuile non limitrophe → pas de flux du tout
- Avec route → flux actif proportionnel à la route et à l'écart démographique entre les tuiles
