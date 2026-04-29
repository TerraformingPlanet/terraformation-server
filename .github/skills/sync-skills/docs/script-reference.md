# Sync-ClineSkills — Référence complète

## Script
`Tools/Sync-ClineSkills.ps1`

## Principe
```
.github\skills\   ←  SOURCE DE VÉRITÉ  (éditer ici)
      ↓
.cline\skills\    ←  Consommé par Cline (ne pas éditer directement)
```

## Usage

### Sync normal
```powershell
cd e:\terraformation
.\Tools\Sync-ClineSkills.ps1
```

### Prévisualiser sans modifier
```powershell
.\Tools\Sync-ClineSkills.ps1 -WhatIf
```

## Sortie attendue

```
  [+] gamehud-ui       → copié       # fichier mis à jour
  [=] unity-mcp        (inchangé)    # hash identique, ignoré
Sync terminé : 1 skill(s) mis à jour, 12 déjà à jour.
```

## Comportement

| Cas | Résultat |
|-----|---------|
| Skill dans `.github` mais pas `.cline` | Créé (dossier + SKILL.md) |
| Skill dans `.github` modifié | Copié (hash MD5 différent) |
| Skill dans `.github` identique | Ignoré |
| Skill dans `.cline` mais pas `.github` | **Non supprimé** (manuel requis) |
| Sous-dossiers `docs/`, `scripts/` | **Non copiés** — voir ci-dessous |

## Copier aussi les docs/ et scripts/

Le script actuel (v1) copie seulement `SKILL.md`. Pour inclure les dossiers `docs/` :

```powershell
# Copier tout le contenu du skill (SKILL.md + docs/ + scripts/)
$srcSkillDir = Join-Path $srcBase $relFolder
$dstSkillDir = Join-Path $dstBase $relFolder
Copy-Item -Path $srcSkillDir -Destination (Join-Path $dstBase $relFolder) -Recurse -Force
```

Pour l'instant, copier manuellement les sous-dossiers après un ajout de `docs/` :
```powershell
Copy-Item -Path ".github\skills\gamehud-ui\docs" -Destination ".cline\skills\gamehud-ui\docs" -Recurse -Force
```

## Ajouter un nouveau skill

1. Créer `.github\skills\<nom>\SKILL.md`
2. Optionnel : créer `.github\skills\<nom>\docs\` avec les fichiers de référence
3. Lancer `.\Tools\Sync-ClineSkills.ps1`
4. Si des `docs/` ont été ajoutés, les copier manuellement (voir ci-dessus)

## Vérifier la cohérence

```powershell
# Lister tous les skills dans les deux emplacements
Get-ChildItem e:\terraformation\.github\skills -Directory | Select-Object Name
Get-ChildItem e:\terraformation\.cline\skills  -Directory | Select-Object Name
```
