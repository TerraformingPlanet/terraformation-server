# Gameplay LLM — Features, Design & Discussion

> Ce fichier est l'espace de réflexion sur les features LLM côté gameplay :  
> ce que le joueur perçoit, ce que les entités IA font, et ce qu'on veut construire.  
> Architecture technique → `ia_modele_langage.md`  
> Implémentation Phase 8.5 (États) → ROADMAP §Phase 8.5  
> Implémentation Phase 11 (Corporations) → ROADMAP §Phase 11

---

## 1. Vision

Le LLM n'est **pas** le moteur de simulation — il est une **couche de décision narrative** par-dessus la simulation.

La simulation tourne indépendamment (tick Python pur). Le LLM intervient pour :
- Donner de la **cohérence narrative** aux entités IA (un État nationaliste agit comme tel)
- Permettre des **décisions complexes** qui dépassent les capacités d'une FSM simple
- Offrir un **partenaire de jeu crédible** qui réagit au contexte, pas seulement aux seuils numériques

**Ce que le LLM ne fait PAS** : calculer les prix, gérer les ticks, valider les règles — ça reste la simulation Python.

---

## 2. Architecture — Agent Monde Générique

### Principe central

Un **unique agent monde générique** est responsable de toutes les entités IA. Il ne tourne **pas** à chaque tick — il est appelé dans deux cas :

```
┌─────────────────────────────────────────────────────┐
│  Simulation tick (Python pur — tourne toujours)     │
└────────────────┬────────────────────────────────────┘
                 │
         Deux déclencheurs
                 │
       ┌─────────┴──────────┐
       │                    │
  Périodique            Sur événement
  (tous les N ticks)    (action joueur impactante)
       │                    │
       └─────────┬──────────┘
                 │
     Agent Monde Générique
     "Regarde tous les États + Corps IA
      → fait prendre des décisions
        dans leur intérêt"
                 │
      Pour chaque entité concernée :
      → lit son contexte (AgentMemory + état sim)
      → génère des actions
      → les soumet aux endpoints normaux
```

### Déclencheurs détaillés

**Périodique** : tous les `WORLD_AGENT_TICK_INTERVAL` ticks, l'agent scanne **tous** les États et corporations IA actifs et prend des décisions dans leur intérêt.

**Sur événement joueur** : quand un joueur effectue une action qui impacte une entité IA, l'agent est appelé **spécifiquement** pour cette entité :

| Action joueur | Entité réveillée | Exemple de réponse |
|---|---|---|
| Claim une tuile près d'un État | Cet État | L'État évalue la menace, propose ou rompt un contrat |
| Demande d'implantation d'usine | L'État hôte | L'État négocie les conditions, accepte/refuse |
| Propose un contrat | L'entité cible | L'entité évalue et répond (accepte/contre-propose/refuse) |
| Colonise une tuile limitrophe | États voisins | Réaction diplomatique selon profil |

**Sur événement corpo IA** : si une corporation est assignée à un agent, les mêmes déclencheurs s'appliquent (événement interne : stock critique, tuile perdue, route commerciale coupée).

---

## 3. Ce que peut faire l'agent aujourd'hui (Phase 8.5)

Pour un **État IA** :
- Lire : territoire, marchés, contrats actifs, relations corps, événements récents
- Décider : nationaliser / gracier une corpo, signer/rompre un contrat, modifier le `taxRate`
- Stocker : `AgentMemory` (profil, historique décisions, mémoire relationnelle)
- Fréquence : tous les `AGENT_TICK_INTERVAL` ticks (défini dans `runtime.py`)

L'implémentation Phase 8.5 est un agent **par entité**. La Phase 11 migre vers l'agent monde générique centralisé.

### Transition Phase 8.5 → Phase 11

| Aspect | Phase 8.5 (actuel) | Phase 11 (cible) |
|---|---|---|
| Entité | Un agent par État | Un agent monde pour tous |
| Déclencheur | `AGENT_TICK_INTERVAL` fixe | Périodique + sur événement |
| Scope | État seulement | États + Corps IA |
| Appel sur action joueur | ❌ Non | ✅ Oui |

---

## 4. Ce qu'on veut construire — feature list discussion

### 4.1 Corporations IA (Phase 11)

Features confirmées :
- FSM gère les décisions routinières tick-by-tick (claim, construire, trader)
- L'agent monde est appelé pour cette corpo sur : événement majeur, stock critique, action joueur impactante, seuil FSM franchi
- L'agent peut **modifier les seuils FSM** (ex : "devenir plus agressif si les prix du fer montent")
- L'agent peut **réordonner la TerritoryQueue** (changer de priorité de construction)
- L'agent peut **signer ou proposer des contrats** avec d'autres entités
- L'agent peut **déclarer une guerre économique** (cibler les tuiles d'une autre corpo)

Features en discussion :
- [ ] **Bluff contractuel** : une corpo IA peut proposer un contrat délibérément défavorable pour attirer puis ruiner un rival
- [ ] **Coalition** : deux corps IA négocient via LLM pour coordonner une prise de marché commune
- [ ] **Mémoire adversariale** : l'agent mémorise les comportements des autres corpos (joueurs inclus) et adapte sa stratégie
- [ ] **Réponse aux messages joueur** : un joueur peut envoyer un message textuel à une corpo IA → le LLM répond in-game (diplomatie textuelle)

### 4.2 Agent Monde comme Game Master narratif

L'agent monde, dans son cycle périodique, évalue le **déséquilibre global de la partie** et peut injecter des éléments narratifs dans la simulation pour maintenir la tension et inciter à la coopération.

**Principe fondamental :** le GM ne punit pas le joueur en avance — il **enrichit le monde** pour le challenger et créer des opportunités pour les autres.

#### Détection du déséquilibre

L'agent lit le leaderboard (`get_scoreboard()`) et détecte des patterns :
- Un joueur a un score 2× supérieur au suivant
- Un joueur monopolise un système entier via corruption d'États vassaux
- Un joueur colonise un nouveau système sans opposition

#### Injection narrative — les 3 leviers du GM

**Levier 1 — Présence alien hostile**
- Le GM génère une **population alien hostile aux humains** sur une planète du système cible
- Conséquence : impossible de coloniser seul, les tuiles résistent, la corpo dominante doit demander de l'aide aux autres
- Mécanisme : `EventType.ALIEN_CONTACT` → new `StateData` de type alien avec `toleranceThreshold` bas

**Levier 2 — Mégastructure / Signal mystérieux**
- Le GM fait apparaître un **anneau-monde en orbite** ou une **balise alien** sur une planète du système
- Conséquence : événement narratif (message indéchiffrable), bonus énorme si décodé → incite à la coopération inter-corpo pour les `ResearchPoints`
- Mécanisme : `EventType.DISCOVERY` → structure spéciale sur une tuile, `knowledgeBonus` massif sur contrat de coopération

**Levier 3 — Empire galactique hostile**
- Le GM révèle que le système cible est sous la **sphère d'influence d'un empire galactique**
- Conséquence : toutes les corporations humaines ont intérêt à s'allier — la menace dépasse les rivalités locales
- Mécanisme : création d'un `StateData` alien à grande échelle, envoi d'`EventData` à toutes les corpos

#### Exemples concrets

**Scénario de référence** : un joueur a corrompu son État vassal pour fermer le marché aux autres corps et s'avance vers Proxima du Centaure.

```
GM détecte :
  score_joueur = 4800
  score_2e     = 1200   → ratio = 4×  (seuil = 2.5×)
  
GM choisit : Levier 1 (population hostile)
  → planète Proxima Centauri b : génération d'une pop alien hostile
  → EventData envoyé à toutes les corps :
    "Des signaux de vie hostiles détectés sur Proxima b.
     Une force unique ne suffira pas."
  → La corpo dominante ne peut pas coloniser seule
  → Les autres corpos reçoivent un contrat GM : aide militaire / logistique = bonus réputation
```

#### Ce que le GM NE fait PAS
- ❌ Détruire les bâtiments du joueur en avance
- ❌ Baisser artificiellement ses ressources
- ❌ Bloquer ses actions légitimes
- ✅ Ajouter de nouveaux acteurs, nouvelles contraintes, nouvelles opportunités

#### Interface technique
- L'agent lit : `get_scoreboard()`, `get_world_state()`, `list_game_events()`
- L'agent écrit via : `POST /game/events` (injection d'événement), `POST /game/corporations` (créer une entité alien), `POST /game/corporations/{id}/claim-hex` (établir présence alien sur des tuiles)
- Tout passe par les **endpoints normaux** — le GM joue avec les mêmes règles que les autres

#### Points de design ouverts sur le GM
- [ ] Seuil de déséquilibre exact qui déclenche le GM (ratio leaderboard ? delta territorial ?)
- [ ] Fréquence max d'injection (1 événement GM par N ticks pour éviter le spam)
- [ ] Le joueur sait-il que c'est le GM qui a généré l'événement, ou est-ce opaque ?
- [ ] Les entités alien créées par le GM persistent-elles indéfiniment ou ont-elles une durée de vie ?

#### Fine-tuning futur du modèle GM narratif

Le GM génère des messages narratifs envoyés aux corporations (ex : *"Des signaux de vie hostiles détectés sur Proxima b..."*). Un modèle de base tend vers des narrations génériques ou incohérentes avec l'univers Terraformation.

Un **LoRA** entraîné sur ~200-500 exemples `(état_monde_json → message_narratif)` apporterait :
- Le registre spatial / colonisation propre à l'univers du jeu
- La retenue du GM (jamais accusateur, toujours une opportunité)
- La cohérence des noms propres (planètes, corporations, événements)

Pipeline envisagé :
1. **Dataset** — générer ~150 exemples via GPT-4o/Claude sur les 3 leviers × 50 scénarios, corriger ~20% à la main. Peut être construit naturellement pendant le dev de la Phase 11.3.
2. **Base model** — `Qwen3-8B` ou `xLAM-2-8b-fc-r` (déjà dans la pipeline benchmark LLM)
3. **LoRA** via `unsloth` (gratuit, optimisé consumer GPU) — ~1-2h sur RTX 3090
4. **Export GGUF** → llama-swap comme n'importe quel autre modèle

> ⏳ À faire après stabilisation de la Phase 11.3 et accumulation de données de jeu réelles.

### 4.3 Corporation joueur assistée (Copilot in-game)

Un LLM qui aide **le joueur humain** à gérer sa corpo :

Features en discussion :
- [ ] **Conseiller** : "Tes stocks de Food baissent, tu devrais construire une Farm sur la tuile (q=3, r=-1)"
- [ ] **Résumé de tick** : résume ce qui s'est passé pendant la déconnexion du joueur
- [ ] **Alertes contextuelles** : "Une corpo adverse a claimé une tuile limitrophe à ta zone minière"
- [ ] **Négociation déléguée** : le joueur fixe des paramètres (prix minimum, ressources acceptées) et le LLM négocie les contrats à sa place

Contrainte importante : le joueur garde toujours le **dernier mot** — le LLM conseille ou prépare, il n'exécute pas sans confirmation.

---

## 5. Interface joueur avec les entités LLM

### Communication directe joueur ↔ entité IA

Question ouverte : veut-on un **chat in-game** avec les entités IA ?

Proposition :
- Chaque entité IA (État ou corpo) a une **boîte de messages**
- Le joueur peut envoyer un message texte libre : "Je veux négocier un accès à ton marché alimentaire"
- L'entité IA répond via LLM en restant dans son profil de personnalité
- Les messages peuvent **débloquer des actions** : contrat proposé, trêve, information partagée

Risques :
- Coût en tokens si trop de messages
- Cohérence narrative (l'IA doit rester dans son profil même sous pression du joueur)

Décision à prendre : **oui / non / Phase 12+**

---

## 6. Profils d'entités LLM

### États
| Type d'État | Comportement LLM attendu |
|---|---|
| Capitaliste | Favorise les contrats, tolère les corpos étrangères, optimise les revenus fiscaux |
| Nationaliste | Protège les ressources stratégiques, nationalise rapidement les corpos "dommageables" |

### Corporations IA
| Profil | Comportement FSM | Déclencheurs LLM |
|---|---|---|
| Expansionniste | Claim agressif de tuiles | Réordonner file si rivale s'approche, coalition temporaire |
| Économiste | Optimise production/marché | Signer contrats longue durée, réagir aux fluctuations |
| Militariste/Saboteur | Cible les infrastructures adverses | Déclarer guerre éco, bluff contractuel, mémoire adversariale |

---

## 7. Mémoire LLM — types et persistance

| Type | Contenu | Durée |
|---|---|---|
| **Profil** | Personnalité, valeurs, stratégie globale | Permanent (fixé à la création) |
| **Événementielle** | Décisions récentes, contrats en cours, crises traversées | Rolling window (N derniers ticks) |
| **Relationnelle** | Corps connues, niveau de confiance, trahisons passées | Permanent, mis à jour |
| **Tactique** | État FSM actuel, seuils en vigueur | Tick courant |

Question ouverte : la mémoire relationnelle doit-elle être **partagée** entre entités IA ? (ex : si la corpo A trahit la corpo B, la corpo C est-elle informée ?)

---

## 8. Contraintes techniques & garde-fous

- Le LLM **ne peut pas** contourner les règles de la simulation (ex : claim une tuile occupée, créer des ressources ex nihilo)
- Toutes les actions LLM passent par les **mêmes endpoints REST** que les joueurs — pas d'API privilegiée
- Si le LLM génère une action invalide → rejetée silencieusement, mémorisée comme "tentative échouée"
- **Timeout** : si le LLM ne répond pas en N secondes → FSM reprend le contrôle (pas de blocage de tick)
- **Budget tokens** : chaque agent a un budget par intervalle — évite les appels infinis

---

## 9. Points de design ouverts

| Question | Options | Décision |
|---|---|---|
| Chat joueur ↔ IA | Oui / Non / Phase 12+ | ❓ |
| Agent Maître de Jeu | Intégré à l'agent monde générique — injection narrative (alien, mégastructure, empire) | ✅ |
| Seuil GM | Ratio leaderboard exact qui déclenche l'injection narrative | ❓ |
| Opacité GM | Le joueur sait-il que l'événement vient du GM ? | ❓ |
| Durée entités alien GM | Persistantes / durée limitée / jusqu'à résolution scénario | ❓ |
| Mémoire relationnelle partagée | Oui (réseau d'info) / Non (silos) | ❓ |
| Copilot joueur | Conseiller seulement / Exécution déléguée | ❓ |
| Nombre d'agents simultanés | 2-4 corps + États IA = 6-8 agents max ? | ❓ |
| LLM local vs API externe | Local (Ollama/LM Studio) / API (OpenAI/Mistral) | 🔄 Local en priorité |
