---
name: roadmap-phase-complete
description: "Use when marking a roadmap task or phase as complete: checking a [ ] box in ROADMAP.md, validating exit criteria, updating roadmap.json, or moving a completed phase to CHANGELOG.md. Trigger words: marquer comme terminé, cocher, [ ] → [x], phase complete, compléter la phase, roadmap, Set-PhaseComplete, roadmap.json."
argument-hint: "Spécifier l'id de la phase (ex: 'p12-polish-ux') ou demander -List pour voir les pendants."
---

# Skill — Roadmap Phase Complete

## Architecture

Le Roadmap Service (`Roadmap/`) est une application FastAPI + FastMCP **locale**, port **8001**. Pas de Docker.

- **State store** : SQLite `Roadmap/roadmap.db` (local, persistant)
- **Launcher** : `e:\terraformation\.venv\Scripts\python.exe e:\terraformation\Roadmap\run.py`
- **Pytest gate** : le service lance pytest localement via subprocess (WORKSPACE_PATH auto-détecté)
- **MCP endpoint** : `http://localhost:8001/mcp` — tools préfixés `roadmap_*`
- **Seed** : `python Roadmap/migrate.py` depuis `Documentation/roadmap.json`

## Principe

**Ne jamais cocher `[ ]` → `[x]` dans ROADMAP.md directement.**
Toujours passer par ce protocole. La source de vérité machine est la DB SQLite locale.

---

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `Roadmap/app/server.py` | FastAPI + FastMCP — source de vérité runtime |
| `Roadmap/app/db.py` | SQLite CRUD — table `phases` |
| `Roadmap/run.py` | Lanceur local — `python run.py` |
| `Roadmap/migrate.py` | Seed/migration depuis `Documentation/roadmap.json` |
| `Documentation/roadmap.json` | Seed canonique — format source |
| `Documentation/ROADMAP.md` | Vue humaine — `[ ]` → `[x]` géré par `Set-PhaseComplete.ps1` |
| `Documentation/CHANGELOG.md` | Archive des phases terminées |
| `Tools/Set-PhaseComplete.ps1` | CLI gate — appelle le service REST, met à jour ROADMAP.md |

---

## Prérequis : démarrer le service

```powershell
# Démarrage local (no Docker)
e:\terraformation\.venv\Scripts\python.exe e:\terraformation\Roadmap\run.py

# Vérifier
Invoke-RestMethod http://localhost:8001/health  # → {"status":"ok"}
```

## Seed initial (une seule fois par DB vierge)

```powershell
# Importer toutes les phases depuis roadmap.json
e:\terraformation\.venv\Scripts\python.exe e:\terraformation\Roadmap\migrate.py

# Mettre à jour les métadonnées sans écraser les statuts
e:\terraformation\.venv\Scripts\python.exe e:\terraformation\Roadmap\migrate.py --update
```

---

## Protocole — workflow planificateur

### Étape 1 — Auditer le backlog

```python
# TOUJOURS commencer par l'audit
roadmap_audit()
```

Ou via PowerShell :
```powershell
.\Tools\Set-PhaseComplete.ps1 -List
```

Réponse type :
```json
{
  "total": 4, "with_tests": 2, "visual_only": 2,
  "phases": [
    { "id": "p13-mirror", "status": "not-started",
      "assertion_script": "SimulationCore/tests/test_p13.py",
      "tests_to_run": [],
      "exit_criteria": "..." },
    { "id": "p12-sound", "status": "pending",
      "assertion_script": null, "tests_to_run": [],
      "notes": "Validation subjective en Play Mode" }
  ]
}
```

### Étape 2 — Valider (selon cas)

**Cas A — phase avec `assertion_script`** (nouveau workflow recommandé) :
```python
result = roadmap_validate_phase("p13-mirror")
# result.status == "pass"  → appeler complete avec force=True
# result.status == "fail"  → corriger le code/script, relancer
```

**Cas B — phase avec `tests_to_run` non vide** (legacy reminder gate) :
```powershell
pytest SimulationCore/tests/test_phaseXX_foo.py
# Si PASS → compléter avec -Force
```

**Cas C — phase visuelle** (`assertion_script` null, `tests_to_run` vide) :
- Capturer screenshot Unity via MCP `Unity_Camera_Capture`
- Vérifier visuellement les critères de sortie
- Compléter avec `-Force`

**Cas D — `validation_filter` seul (legacy)** :
Le service lance pytest en interne. HTTP 422 si FAIL.

### Étape 3 — Compléter

```powershell
.\Tools\Set-PhaseComplete.ps1 -PhaseId "<id>"          # gate automatique
.\Tools\Set-PhaseComplete.ps1 -PhaseId "<id>" -Force   # après validation manuelle/visuelle
```

Via MCP :
```python
roadmap_complete_phase("<id>", force=True)   # après validation réussie (Cas A/B/C)
roadmap_complete_phase("<id>", force=False)  # laisse le service décider (lance assertion_script)
```

### Étape 4 — Archiver si phase entière terminée

```python
roadmap_summary()  # vérifier l'état global
```

Si tous les items d'une phase parente sont `done` :
1. Couper le bloc dans `ROADMAP.md`
2. Coller dans `Documentation/CHANGELOG.md` avec date
3. Mettre à jour la table récapitulative en bas de `ROADMAP.md`

---

## Ajouter une nouvelle phase au backlog (workflow planificateur)

```python
roadmap_add_phase(
    phase_id="p14-exemple",
    name="Phase 14 — Exemple",
    exit_criteria="Description du critère de sortie mesurable",
    assertion_script="SimulationCore/tests/test_p14_exemple.py",  # chemin relatif au workspace
    roadmap_anchor="Phase 14",
    notes=None
)
```

`assertion_script` = chemin pytest relatif à la racine du workspace (`e:\terraformation`).  
Convention : `SimulationCore/tests/assertions/test_<phase_id_underscored>.py`

| Phase id | Chemin assertion_script |
|----------|-------------------------|
| `p10-economy` | `SimulationCore/tests/assertions/test_p10_economy.py` |
| `p12-hud-p2` | `SimulationCore/tests/assertions/test_p12_hud_p2.py` |

Templaté dans : `SimulationCore/tests/assertions/_template.py`

Puis ajouter la section `[ ]` correspondante dans `ROADMAP.md`.

---

## Valider toutes les phases d'un coup

```python
# Vérifier la santé globale — rapport complet
roadmap_test_all()
```

Ou via REST :
```powershell
Invoke-RestMethod http://localhost:8001/test | ConvertTo-Json -Depth 3
```

Réponse type :
```json
{
  "total": 5, "passed": 3, "failed": 1, "no_script": 29, "errors": 0,
  "results": [
    {"phase_id": "p10-economy", "status": "pass", "output": "1 passed"},
    {"phase_id": "p11-contracts", "status": "fail", "output": "FAILED test_contract_lifecycle"}
  ]
}
```

---

## Règles strictes

- **BLOCAGE** : `complete` avec `assertion_script` retourne HTTP 422 si pytest échoue
- **Jamais** éditer `[ ]` → `[x]` dans ROADMAP.md à la main
- **Jamais** appeler `db.mark_complete()` directement — toujours passer par `/complete`
- **Toujours** appeler `roadmap_validate_phase` avant `roadmap_complete_phase` quand un `assertion_script` est configuré
- **Toujours** vérifier `exit_criteria` avant de déclencher la complétion
- Pour les phases sans script : validation visuelle obligatoire (screenshot ou `-Force` explicite)
- **Pas de Docker** — le service se lance avec `python run.py` depuis `Roadmap/`
- **À chaque phase implémentée**, l'agent DOIT :
  1. Créer `SimulationCore/tests/assertions/test_<phase_id_underscored>.py` (copier `_template.py`)
  2. Mettre à jour `assertion_script` de la phase via `roadmap_add_phase` ou `roadmap_update_phase`
  3. Vérifier que `roadmap_test_all()` retourne `passed` pour cette phase avant de la compléter
