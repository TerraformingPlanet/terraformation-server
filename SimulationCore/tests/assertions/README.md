# Assertion Scripts — Convention

Ce dossier contient **un script pytest par phase de roadmap**.  
Chaque script valide automatiquement les critères de sortie de sa phase.

## Convention de nommage

```
test_<phase_id>.py
```

Où `<phase_id>` est l'id de la phase avec les `-` remplacés par `_`.

| Phase id | Fichier |
|----------|---------|
| `p10-economy` | `test_p10_economy.py` |
| `p12-hud-p2` | `test_p12_hud_p2.py` |
| `p13-mirror` | `test_p13_mirror.py` |

## Lien avec le Roadmap Service

Le champ `assertion_script` de la phase pointe vers ce fichier (chemin relatif à la racine du workspace) :

```python
roadmap_add_phase(
    phase_id="p14-exemple",
    name="Phase 14 — Exemple",
    exit_criteria="...",
    assertion_script="SimulationCore/tests/assertions/test_p14_exemple.py",
)
```

## Lancer tous les scripts

```powershell
# Via REST (rapport complet)
Invoke-RestMethod http://localhost:8001/test | ConvertTo-Json -Depth 3

# Via MCP tool
roadmap_test_all()

# Directement avec pytest
pytest SimulationCore/tests/assertions/ --tb=short -v
```

## Lancer un script isolé

```powershell
pytest SimulationCore/tests/assertions/test_p10_economy.py --tb=short -v
```

## Règle pour les agents

**À chaque phase implémentée, l'agent DOIT :**
1. Créer `SimulationCore/tests/assertions/test_<phase_id_underscored>.py` (basé sur `_template.py`)
2. Appeler `roadmap_add_phase` ou mettre à jour la phase avec `assertion_script` pointant vers ce fichier
3. Vérifier que `roadmap_test_all()` retourne `passed` pour cette phase avant de la compléter
