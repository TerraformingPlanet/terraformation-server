<#
.SYNOPSIS
    Gate de validation avant de cocher une phase dans roadmap.json + ROADMAP.md.
    Délègue la persistance et le lancement de tests au Roadmap Service (port 8001).

.DESCRIPTION
    1. Appelle GET /phases/{id} pour obtenir l etat courant
    2. Appelle POST /phases/{id}/complete[?force=true] — le service lance pytest + mark done
    3. Si status=needs_confirmation → demande confirmation visuelle, puis relance avec force=true
    4. Met a jour ROADMAP.md localement ([ ] → [x]) via roadmapAnchor retourne par le service

.PARAMETER PhaseId
    L id JSON de la phase a completer (ex: "p12-polish-ux").

.PARAMETER List
    Affiche les phases pending/not-started sans completer.

.PARAMETER Force
    Passe la confirmation manuelle (phases sans tests).

.PARAMETER ServiceUrl
    URL du Roadmap Service (defaut: http://localhost:8001).

.PARAMETER SeedFirst
    Import Documentation/roadmap.json dans le service si la DB est vide.
#>
param(
    [string]$PhaseId     = "",
    [switch]$List,
    [switch]$Force,
    [string]$ServiceUrl  = "http://localhost:8001",
    [switch]$SeedFirst,
    [switch]$SeedUpdate
)

$Root        = $PSScriptRoot | Split-Path -Parent
$RoadmapMd   = Join-Path $Root "Documentation\ROADMAP.md"
$RoadmapJson = Join-Path $Root "Documentation\roadmap.json"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Invoke-Api {
    param([string]$Method, [string]$Path, $Body = $null)
    $url = "$ServiceUrl$Path"
    try {
        $params = @{ Method = $Method; Uri = $url; ContentType = "application/json" }
        if ($Body) { $params.Body = ($Body | ConvertTo-Json -Depth 10) }
        $resp = Invoke-RestMethod @params
        return $resp
    } catch {
        $statusCode = [int]$_.Exception.Response.StatusCode
        $stream  = $_.Exception.Response.GetResponseStream()
        $reader  = [System.IO.StreamReader]::new($stream)
        $detail  = $reader.ReadToEnd() | ConvertFrom-Json -ErrorAction SilentlyContinue
        if ($detail.detail) {
            Write-Host "  API $statusCode : $($detail.detail | ConvertTo-Json -Depth 5)" -ForegroundColor Red
        } else {
            Write-Host "  API $statusCode : $($_.Exception.Message)" -ForegroundColor Red
        }
        return $null
    }
}

function Assert-ServiceRunning {
    $health = Invoke-Api GET "/health"
    if (-not $health) {
        Write-Host ""
        Write-Host "ERREUR : Roadmap Service inaccessible sur $ServiceUrl" -ForegroundColor Red
        Write-Host "         Demarrer avec : .\.venv\Scripts\activate ; cd Roadmap ; python run.py" -ForegroundColor Yellow
        exit 1
    }
}

if ($SeedFirst) {
    Assert-ServiceRunning
    Write-Host "Seeding depuis $RoadmapJson ..." -ForegroundColor Cyan
    $rawBody = Get-Content $RoadmapJson -Raw -Encoding UTF8
    $url = "$ServiceUrl/seed"
    try {
        $result = Invoke-RestMethod -Method POST -Uri $url -ContentType "application/json; charset=utf-8" -Body $rawBody
    } catch {
        $statusCode = [int]$_.Exception.Response.StatusCode
        Write-Host "  API $statusCode seed error" -ForegroundColor Red
        $result = $null
    }
    if ($result) {
        Write-Host "  Inserted : $($result.inserted)  Skipped : $($result.skipped)  Total : $($result.total)" -ForegroundColor Green
    }
    if (-not $PhaseId -and -not $List) { exit 0 }
}

if ($SeedUpdate) {
    Assert-ServiceRunning
    Write-Host "Mise a jour metadata depuis $RoadmapJson ..." -ForegroundColor Cyan
    $rawBody = Get-Content $RoadmapJson -Raw -Encoding UTF8
    $url = "$ServiceUrl/seed?update=true"
    try {
        $result = Invoke-RestMethod -Method POST -Uri $url -ContentType "application/json; charset=utf-8" -Body $rawBody
    } catch {
        $statusCode = [int]$_.Exception.Response.StatusCode
        Write-Host "  API $statusCode seed error" -ForegroundColor Red
        $result = $null
    }
    if ($result) {
        Write-Host "  Mis a jour : $($result.inserted)  Inchanges : $($result.skipped)  Total : $($result.total)" -ForegroundColor Green
    }
    if (-not $PhaseId -and -not $List) { exit 0 }
}

if ($List) {
    Assert-ServiceRunning
    Write-Host ""
    Write-Host "Phases actives :" -ForegroundColor Cyan
    $phases = Invoke-Api GET "/phases"
    if (-not $phases) { exit 1 }
    $phases | Where-Object { $_.status -ne "done" } | ForEach-Object {
        $color = if ($_.status -eq "pending") { "Yellow" } else { "DarkGray" }
        Write-Host ("  [{0,-20}]  {1}" -f $_.id, $_.name) -ForegroundColor $color
        if ($_.exit_criteria) { Write-Host ("             Critere : {0}" -f $_.exit_criteria) -ForegroundColor DarkGray }
        if ($_.notes)          { Write-Host ("             Notes   : {0}" -f $_.notes)          -ForegroundColor DarkGray }
        Write-Host ""
    }
    exit 0
}

if (-not $PhaseId) {
    Write-Host "Usage: .\Tools\Set-PhaseComplete.ps1 -PhaseId <id> [-Force] [-List] [-SeedFirst]" -ForegroundColor Yellow
    exit 1
}

Assert-ServiceRunning

$forceParam = if ($Force) { "?force=true" } else { "?force=false" }

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  Set-PhaseComplete : $PhaseId" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

$result = Invoke-Api POST "/phases/$PhaseId/complete$forceParam"

if (-not $result) { exit 1 }

if ($result.status -eq "needs_validation") {
    Write-Host ""
    Write-Host "  Cette phase necessite des tests avant validation." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Lance ces commandes depuis e:\terraformation :" -ForegroundColor Cyan
    foreach ($f in $result.test_files) {
        Write-Host ("    pytest SimulationCore/tests/{0}" -f $f) -ForegroundColor White
    }
    Write-Host ""
    if (-not $Force) {
        $confirm = Read-Host "   Les tests sont-ils tous PASS ? (oui/non)"
        if ($confirm -notmatch "^(oui|o|yes|y)$") {
            Write-Host "Annule. Lance les tests d'abord." -ForegroundColor DarkGray
            exit 0
        }
    }
    $result = Invoke-Api POST "/phases/$PhaseId/complete?force=true"
    if (-not $result) { exit 1 }
}

if ($result.status -eq "needs_confirmation") {
    Write-Host ""
    Write-Host "  Cette phase necessite une validation visuelle (Play Mode Unity)." -ForegroundColor Yellow
    Write-Host "  $($result.message)" -ForegroundColor Gray
    if ($result.phase.notes) {
        Write-Host "  Notes : $($result.phase.notes)" -ForegroundColor DarkGray
    }
    Write-Host ""
    $confirm = Read-Host "   La validation visuelle est-elle passee ? (oui/non)"
    if ($confirm -notmatch "^(oui|o|yes|y)$") {
        Write-Host "Annule." -ForegroundColor DarkGray
        exit 0
    }
    $result = Invoke-Api POST "/phases/$PhaseId/complete?force=true"
    if (-not $result) { exit 1 }
}

$anchor = $result.phase.roadmap_anchor
if ($anchor) {
    $mdContent  = Get-Content $RoadmapMd -Raw -Encoding UTF8
    $escaped    = [regex]::Escape($anchor)
    $newContent = $mdContent -replace "(\- \[ \] )(.*$escaped)", '- [x] $2'
    if ($newContent -ne $mdContent) {
        Set-Content $RoadmapMd -Value $newContent -Encoding UTF8
        Write-Host "  ROADMAP.md mis a jour ([ ] → [x] sur '$anchor')." -ForegroundColor Green
    } else {
        Write-Host "  WARN : ancre '$anchor' non trouvee dans ROADMAP.md." -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  DONE : $($result.phase.name)" -ForegroundColor Green
Write-Host "  Date : $($result.phase.completed_date)" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
Write-Host ""

exit 0
