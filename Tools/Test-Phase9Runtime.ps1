#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test-Phase9Runtime.ps1
    
.DESCRIPTION
    Lance les tests unitaires Phase 9.2 (runtime expeditions & trade routes).
    
.NOTES
    Independant de Docker — utilise uniquement le venv local.
    Aucun serveur requis. Duree attendue : < 5 secondes.
    
.PARAMETER VenvPath
    Chemin vers le venv Python. Defaut : e:\terraformation\.venv
    
.EXAMPLE
    .\Tools\Test-Phase9Runtime.ps1
#>
param(
    [string]$VenvPath = "e:\terraformation\.venv"
)

$python = Join-Path $VenvPath "Scripts\python.exe"
$testFile = Join-Path $PSScriptRoot "..\SimulationCore\tests\test_phase9_runtime.py"

Write-Host "=== Test-Phase9Runtime ===" -ForegroundColor Cyan
Write-Host "Python  : $python" -ForegroundColor Gray
Write-Host "Test    : $testFile" -ForegroundColor Gray
Write-Host ""
Write-Host "=== Tests Phase 9.2 - runtime expeditions & trade routes ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $python)) {
    Write-Error "Python non trouve : $python"
    exit 1
}

if (-not (Test-Path $testFile)) {
    Write-Error "Fichier test non trouve : $testFile"
    exit 1
}

# Lance les tests
& $python $testFile

# Verifie le code de sortie
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "OK - Tous les tests Phase 9.2 reussis." -ForegroundColor Green
    exit 0
} else {
    Write-Host ""
    Write-Host "ECHEC - des tests ont echoue." -ForegroundColor Red
    exit 1
}
