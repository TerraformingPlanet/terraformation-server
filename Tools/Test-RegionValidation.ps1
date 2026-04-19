param(
    [string]$ServerUrl = "http://localhost:8080",
    [double]$Latitude  = 0.47,
    [double]$Longitude = 0.18
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Profiles = @(
    @{ Name="Coast";  Coherence=4; WaterLevel=0.71 }
    @{ Name="Ocean";  Coherence=1; WaterLevel=0.85 }
    @{ Name="Arid";   Coherence=2; WaterLevel=0.03 }
    @{ Name="Frozen"; Coherence=3; WaterLevel=0.35 }
    @{ Name="Basin";  Coherence=5; WaterLevel=0.18 }
)

function Invoke-SGet([string]$Path, [hashtable]$P=@{}) {
    $qs = ($P.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "&"
    $url = if ($qs) { "${ServerUrl}${Path}?${qs}" } else { "${ServerUrl}${Path}" }
    (Invoke-WebRequest -UseBasicParsing -Method GET $url -TimeoutSec 10).Content | ConvertFrom-Json
}
function Invoke-SPost([string]$Path, [hashtable]$P=@{}) {
    $qs = ($P.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "&"
    $url = if ($qs) { "${ServerUrl}${Path}?${qs}" } else { "${ServerUrl}${Path}" }
    (Invoke-WebRequest -UseBasicParsing -Method POST $url -TimeoutSec 10).Content | ConvertFrom-Json
}

Write-Host ""
Write-Host "=== Terraformation - Region Validation Suite ===" -ForegroundColor Cyan
Write-Host "Server : $ServerUrl | lat=$Latitude lon=$Longitude"
Write-Host ""

try {
    $h = (Invoke-WebRequest -UseBasicParsing "${ServerUrl}/health" -TimeoutSec 5).StatusCode
    Write-Host "Health : HTTP $h" -ForegroundColor Green
} catch {
    Write-Host "FAILED: server unreachable at $ServerUrl" -ForegroundColor Red
    exit 1
}

$Results = @()
$TotalIssues = 0

foreach ($p in $Profiles) {
    $row = [PSCustomObject]@{
        Preset     = $p.Name
        Cells      = 0
        OceanPct   = 0.0
        DryPct     = 0.0
        Issues     = 0
        Passed     = $true
        Note       = ""
    }
    try {
        Invoke-SPost "/commands/set-projection" @{ projection_override=$p.Coherence; water_level=$p.WaterLevel } | Out-Null
        $region = Invoke-SPost "/commands/open-region" @{ latitude=$Latitude; longitude=$Longitude }
        $row.Cells = ($region.cells | Measure-Object).Count
        $hy = Invoke-SGet "/debug/hydrology"
        $row.OceanPct = [math]::Round($hy.openOceanPct, 1)
        $row.DryPct   = [math]::Round($hy.dryPct, 1)
        $v = Invoke-SGet "/debug/validate"
        $row.Issues = $v.issueCount
        $row.Passed = [bool]$v.passed
        if (-not $v.passed) { $TotalIssues += $v.issueCount }
    } catch {
        $row.Passed = $false
        $row.Note   = $_.Exception.Message.Substring(0, [Math]::Min(60, $_.Exception.Message.Length))
        $TotalIssues++
    }
    $Results += $row
}

Write-Host ""
$Results | Format-Table Preset, Cells, OceanPct, DryPct, Issues, Passed, Note -AutoSize

$Failed = @($Results | Where-Object { -not $_.Passed })
if ($Failed.Count -eq 0) {
    Write-Host "ALL PASS ($($Results.Count)/$($Results.Count))" -ForegroundColor Green
    exit 0
} else {
    Write-Host "FAILED: $($Failed.Count)/$($Results.Count) - $TotalIssues total issues" -ForegroundColor Red
    exit 1
}