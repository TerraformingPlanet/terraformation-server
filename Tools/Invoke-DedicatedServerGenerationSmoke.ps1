param(
    [string]$BaseUrl = 'http://127.0.0.1:8080',
    [switch]$SkipBuild,
    [int]$H3Resolution = 2,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $SkipBuild) {
    Write-Host 'Rebuilding dedicated server container...'
    Push-Location $repoRoot
    try {
        docker compose up -d --build terraformation-dedicated-server
    }
    finally {
        Pop-Location
    }
}

$qualityScript = Join-Path $PSScriptRoot 'Test-GenerationQuality.ps1'
$psArgs = @(
    '-NoProfile'
    '-ExecutionPolicy'
    'Bypass'
    '-File'
    $qualityScript
    '-BaseUrl'
    $BaseUrl
    '-H3Resolution'
    $H3Resolution
)

if ($AsJson) {
    $psArgs += '-AsJson'
}

Write-Host 'Running generation quality suite...'
& powershell @psArgs
exit $LASTEXITCODE