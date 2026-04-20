<#
.SYNOPSIS
    Lance les tests unitaires Phase 9 (modeles routes commerciales & expeditions).
    Independant de Docker - utilise uniquement le venv local.

.DESCRIPTION
    Exécute SimulationCore/tests/test_phase9_models.py directement.
    Aucun serveur requis. Duree attendue : < 3 secondes.

.PARAMETER VenvPath
    Chemin vers le venv Python. Defaut : e:\terraformation\.venv

.EXAMPLE
    .\Tools\Test-Phase9Models.ps1
    .\Tools\Test-Phase9Models.ps1 -VenvPath "C:\mon\venv"
#>
param(
    [string]$VenvPath = "e:\terraformation\.venv"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rootDir  = "e:\terraformation"
$testFile = "$rootDir\SimulationCore\tests\test_phase9_models.py"
$python   = "$VenvPath\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Python non trouve : $python"
    exit 1
}
if (-not (Test-Path $testFile)) {
    Write-Error "Fichier test non trouve : $testFile"
    exit 1
}

Write-Host ""
Write-Host "=== Test-Phase9Models ===" -ForegroundColor Cyan
Write-Host "Python  : $python"
Write-Host "Test    : $testFile"
Write-Host ""

Push-Location $rootDir
try {
    & $python $testFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ECHEC - des tests ont echoue." -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    Write-Host "OK - Tous les tests Phase 9.1 reussis." -ForegroundColor Green
}
finally {
    Pop-Location
}
