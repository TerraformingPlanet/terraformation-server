# Workflow — Exécution d'un plan Copilot

Ce workflow s'utilise quand Copilot (Sonnet) a produit un plan structuré à exécuter.

## Modèle recommandé par type de tâche

| Tâche | Modèle | Pourquoi |
|-------|--------|----------|
| Écriture de code (Python, C#, USS) | `Gemma4-A4B-NoThink` | Rapide, précis, 26B |
| Refacto ou tâche multi-fichiers complexe | `qwen3.5-sonnet-30b` | Raisonnement long, 30B |
| Simple (renommage, fix typo, ajout champ) | `Gemma4-A4B-NoThink` | Latence minimale |

Change le modèle dans le sélecteur Cline **avant** de démarrer.

---

## Étapes

### 1. Reçois le plan

Le plan de Copilot contient :
- `## Contexte` — fichiers impliqués, état actuel
- `## Objectif` — ce qui doit être produit
- `## Tâches` — liste ordonnée, une tâche = un fichier ou une action atomique
- `## Contraintes` — règles à respecter (tokens USS, pas de logique en C#, etc.)
- `## Validation` — comment vérifier que c'est bon

### 2. Lis les fichiers mentionnés avant d'écrire

Pour chaque fichier listé dans `## Contexte` :
- Lis-le intégralement si < 300 lignes
- Lis les sections pertinentes si > 300 lignes
- Ne modifie jamais un fichier que tu n'as pas lu

### 3. Exécute tâche par tâche

- Une tâche à la fois
- Après chaque tâche : vérifie avec les critères de `## Validation`
- Si une tâche bloque → arrête et signale le problème sans inventer de solution

### 4. Respecte les contraintes du projet

- **Python** : venv `e:\terraformation\.venv` (jamais `.venv-1`)
- **USS/CSS** : toujours `var(--token-name)`, jamais de valeur hardcodée
- **C#** : `FindAnyObjectByType<T>()`, pas de logique gameplay, PascalCase
- **Contrats partagés** : modifier `models.py` → synchroniser `SimulationContracts.cs`

### 5. Rapport final

À la fin, produis un résumé :
```
## Rapport d'exécution
- Tâches complétées : X/Y
- Fichiers modifiés : [liste]
- Tests à lancer : [commande si applicable]
- Points en suspens : [si applicable]
```
