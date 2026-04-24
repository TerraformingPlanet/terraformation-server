# Conditions de Victoire — Questions de Clarification

> **Source design** : Description_du_jeu.md §20 — Conditions de Victoire
> 
> **État implémentation** : ✅ Scoreboard (Phase 7.5) | ❌ Victoire = ?

---

## Contexte design

### Quatre chemins de victoire

1. **Court terme — Classement**
   - Être #1 au scoreboard pendant X ticks consécutifs
   - Score = crédits + (nombre tuiles × valeur) + reputation bonus
   - Objectif pour session courte (quelques heures)

2. **Long terme — Terraformation globale**
   - Atteindre un score de terraformation **global de la planète**
   - Exemple : habitabilityScore moyen de la planète > 0.7 ET toutes zones couvertes
   - Corp qui passe ce seuil en PREMIÈRE gagne
   - Objectif pour campagne longue (semaines/mois)

3. **Coopératif — Planète habitable pour tous**
   - Tous les joueurs combinent leurs efforts
   - Planète devient habitable si habitabilityScore global > X (ex : 0.75)
   - **Tout le monde gagne ensemble** ou nul gagne
   - Bonus final partagé (tech rare, prestige inter-galactique)
   - Objectif pour mode friendly/PvE

4. **Fin alternative — Contrôle inter-étatique**
   - Créer/contrôler un **organisme inter-étatique** (marché global corruptible)
   - Celui qui le contrôle gagne influence maximale
   - Peut être corrompu par une corporation très riche
   - Objectif pour diplomatie et intrigue

---

## Questions à clarifier

### Q1 — Mode de partie (MVP)
- [ ] Quel est le MVP initial ? 
  - Juste le classement (#1) ?
  - Ou terraform global aussi ?
  - Coopératif et inter-étatique différés ?

### Q2 — Classement (Court terme)
- [ ] Formule du score :
  - `score = crédits + (claimedTiles × 100) + (reputation × 50)` ?
  - Ou autre pondération ?
- [ ] Être #1 quelques ticks suffit-il ou minimum X ticks consécutifs (ex : 10 ticks = 10 jours) ?

### Q3 — Terraformation globale (Long terme)
- [ ] Définition de « score de terraformation planète » :
  - Moyenne de tous les `habitabilityScore` de toutes les tuiles ?
  - Seuil à atteindre : 0.7 ? 0.75 ? Configurable par partie ?
- [ ] Toutes les tuiles doivent être exploitées ou juste "couvertes" (une expédition suffit) ?
- [ ] Après ce seuil : la partie se termine ?

### Q4 — Mode coopératif
- [ ] Comment bascule-t-on en mode coopératif ?
  - Option au démarrage de partie ?
  - Vote des joueurs connectés ?
  - Permanent une fois activé ou changeable en jeu ?
- [ ] Score global = moyenne habitabilityScore de tout le monde combiné ou somme ?
- [ ] Bonus final : quoi exactement ? (tech débloquée, crédits bonus, titre cosmique ?)

### Q5 — Organisme inter-étatique
- [ ] Créé comment ?
  - Événement (Convention inter-étatique, Phase 17) ?
  - Ou action directe : corporation vote pour l'établir, État gouverne ?
- [ ] Contrôle = avoir le plus de crédits ou autre ? Comment le perd-on ?
- [ ] Corrompre : une corpo riche peut-elle y injecter X crédits pour contrôler ?

### Q6 — Fin de partie
- [ ] Quand la victoire est atteinte :
  - La partie se termine immédiatement ou continuer possible ?
  - Stats sauvegardées ? Replay stats détaillés ?
  - Nouvelle partie ou serveur persiste ?

### Q7 — Défaite
- [ ] Peut-on perdre ?
  - Être éjecté si score < minimum X ticks (ex : -∞) ?
  - Perdre toutes les tuiles → exclusion ?
  - Faillite (crédits < 0) → fin corp possible ?

---

## Réponses

✅ **DÉCISION : Simulation sans fin + Leaderboard persistant**

### Vision du user
- **Pas de condition de "victoire"** au sens traditionnel (pas de "fin" de partie)
- **Simulation continue** : le monde tourne indéfiniment
- **Leaderboard persistant** : affiche les meilleures corporations/États en temps réel
  - Classement par : crédits, territoires, réputation, score terraformation
  - Mis à jour chaque tick
  - Visible à tout moment (HUD principal)

### Réponses aux questions

#### Q1 — Mode de partie (MVP)
**✅ MVP = Leaderboard simple**
- Juste afficher un **scoreboard global** avec top N corporations (ex : top 10)
- Pas de condition d'arrêt
- Pas de "modes" (coopératif, long-terme…) — juste une bourse en direct
- Terraform global, conditions victoire, inter-étatique → **différés Phase 12+ (polish)**

#### Q2 — Classement (Court terme)
**✅ Formule du score (actuelle Phase 7.5)**
- `score = crédits + (claimedTiles × 100) + (globalReputation × 50)`
- **Top fluctue chaque tick** → dynamique continue
- Pas de seuil "X ticks consécutifs" — c'est live

#### Q3 — Terraformation globale (Long terme)
**⏸️ Différé Phase 12+** — pas de priorité immédiate
- Concept = bon, mais implémentation complexe
- MVP : juste leaderboard crédits/territoire suffit

#### Q4 — Mode coopératif
**⏸️ Différé Phase 12+** — pas de priorité immédiate

#### Q5 — Organisme inter-étatique
**⏸️ Différé Phase 12+** — concepts intéressant mais trop tard pour MVP

#### Q6 — Fin de partie
**✅ Pas de fin**
- Simulation tourne indéfiniment
- Joueur peut quitter/se reconnecter (monde persiste)
- Stats sauvegardées automatiquement (PostgreSQL)

#### Q7 — Défaite
**✅ Pas de défaite absolue — faillite possible mais pas éjection**
- Corp peut faire faillite (`crédits < 0`) → devient inactive (bot peut rester ou être éjectée)
- Perdre toutes les tuiles ne signifie pas fin (peut relancer expansion)
- Personne n'est "éjectée" du serveur — juste au bas du leaderboard

---

---

## Dynamique joueurs — Relations libres

✅ **Les joueurs ne sont PAS forcément ennemis**

### Liberté de relations
- **Adversaires** : compétition directe pour crédits/territoires, sabotage, blocs commerciaux
- **Partenaires** : alliances, joint-ventures, partage de routes commerciales, aides mutuelles
- **Neutres** : coexistent sans interaction

### Implémentations possibles (Phase 7.5+)
- Relations bilatérales : `CorporationData.relations: dict[corp_id → relation_level]` (hostile/neutral/allied)
- Contrats partenariats (Phase 7.4+) : deux corpos partagent revenus d'une route
- Diplomatie : demande d'alliance (visuelle UI, pas de gameplay dur)
- IA corpos (Phase 11) : peuvent choisir alliance ou sabotage selon profil

### Conséquence sur le leaderboard
- **Pas de mode coopératif forcé** — juste des relations émergentes
- Joueurs peuvent s'entraider et monter ensemble au classement
- Ou s'écraser mutuellement — liberté totale

---

## Implémentation pour MVP

### Leaderboard HUD (Phase 10)
- Affichage : top 10 corporations
- Colonnes : rang, nom, crédits, tuiles, réputation, score total
- Rafraîchi chaque tick
- Accessible depuis HUD principal (toggle panel)
- Optional : graphique courbe évolution (derniers 100 ticks)
- Badge optionnel : "Allied with X" ou "At war with Y"

### Données requises (déjà existantes)
- ✅ `CorporationData.credits`
- ✅ `_tile_ownership` count
- ✅ `CorporationData.globalReputation`
- ✅ `get_scoreboard()` dans `runtime.py` (Phase 7.5)
- ⏳ Relations bilatérales (structure TODO, Phase 7.5+)

### Pas besoin (MVP)
- ❌ Condition d'arrêt
- ❌ Détection faillite (ok si crédits < 0)
- ❌ Modes alternatifs
- ❌ Fin de partie
