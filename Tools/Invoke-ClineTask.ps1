<#
.SYNOPSIS
    Lance une tâche Cline depuis clineTask/pending/ et la déplace dans done/ après exécution.

.PARAMETER TaskFile
    Chemin vers le fichier .md de la tâche (dans clineTask/pending/).

.PARAMETER Review
    Mode review : Cline demande confirmation avant chaque action (sans -y).
    Par défaut : YOLO mode (auto-approve tout).

.EXAMPLE
    .\Tools\Invoke-ClineTask.ps1 .\clineTask\pending\2026-04-29_fix-tileinspector.md
    .\Tools\Invoke-ClineTask.ps1 .\clineTask\pending\2026-04-29_fix-tileinspector.md -Review

.NOTES
    Cline CLI doit être installé : npm install -g cline
    Config LLM : cline auth -p openai -k dummy -b http://192.168.5.213:41200/v1 -m Gemma4-A4B-NoThink
    Cline cmd : C:\Users\wafhi\AppData\Roaming\npm\cline.cmd
#>
param(
    [Parameter(Mandatory)]
    [string]$TaskFile,

    [switch]$Review
)

$cline = "C:\Users\wafhi\AppData\Roaming\npm\cline.cmd"

if (-not (Test-Path $cline)) {
    Write-Error "Cline CLI introuvable : $cline — installer avec: npm install -g cline"
    exit 1
}

$resolved = Resolve-Path $TaskFile -ErrorAction SilentlyContinue
if (-not $resolved) {
    Write-Error "Fichier introuvable : $TaskFile"
    exit 1
}

$taskPath   = $resolved.Path
$taskName   = Split-Path $taskPath -Leaf
$doneDir    = Join-Path (Split-Path $taskPath -Parent | Split-Path -Parent) "done"
$donePath   = Join-Path $doneDir $taskName

# Lire le frontmatter pour override modèle si spécifié
$content  = Get-Content $taskPath -Raw
$modelOverride = $null
if ($content -match '(?m)^model:\s*(.+)$') {
    $modelOverride = $Matches[1].Trim()
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  Cline Task Runner" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  Tâche  : $taskName"
Write-Host "  Modèle : $($modelOverride ?? 'Gemma4-A4B-NoThink (défaut)')"
Write-Host "  Mode   : $($Review ? 'Review (confirmation manuelle)' : 'YOLO (auto-approve)')"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Changer de modèle si frontmatter le spécifie
if ($modelOverride) {
    & $cline auth -p openai -k "dummy" -b "http://192.168.5.213:41200/v1" -m $modelOverride 2>&1 | Out-Null
    Write-Host "  [~] Modèle switché → $modelOverride" -ForegroundColor Yellow
}

# Construire le prompt : contenu du fichier + instruction d'exécution
$prompt = @"
Execute the following task plan. Follow every instruction precisely.
Read all mentioned files before editing anything.
At the end, output a brief execution report (files modified, validation result).

$content
"@

# Lancer Cline
if ($Review) {
    # Mode interactif avec confirmation
    Write-Host "  Lancement en mode Review (Ctrl+C pour annuler)..." -ForegroundColor Yellow
    $prompt | & $cline "Execute the task plan provided via stdin"
} else {
    # YOLO : auto-approve tout
    Write-Host "  Lancement en mode YOLO..." -ForegroundColor Green
    $prompt | & $cline -y "Execute the task plan provided via stdin"
}

$exitCode = $LASTEXITCODE

# Déplacer dans done/ quelle que soit la sortie (l'historique Cline garde les détails)
if (-not (Test-Path $doneDir)) {
    New-Item -ItemType Directory -Path $doneDir -Force | Out-Null
}

# Renommer avec timestamp pour éviter les collisions
$timestamp   = Get-Date -Format "HHmm"
$doneNameTs  = $taskName -replace '\.md$', "_done-$timestamp.md"
$doneFinal   = Join-Path $doneDir $doneNameTs

Move-Item -Path $taskPath -Destination $doneFinal -Force

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "  [✓] Tâche terminée → $doneFinal" -ForegroundColor Green
} else {
    Write-Host "  [!] Cline a terminé avec code $exitCode → $doneFinal" -ForegroundColor Yellow
}
