<#
.SYNOPSIS
    Synchronise .github\skills → .cline\skills (source de vérité = .github\skills)

.DESCRIPTION
    Copie tous les SKILL.md de .github\skills\*\SKILL.md vers .cline\skills\*\SKILL.md.
    Crée les dossiers manquants. Ne supprime pas les skills qui n'existent plus côté .github.

.EXAMPLE
    .\Tools\Sync-ClineSkills.ps1
    .\Tools\Sync-ClineSkills.ps1 -WhatIf
#>
param(
    [switch]$WhatIf
)

$root      = $PSScriptRoot | Split-Path -Parent
$srcBase   = Join-Path $root ".github\skills"
$dstBase   = Join-Path $root ".cline\skills"

if (-not (Test-Path $srcBase)) {
    Write-Error "Source introuvable : $srcBase"
    exit 1
}

$skills = Get-ChildItem -Path $srcBase -Filter "SKILL.md" -Recurse

if ($skills.Count -eq 0) {
    Write-Warning "Aucun SKILL.md trouvé dans $srcBase"
    exit 0
}

$copied  = 0
$skipped = 0

foreach ($src in $skills) {
    $relFolder = $src.DirectoryName.Substring($srcBase.Length).TrimStart('\','/')
    $dstDir    = Join-Path $dstBase $relFolder
    $dstFile   = Join-Path $dstDir "SKILL.md"

    $needsUpdate = $true
    if (Test-Path $dstFile) {
        $srcHash = (Get-FileHash $src.FullName -Algorithm MD5).Hash
        $dstHash = (Get-FileHash $dstFile      -Algorithm MD5).Hash
        if ($srcHash -eq $dstHash) {
            Write-Host "  [=] $relFolder  (inchangé)" -ForegroundColor DarkGray
            $skipped++
            $needsUpdate = $false
        }
    }

    if ($needsUpdate) {
        if ($WhatIf) {
            Write-Host "  [?] $relFolder  → serait copié" -ForegroundColor Cyan
        } else {
            if (-not (Test-Path $dstDir)) {
                New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
            }
            Copy-Item -Path $src.FullName -Destination $dstFile -Force

            # Copier aussi les sous-dossiers docs/, scripts/, templates/
            foreach ($subDir in @("docs", "scripts", "templates")) {
                $srcSub = Join-Path $src.DirectoryName $subDir
                $dstSub = Join-Path $dstDir $subDir
                if (Test-Path $srcSub) {
                    Copy-Item -Path $srcSub -Destination $dstSub -Recurse -Force
                }
            }

            Write-Host "  [+] $relFolder  → copié" -ForegroundColor Green
        }
        $copied++
    }
}

Write-Host ""
if ($WhatIf) {
    Write-Host "WhatIf : $copied skill(s) seraient mis à jour, $skipped déjà à jour." -ForegroundColor Cyan
} else {
    Write-Host "Sync terminé : $copied skill(s) mis à jour, $skipped déjà à jour." -ForegroundColor Green
}
