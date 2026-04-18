# Roadmap — Terraformation & Colonisation Spatiale (Backlog Actif)

Chaque phase a une cible claire. **Ne pas passer à la suivante avant d'avoir atteint la cible.**

> Pour l'historique des phases complétées (Phase 0 → 6.9, Sprint 0), voir [CHANGELOG.md](CHANGELOG.md).

---

## En cours : Phase 6.75 — Split Simulation / Client / MCP

**Restant (1 tâche)** :
- [ ] Garder le bridge Unity uniquement pour le debug visuel et les artefacts de rendu — finaliser la migration des tools `get_view_state`, `get_projection_summary`, `get_local_summary`, `get_client_snapshot` vers le `DedicatedServer` ou les marquer définitivement comme "debug client uniquement"

**Cible**
> Le monde peut tourner sans la scène Unity, Unity peut afficher des snapshots serveur, et le MCP n'est plus un backend de fortune mais une couche d'outillage.

---

## En cours : Phase 6.5 — Relief & Hydrologie Locale

### Tâches restantes
- [ ] Étendre `MapRegion.ComputeCoherence()` et `CoherenceValidationSystem` avec rugosité, accumulation et signaux relief/hydrologie
- [ ] Ajouter un débordement de bassin avec exutoire dynamique
- [ ] Remplacer l'heuristique locale côte / océan par une logique de connectivité hydrologique plus robuste
- [ ] Vérifier en jeu les cas de référence : océan ouvert, côte, bassin, lac intérieur, désert drainant, pôle gelé

**Cible**
> Une région locale où l'eau suit le relief : les montagnes drainent, les cuvettes se remplissent, les côtes sont distinguées des lacs, et les pôles gelés restent cohérents avec la projection.

---

## Sprint A — Stabilisation Debug + Hydrologie Locale v2 (reste)

**Restant** :
- [ ] Vérifier en Play Mode les 5 cas de référence (océan ouvert, côte, bassin, désert drainant, pôle gelé)

**Critères de sortie restants** :
- [ ] Les bassins fermés, côtes et lacs sont lisibles visuellement dans les cas de test de base
- [ ] Les seuils hydrologiques ont une première passe de tuning documentée

**Fichiers** :
- `Game/Assets/Scripts/World/Systems/WaterSystem.cs`
- `Game/Assets/Scripts/World/Systems/WaterClassificationSystem.cs`

---

## Sprint B — Cohérence Macro → Micro + Projection Hydrologique

**Objectif**
> Améliorer la cohérence entre cellule projetée et région locale pour que la projection devienne un résumé hydrologique crédible du globe.

**Backlog** :
- [ ] Étendre `MapRegion.ComputeCoherence()` avec signaux de rugosité, accumulation et structure de relief
- [ ] Enrichir `CoherenceValidationSystem` pour utiliser ces signaux comme biais progressifs plutôt que des overrides trop binaires
- [ ] Ajouter une hydrologie simplifiée côté `PlanetaryHexGrid` pour améliorer océan/côte/aride/gel côté projection
- [ ] Rendre les zones côtières projetées plus robustes via une logique de connectivité ou de voisinage enrichi
- [ ] Vérifier que les presets debug (Ocean, Arid, Frozen, Basin, Coast) restent cohérents après enrichissement de la projection
- [ ] Mettre à jour le HUD/debug pour comparer clairement projection et local sur les nouveaux signaux si nécessaire

**Fichiers** :
- `Game/Assets/Scripts/World/MapRegion.cs`
- `Game/Assets/Scripts/World/GenerationContext.cs`
- `Game/Assets/Scripts/World/Systems/CoherenceValidationSystem.cs`
- `Game/Assets/Scripts/World/PlanetaryHexGrid.cs`
- `Game/Assets/Scripts/UI/ViewManager.cs`

**Critères de sortie** :
- [ ] Un clic sur une zone projetée humide/aride/gelée produit une région locale cohérente sans forçage excessif
- [ ] La projection distingue mieux océan, côte et zones continentales humides
- [ ] Les presets debug restent exploitables et n'introduisent pas de régression de navigation

---

## Sprint C — Persistance Régionale + Synchro Local → Projection

**Objectif**
> Faire survivre les modifications locales aux régénérations et préparer la transition vers un vrai gameplay de corporation.

**Backlog** :
- [ ] Introduire un cache runtime des modifications par région (deltas d'eau, température, état terraformé)
- [ ] Réappliquer ces deltas lors de `ReloadCurrentProjection`, `OpenRegion` et `RegenerateCurrentLocalRegion`
- [ ] Définir la granularité de remontée local → projection (moyenne, max, ou agrégation hydrologique)
- [ ] Implémenter une première synchro locale → projection pour les signaux essentiels
- [ ] Vérifier qu'une région modifiée puis rechargée conserve son état attendu
- [ ] Préparer les points d'entrée qui serviront au claim de territoire et aux bâtiments

**Fichiers** :
- `Game/Assets/Scripts/UI/ViewManager.cs`
- `Game/Assets/Scripts/World/PlanetSphereGoldberg.cs`
- `Game/Assets/Scripts/World/PlanetaryHexGrid.cs`
- `Game/Assets/Scripts/HexGrid/HexGrid.cs`
- `Game/Assets/Scripts/World/MapRegion.cs`

**Critères de sortie** :
- [ ] Une modification locale persiste après fermeture/réouverture de la région
- [ ] La projection reflète au moins partiellement l'état local modifié sur la zone concernée
- [ ] Le socle technique est prêt pour démarrer Phase 7

---

## Sprint D — AtmosphericState : progression terraformation mesurable (prérequis Phase 7)

**Objectif**
> Donner aux corporations un indicateur de progression de la terraformation calculé à l'échelle de la région entière.

**Contexte**
La terraformation doit être modélisée comme une évolution atmosphérique agrégée (CO₂, O₂, pression) avec des boucles de feedback. L'`AtmosphericState` est l'agrégation des `SimulationCellState` en un indicateur région/planète lisible par les corporations.

**Backlog** :
- [ ] Définir `AtmosphericState` (Pydantic + C#) : `co2Ratio`, `o2Ratio`, `atmosphericPressure`, `averageTemperature`, `toxinRatio`, `habitabilityScore`
- [ ] Ajouter `atmosphericState: AtmosphericState` à `RegionState` (Python + C#) — mettre à jour [SIMULATION_CONTRACTS.md](SIMULATION_CONTRACTS.md)
- [ ] `SimulationCore/logic.py` — fonction `compute_atmospheric_state(cells)`
- [ ] `DedicatedServer` — peupler `atmosphericState` dans `/commands/open-region`
- [ ] `SimulationContractFactory.cs` — peupler `atmosphericState` dans `TryBuildRegionState`
- [ ] `TerraformHUD.cs` — afficher O₂%, CO₂%, pression, score d'habitabilité
- [ ] `TerraformProgressTracker.cs` — utiliser `habitabilityScore` comme source du slider
- [ ] Ajouter tool MCP `get_atmospheric_state(latitude, longitude)`

**Fichiers** :
- `SimulationCore/terraformation_sim/models.py`
- `SimulationCore/terraformation_sim/logic.py`
- `DedicatedServer/app/server.py`
- `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs`
- `Game/Assets/Scripts/Simulation/Contracts/SimulationContractFactory.cs`
- `Game/Assets/Scripts/UI/TerraformHUD.cs`
- `Game/Assets/Scripts/World/TerraformProgressTracker.cs`
- `Mcp/server.py`

**Critères de sortie** :
- [ ] `GET /commands/open-region` retourne un champ `atmosphericState` non vide
- [ ] Le HUD affiche O₂%, pression et score d'habitabilité depuis les données serveur
- [ ] `get_atmospheric_state` répond sans Unity ouvert
- [ ] Le slider de progression est cohérent avec `habitabilityScore`

---

## Sprints MCP — Responsabilité GitHub Copilot

**GitHub Copilot est propriétaire du MCP et de l'API du jeu.**
Référence complète : [MCP_TOOLS_ARCHITECTURE.md](MCP_TOOLS_ARCHITECTURE.md)

### Sprint MCP-1 — Outils de cellule et validation (Sprint B → C)

**Backlog** :
- [ ] Endpoint `/debug/cell?q=&r=` → tool `get_cell_detail`
- [ ] Endpoint `/debug/hydrology` → tool `get_hydrology_stats`
- [ ] Endpoint `/debug/validate` → tool `run_validation`
- [ ] Exposer ces 3 tools dans `Mcp/server.py` + documenter dans `MCP_TOOLS_ARCHITECTURE.md`
- [ ] Valider les 3 tools en Play Mode via Copilot Chat

**Critères de sortie** :
- [ ] L'agent peut sélectionner un hex par coordonnées axiales et lire son état complet
- [ ] L'agent peut déclencher `run_validation` et obtenir la liste des incohérences sans ouvrir Unity

### Sprint MCP-2 — Boucle de test automatisée (Sprint C → Phase 7)

**Backlog** :
- [ ] Implémenter la séquence `launch_preset → get_local_summary → comparer checklist → get_console_errors → take_screenshot` pour chaque preset
- [ ] Archiver les résultats JSON par preset dans `Artifacts/<PresetName>/`
- [ ] Produire un rapport de delta entre deux runs (régression / amélioration)

**Critères de sortie** :
- [ ] Un seul appel déclenche la validation complète des 5 presets et produit un rapport lisible

### Sprint MCP-3 — API Gameplay (Phase 7 → 9)

**Backlog** :
- [ ] `/game/corporation` → `get_corporation_state`
- [ ] `/game/market` → `get_market_state`
- [ ] `/game/events` → `get_active_events`
- [ ] `/game/tick` → `get_tick_state`
- [ ] `/game/planet` → `get_planet_overview`
- [ ] Règle : les writes (claim, achat) passent par Mirror, jamais par cette API

---

## Ordre d'exécution conseillé

- [ ] Ne pas démarrer la Phase 7 avant la fin du Sprint C et du Sprint D
- [ ] Considérer la Phase 6.5 comme terminée seulement quand les critères de sortie des sprints A et B sont validés
- [ ] Utiliser le Sprint C comme sas de stabilisation avant `Corporation`, `Events` et `Economy`

---

## Phase 7 — Système de Corporation

**Prérequis** : Sprint C (persistance régionale) + Sprint D (AtmosphericState) terminés. Phase 6.9 (hiérarchie Cosmos) ✅

### Tâches restantes
- [ ] Créer `CorporationData` côté Python `SimulationCore` + contrat C# miroir
- [ ] Implémenter le claim d'un hex — route `POST /game/corporations/{id}/claim-hex` sur `DedicatedServer`
- [ ] Afficher les hexes possédés (bordure colorée par corpo) — couche ownership sur la grille Unity
- [ ] Implémenter la construction de bâtiments sur un hex (mine, serre, raffinerie, centrale)
- [ ] Modéliser la chaîne de valeur par type de bâtiment : extraction → raffinage → transport → vente
- [ ] Calculer la production automatique par tick côté `DedicatedServer`
- [ ] Afficher un HUD de base (solde, ressources, score) + barre atmosphérique
- [ ] Afficher un scoreboard avec toutes les corpos
- [ ] Exposer `GET /game/corporations` sur `DedicatedServer` pour le MCP

**Cible**
> Une corpo joueur qui claim des hexes, construit des mines, accumule des crédits et monte au classement. `habitabilityScore` est le KPI commun.

---

## Phase 8 — Système d'Événements

- [ ] `EventData` (ScriptableObject) : nom, description, effets, poids de probabilité
- [ ] Événements de base : RencontreAlienne, TempêteSolaire, DécouverteMinière, CriseÉconomique, SabotageCorpo
- [ ] `EventManager` : tirage pondéré à chaque tick serveur
- [ ] Popup UI de notification

**Cible** : événements qui modifient l'état de la partie en temps réel

---

## Phase 9 — Économie & Bourse Commune

- [ ] Ressources tradables : fer, O₂, eau, énergie, tech, nourriture
- [ ] `MarketManager` avec order book simplifié
- [ ] Fluctuation des prix (offre/demande par tick)
- [ ] UI de marché pour les corpos joueurs
- [ ] Corpos IA participantes au marché

**Cible** : bourse qui fluctue en temps réel selon les actions des joueurs et des IA

---

## Phase 10 — Multijoueur Réseau

- [ ] Intégrer Mirror Networking
- [ ] Serveur dédié autoritaire (client-serveur, pas P2P)
- [ ] Synchroniser hexes, corpos, marché entre clients
- [ ] Authentification joueur (Unity Authentication)
- [ ] Firebase Firestore pour la persistance monde
- [ ] Sauvegardes toutes les X minutes
- [ ] Test avec 2 joueurs simultanés

---

## Phase 11 — IA Corporations

- [ ] `BotCorporation` avec FSM
- [ ] 3 profils : Expansionniste, Économiste, Militariste/Saboteur
- [ ] Réaction aux événements et aux fluctuations de marché

---

## Phase 12 — Polish

- [ ] UI/UX complet : HUD, menus, tooltips
- [ ] Sound design
- [ ] Équilibrage économique (playtesting)
- [ ] Optimisation performances (profiler Unity)
- [ ] Distribution (itch.io ou autre)

---

## Récapitulatif

| Phase | Contenu | Statut |
|---|---|---|
| 0–6.9, Sprint 0 | Fondations, grille, génération, vues, terraformation, cosmos, split sim | ✅ Voir [CHANGELOG.md](CHANGELOG.md) |
| 6.75 | Isolation bridge Unity | 🔄 1 tâche restante |
| 6.5 + Sprints A→D | Hydrologie, cohérence, persistance, AtmosphericState | 🔄 En cours |
| MCP-1, 2, 3 | Outils cellule, tests auto, API gameplay | ⬜ À faire |
| 7 | Corporations | ⬜ À faire (attend Sprints C + D) |
| 8 | Événements | ⬜ À faire |
| 9 | Économie & Bourse | ⬜ À faire |
| 10 | Multijoueur Réseau | ⬜ À faire |
| 11 | IA Corporations | ⬜ À faire |
| 12 | Polish | ⬜ Continu |
