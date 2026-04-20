# Test-Phase94Market.ps1
#
# Phase 9.4 — Price velocity and history unit tests.
# Runs the test suite for market pricing logic.
#
# Usage:
#   .\Tools\Test-Phase94Market.ps1

# Ensure we're in the terraformation directory
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

# Run tests using the venv Python
& "$repoRoot\.venv\Scripts\python.exe" "$repoRoot\SimulationCore\tests\test_phase94_market.py"
