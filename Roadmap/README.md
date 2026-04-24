# Roadmap Service — Terraformation

Micro-service FastAPI + FastMCP qui gère le backlog du projet en base SQLite.  
Il est la **source de vérité d'état** des phases (pas `ROADMAP.md` ni `roadmap.json`).

---

## Architecture

```
Roadmap/
├── app/
│   ├── server.py     # FastAPI + FastMCP — endpoints REST et outils MCP
│   ├── db.py         # SQLite CRUD — table phases (stdlib sqlite3)
│   └── models.py     # Pydantic — PhaseRecord, CompletionResult, SeedPayload
├── docker-compose.yml
├── Dockerfile        # python:3.12-slim, expose :8001
└── requirements.txt
```

**Ports**

| Service | URL |
|---------|-----|
| REST API | `http://localhost:8001` |
| MCP (FastMCP streamable-http) | `http://localhost:8001/mcp` |

**Volumes Docker**

| Volume | Usage |
|--------|-------|
| `roadmap_db` | SQLite persistant `/data/roadmap.db` — survit aux rebuilds |
| `..:/workspace:ro` | Repo Terraformation monté en lecture seule (pour accès aux tests) |

---

## Démarrage

```powershell
# Premier démarrage ou après rebuild
cd e:\terraformation\Roadmap
docker compose up -d

# Vérifier
Invoke-RestMethod http://localhost:8001/health
# → {"status":"ok","service":"terraformation-roadmap"}
```

### Seed initial (une seule fois par DB vierge)

```powershell
cd e:\terraformation
.\Tools\Set-PhaseComplete.ps1 -SeedFirst
# → Inserted : 31  Skipped : 0  Total : 31
```

### Mettre à jour les métadonnées (après modif de roadmap.json)

```powershell
.\Tools\Set-PhaseComplete.ps1 -SeedUpdate
# → préserve status + completed_date, met à jour tests/filter/etc.
```

---

## Endpoints REST

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/health` | Sanity check |
| `GET` | `/phases?status=pending` | Liste les phases (filtre optionnel : `done`, `pending`, `not-started`) |
| `GET` | `/phases/{id}` | Détail d'une phase |
| `POST` | `/phases` | Créer une nouvelle phase |
| `POST` | `/phases/{id}/complete?force=false` | Valider et cocher une phase |
| `GET` | `/audit` | **Toutes les phases non-done avec tests à lancer** — point d'entrée agent |
| `POST` | `/seed?update=false` | Import bulk depuis `roadmap.json`. Avec `?update=true` : refresh metadata sans écraser status |
| `DELETE` | `/phases/{id}` | Supprimer une phase |

---

## Outils MCP (`roadmap_*`)

Accessibles via `http://localhost:8001/mcp` — utilisables directement par l'agent Copilot.

| Tool | Description |
|------|-------------|
| `roadmap_summary()` | Comptage par statut (done/pending/not-started) |
| `roadmap_audit()` | **Point d'entrée agent** — toutes les phases à valider avec `tests_to_run` et `exit_criteria` |
| `roadmap_list_phases(status_filter?)` | Liste détaillée avec exit_criteria et notes |
| `roadmap_get_phase(phase_id)` | Détail complet d'une phase |
| `roadmap_add_phase(...)` | Ajouter une phase au backlog |
| `roadmap_complete_phase(phase_id, force?)` | Valider une phase — retourne le statut de validation |
| `roadmap_seed(phases_json)` | Import bulk (même format que `roadmap.json`) |

---

## Cycle de vie d'une phase — complétion

### Cas 1 — Phase avec tests (`tests` renseigné dans `roadmap.json`)

```
POST /phases/{id}/complete?force=false
→ HTTP 200  status="needs_validation"
            test_files=["test_phaseXX_foo.py"]
            message="Lance ces tests puis re-appelle avec -Force"
```

**L'agent doit lancer les tests lui-même** (le service ne les exécute pas) :

```powershell
cd e:\terraformation
pytest SimulationCore/tests/test_phaseXX_foo.py
```

Si les tests passent → re-appeler avec `-Force` :

```powershell
.\Tools\Set-PhaseComplete.ps1 -PhaseId pXX-foo -Force
→ POST /complete?force=true → status="ok" + ROADMAP.md coché
```

### Cas 2 — Phase visuelle (pas de tests, `notes` contient "visuelle")

```
POST /phases/{id}/complete?force=false
→ HTTP 200  status="needs_confirmation"
            message="Visual validation required — re-call with force=true"
```

Valider en Play Mode Unity, puis :

```powershell
.\Tools\Set-PhaseComplete.ps1 -PhaseId pXX-foo -Force
```

### Cas 3 — Phase `validation_filter` seul (legacy, sans `tests` explicite)

Le service lance pytest en interne avec `-k <filter>`.  
HTTP 422 si les tests échouent (output pytest inclus dans la réponse).

---

## Script CLI — `Tools/Set-PhaseComplete.ps1`

```powershell
# Lister les phases actives
.\Tools\Set-PhaseComplete.ps1 -List

# Valider une phase (flux complet avec prompt si tests/visuel)
.\Tools\Set-PhaseComplete.ps1 -PhaseId <id>

# Forcer sans confirmation (mode agent)
.\Tools\Set-PhaseComplete.ps1 -PhaseId <id> -Force

# Seed initial
.\Tools\Set-PhaseComplete.ps1 -SeedFirst

# Refresh metadata après modif roadmap.json
.\Tools\Set-PhaseComplete.ps1 -SeedUpdate
```

Le script :
1. Appelle `POST /phases/{id}/complete`
2. Si `needs_validation` → affiche les fichiers de tests à lancer, demande confirmation
3. Si `needs_confirmation` → demande validation visuelle Unity Play Mode
4. Une fois confirmé → `POST /complete?force=true`
5. Met à jour `ROADMAP.md` : `[ ]` → `[x]` via `roadmapAnchor`

---

## Skill associé

Le skill `roadmap-phase-complete` (`.github/skills/roadmap-phase-complete/SKILL.md`) documente le protocole complet pour l'agent Copilot :

- Étape 1 : `.\Tools\Set-PhaseComplete.ps1 -List` → identifier les phases actives
- Étape 2 : Valider selon le type (tests / visuel / legacy filter)
- Étape 3 : Compléter via le script ou MCP
- Étape 4 : Archiver dans `CHANGELOG.md` si toute la phase parente est terminée

---

## Source de données — `Documentation/roadmap.json`

Fichier seed canonique (format `SeedPayload`). Champs clés par phase :

```jsonc
{
  "id": "p73-market",           // identifiant unique
  "name": "Phase 7.3 — ...",
  "status": "done",             // not-started | pending | done
  "tests": ["test_phase73_market.py"],  // fichiers à lancer par l'agent
  "validationFilter": "phase73",        // filtre -k legacy (si tests vide)
  "exitCriteria": "...",        // critère de sortie lisible
  "roadmapAnchor": "...",       // texte à cocher dans ROADMAP.md
  "notes": "..."                // info supplémentaire (ex: "visuelle")
}
```

**Règle** : ne jamais éditer `[ ]` → `[x]` dans `ROADMAP.md` à la main — toujours passer par `Set-PhaseComplete.ps1`.
