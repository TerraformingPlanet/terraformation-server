<#
.SYNOPSIS
    Validation globale de fin de phase : Python tests + syntaxe.
    Depuis la racine : .\Tools\Invoke-PhaseValidation.ps1
.PARAMETER Filter
    Filtre les fichiers test_<Filter>*.py. Par defaut "*" = tous.
.EXAMPLE
    .\Tools\Invoke-PhaseValidation.ps1
    .\Tools\Invoke-PhaseValidation.ps1 -Filter "phase9"
#>
param(
    [string]$Filter    = "*",
    [string]$PythonExe = ".\.venv\Scripts\python.exe"
)

$Root       = $PSScriptRoot | Split-Path -Parent
$TestDir    = Join-Path $Root "SimulationCore\tests"
$ModelsPath = Join-Path $Root "SimulationCore\terraformation_sim\models.py"

$totalPass   = 0
$totalFail   = 0
$failedItems = @()

# Force UTF-8 pour que les caracteres Unicode des tests s'affichent correctement
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "========================================================"  -ForegroundColor Cyan
Write-Host "  TERRAFORMATION -- Phase Validation"                       -ForegroundColor Cyan
Write-Host "========================================================"  -ForegroundColor Cyan
Write-Host ""

# Helper : executer Python et capturer stdout+stderr sans que PS leve une exception
function Invoke-Python {
    param([string[]]$Args_)
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName  = (Resolve-Path $PythonExe).Path
    $psi.Arguments = ($Args_ | ForEach-Object { "`"$_`"" }) -join " "
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.UseShellExecute        = $false
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding  = [System.Text.Encoding]::UTF8
    $psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8"
    $proc = [System.Diagnostics.Process]::Start($psi)
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    [PSCustomObject]@{ ExitCode = $proc.ExitCode; Output = ($stdout + $stderr).Split("`n") }
}

# -- 1. Syntaxe models.py -------------------------------------------------------
Write-Host "[1/3] Syntax check -- models.py" -ForegroundColor Yellow
$r = Invoke-Python "-m", "py_compile", $ModelsPath
if ($r.ExitCode -eq 0) {
    Write-Host "  OK  models.py syntaxe OK" -ForegroundColor Green
    $totalPass++
} else {
    Write-Host "  ERR models.py -- ERREUR SYNTAXE :" -ForegroundColor Red
    $r.Output | Select-Object -First 5 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    $totalFail++
    $failedItems += "models.py (syntax)"
}

# -- 2. Tests Python ------------------------------------------------------------
Write-Host ""
Write-Host "[2/3] Python unit tests (test_$Filter*.py)" -ForegroundColor Yellow

$testFiles = Get-ChildItem -Path $TestDir -Filter "test_$Filter*.py" -ErrorAction SilentlyContinue | Sort-Object Name

if (-not $testFiles -or $testFiles.Count -eq 0) {
    Write-Host "  WARN Aucun fichier test trouve (filtre: test_$Filter*.py)" -ForegroundColor DarkYellow
} else {
    foreach ($file in $testFiles) {
        Write-Host "  Running $($file.Name) ..." -NoNewline
        $r = Invoke-Python $file.FullName
        if ($r.ExitCode -eq 0) {
            $passLine = ($r.Output | Select-String "PASS|tests PASSED|reussis" | Select-Object -Last 1)
            Write-Host " PASS" -ForegroundColor Green
            if ($passLine) { Write-Host "    $($passLine.Line.Trim())" -ForegroundColor DarkGray }
            $totalPass++
        } else {
            Write-Host " FAIL" -ForegroundColor Red
            $r.Output | Select-Object -First 10 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
            $totalFail++
            $failedItems += $file.Name
        }
    }
}

# -- 3. Recap -------------------------------------------------------------------
Write-Host ""
Write-Host "[3/3] Recap" -ForegroundColor Yellow
$total = $totalPass + $totalFail
if ($totalFail -eq 0) {
    Write-Host "  ALL PASS : $totalPass/$total checks OK" -ForegroundColor Green
} else {
    Write-Host "  FAILED   : $totalPass/$total pass -- $totalFail echoues" -ForegroundColor Red
    $failedItems | ForEach-Object { Write-Host "     . $_" -ForegroundColor Red }
}

# -- 4. Rappel Unity (MCP agent uniquement) ------------------------------------
Write-Host ""
Write-Host "--------------------------------------------------------"  -ForegroundColor DarkCyan
Write-Host "  UNITY VALIDATION (agent MCP -- non automatisable PS)"    -ForegroundColor DarkCyan
Write-Host "--------------------------------------------------------"  -ForegroundColor DarkCyan
Write-Host "  Si SimulationContracts.cs modifie :"                     -ForegroundColor DarkCyan
Write-Host "    Unity_ValidateScript('Assets/Scripts/Simulation/Contracts/SimulationContracts.cs')" -ForegroundColor DarkCyan
Write-Host "  Si GameHUD.cs modifie :"                                  -ForegroundColor DarkCyan
Write-Host "    Unity_ValidateScript('Assets/Scripts/UI/GameHUD.cs')"  -ForegroundColor DarkCyan
Write-Host "  Si GameHUDBuildingIcons.cs modifie :"                    -ForegroundColor DarkCyan
Write-Host "    Unity_ValidateScript('Assets/Scripts/UI/GameHUDBuildingIcons.cs')" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  Marquer [x] ROADMAP uniquement apres 0 erreur Python ET 0 erreur C#." -ForegroundColor DarkCyan
Write-Host "========================================================"  -ForegroundColor Cyan
Write-Host ""

if ($totalFail -gt 0) { exit 1 } else { exit 0 }