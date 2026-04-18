param(
    [string]$BaseUrl = 'http://127.0.0.1:48621',
    [string]$Preset = 'Coast',
    [double]$Latitude = [double]::NaN,
    [double]$Longitude = [double]::NaN,
    [switch]$SkipRegionOpen,
    [int]$ConsoleMaxEntries = 20,
    [ValidateSet('Log', 'Warning', 'Error', 'Assert', 'Exception')]
    [string]$MinimumSeverity = 'Warning',
    [switch]$CaptureScreenshot,
    [string]$ScreenshotName,
    [string]$OutputDirectory,
    [switch]$FailOnWarnings
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-DebugGet {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [hashtable]$Query
    )

    $builder = [System.UriBuilder]::new(($BaseUrl.TrimEnd('/') + $Path))
    if ($Query -and $Query.Count -gt 0) {
        $pairs = foreach ($entry in $Query.GetEnumerator()) {
            $encodedKey = [System.Uri]::EscapeDataString([string]$entry.Key)
            $encodedValue = [System.Uri]::EscapeDataString([string]$entry.Value)
            "$encodedKey=$encodedValue"
        }

        $builder.Query = ($pairs -join '&')
    }

    Write-Host ("GET {0}" -f $builder.Uri.AbsoluteUri)
    return Invoke-RestMethod -Method Get -Uri $builder.Uri.AbsoluteUri
}

function Save-Artifact {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Value
    )

    if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
        return
    }

    if (-not (Test-Path -LiteralPath $OutputDirectory)) {
        New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
    }

    $filePath = Join-Path $OutputDirectory ($Name + '.json')
    $Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $filePath -Encoding UTF8
}

function Get-DefaultCoordinates {
    param([string]$PresetName)

    switch ($PresetName.ToLowerInvariant()) {
        'coast' { return @{ lat = 0.47; lon = 0.18 } }
        'basin' { return @{ lat = 0.57; lon = 0.58 } }
        'frozen' { return @{ lat = 0.20; lon = 0.50 } }
        'ocean' { return @{ lat = 0.50; lon = 0.50 } }
        'arid' { return @{ lat = 0.52; lon = 0.52 } }
        default { return @{ lat = 0.50; lon = 0.50 } }
    }
}

function Add-CheckResult {
    param(
        [Parameter(Mandatory = $true)]$Checks,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Passed,
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$Severity = 'Error'
    )

    $Checks.Add([pscustomobject]@{
        name = $Name
        passed = $Passed
        severity = $Severity
        message = $Message
    }) | Out-Null
}

function Test-ObjectHasProperty {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$PropertyName
    )

    if ($null -eq $Object) {
        return $false
    }

    return ($Object.PSObject.Properties.Name -contains $PropertyName)
}

function Test-SmokeResults {
    param(
        [Parameter(Mandatory = $true)][string]$PresetName,
        [Parameter(Mandatory = $true)]$SummaryObject,
        [switch]$TreatWarningsAsFailures
    )

    $checks = [System.Collections.Generic.List[object]]::new()

    Add-CheckResult -Checks $checks -Name 'state-before-response' -Passed ($null -ne $SummaryObject.stateBefore) -Message 'Le endpoint /debug/state doit repondre avant le lancement.'
    Add-CheckResult -Checks $checks -Name 'launch-preset-success' -Passed ($SummaryObject.launchResult.success -eq $true) -Message 'Le preset doit etre lance avec succes.'
    Add-CheckResult -Checks $checks -Name 'projection-valid' -Passed ($SummaryObject.projection.isValid -eq $true) -Message 'La projection active doit retourner un resume valide.'
    $hasProjectionGridSummary = Test-ObjectHasProperty -Object $SummaryObject.projection -PropertyName 'gridSummary'
    Add-CheckResult -Checks $checks -Name 'projection-grid-summary' -Passed $hasProjectionGridSummary -Message 'La projection doit inclure un gridSummary exploitable.'

    if ($SummaryObject.Contains('openRegion')) {
        Add-CheckResult -Checks $checks -Name 'open-region-success' -Passed ($SummaryObject.openRegion.success -eq $true) -Message 'L ouverture de region doit reussir.'
    }

    $hasLocalGridSummary = $false
    if ($SummaryObject.Contains('local')) {
        Add-CheckResult -Checks $checks -Name 'local-valid' -Passed ($SummaryObject.local.isValid -eq $true) -Message 'La region locale doit retourner un resume valide.'
        $hasLocalGridSummary = Test-ObjectHasProperty -Object $SummaryObject.local -PropertyName 'gridSummary'
        Add-CheckResult -Checks $checks -Name 'local-grid-summary' -Passed $hasLocalGridSummary -Message 'La region locale doit inclure un gridSummary exploitable.'
    }

    Add-CheckResult -Checks $checks -Name 'console-no-errors' -Passed (($SummaryObject.console.errorCount -eq 0) -and ($SummaryObject.console.exceptionCount -eq 0)) -Message 'La console ne doit pas contenir d erreurs ou d exceptions.'
    Add-CheckResult -Checks $checks -Name 'console-warning-count' -Passed ($SummaryObject.console.warningCount -eq 0) -Message 'La console ne devrait idealement pas contenir de warnings.' -Severity 'Warning'

    switch ($PresetName.ToLowerInvariant()) {
        'coast' {
            if ($hasProjectionGridSummary) {
                Add-CheckResult -Checks $checks -Name 'projection-coast-cells' -Passed ($SummaryObject.projection.gridSummary.coastCells -gt 0) -Message 'Le preset Coast doit produire des cellules Coast sur la projection.'
            }
            if ($SummaryObject.Contains('local') -and $hasLocalGridSummary) {
                Add-CheckResult -Checks $checks -Name 'local-coast-cells' -Passed ($SummaryObject.local.gridSummary.coastCells -gt 0) -Message 'Le preset Coast doit produire des cellules Coast localement.'
            }
        }
        'basin' {
            if ($hasProjectionGridSummary) {
                Add-CheckResult -Checks $checks -Name 'projection-inland-water' -Passed ($SummaryObject.projection.gridSummary.inlandWaterCells -gt 0) -Message 'Le preset Basin doit produire de l eau interieure sur la projection.'
            }
            if ($SummaryObject.Contains('local') -and $hasLocalGridSummary) {
                Add-CheckResult -Checks $checks -Name 'local-basin-or-water' -Passed (($SummaryObject.local.gridSummary.basinCells -gt 0) -or ($SummaryObject.local.gridSummary.inlandWaterCells -gt 0)) -Message 'Le preset Basin doit produire un bassin ou de l eau interieure localement.'
            }
        }
        'ocean' {
            if ($hasProjectionGridSummary) {
                Add-CheckResult -Checks $checks -Name 'projection-ocean-dominant' -Passed ($SummaryObject.projection.gridSummary.openOceanCells -gt $SummaryObject.projection.gridSummary.dryCells) -Message 'Le preset Ocean doit etre majoritairement oceanique en projection.'
            }
            if ($SummaryObject.Contains('local') -and $hasLocalGridSummary) {
                Add-CheckResult -Checks $checks -Name 'local-water-dominant' -Passed ($SummaryObject.local.gridSummary.averageWaterRatio -ge 0.45) -Message 'Le preset Ocean doit conserver une eau moyenne elevee localement.'
            }
        }
        'arid' {
            if ($hasProjectionGridSummary) {
                Add-CheckResult -Checks $checks -Name 'projection-dry-dominant' -Passed ($SummaryObject.projection.gridSummary.dryCells -gt ($SummaryObject.projection.gridSummary.openOceanCells + $SummaryObject.projection.gridSummary.inlandWaterCells)) -Message 'Le preset Arid doit etre majoritairement sec en projection.'
            }
            if ($SummaryObject.Contains('local') -and $hasLocalGridSummary) {
                Add-CheckResult -Checks $checks -Name 'local-dry-dominant' -Passed ($SummaryObject.local.gridSummary.dryCells -gt ($SummaryObject.local.gridSummary.openOceanCells + $SummaryObject.local.gridSummary.inlandWaterCells + $SummaryObject.local.gridSummary.coastCells)) -Message 'Le preset Arid doit rester majoritairement sec localement.'
            }
        }
        'frozen' {
            if ($hasProjectionGridSummary) {
                Add-CheckResult -Checks $checks -Name 'projection-frozen-cells' -Passed ($SummaryObject.projection.gridSummary.frozenWaterCells -gt 0) -Message 'Le preset Frozen doit produire de l eau gelee en projection.'
            }
            if ($SummaryObject.Contains('local') -and $hasLocalGridSummary) {
                Add-CheckResult -Checks $checks -Name 'local-frozen-or-cold' -Passed (($SummaryObject.local.gridSummary.frozenWaterCells -gt 0) -or ($SummaryObject.local.gridSummary.averageTemperature -le 0)) -Message 'Le preset Frozen doit produire soit de l eau gelee soit une temperature moyenne locale froide.'
            }
        }
    }

    $failures = @($checks | Where-Object { -not $_.passed -and $_.severity -eq 'Error' })
    $warnings = @($checks | Where-Object { -not $_.passed -and $_.severity -eq 'Warning' })
    $passed = ($failures.Count -eq 0) -and (-not $TreatWarningsAsFailures -or $warnings.Count -eq 0)

    return [pscustomobject]@{
        passed = $passed
        failures = $failures
        warnings = $warnings
        checks = @($checks)
    }
}

$coordinates = Get-DefaultCoordinates -PresetName $Preset
if (-not [double]::IsNaN($Latitude)) {
    $coordinates.lat = $Latitude
}
if (-not [double]::IsNaN($Longitude)) {
    $coordinates.lon = $Longitude
}

$summary = [ordered]@{
    baseUrl = $BaseUrl
    preset = $Preset
    latitude = $coordinates.lat
    longitude = $coordinates.lon
    startedAt = (Get-Date).ToString('s')
}

$stateBefore = Invoke-DebugGet -Path '/debug/state'
$summary.stateBefore = $stateBefore
Save-Artifact -Name '01_state_before' -Value $stateBefore

$launchResult = Invoke-DebugGet -Path '/debug/launch-preset' -Query @{ preset = $Preset }
$summary.launchResult = $launchResult
Save-Artifact -Name '02_launch_preset' -Value $launchResult

$stateAfterLaunch = Invoke-DebugGet -Path '/debug/state'
$summary.stateAfterLaunch = $stateAfterLaunch
Save-Artifact -Name '03_state_after_launch' -Value $stateAfterLaunch

$projection = Invoke-DebugGet -Path '/debug/projection'
$summary.projection = $projection
Save-Artifact -Name '04_projection' -Value $projection

if (-not $SkipRegionOpen) {
    $openRegion = Invoke-DebugGet -Path '/debug/open-region' -Query @{
        lat = $coordinates.lat
        lon = $coordinates.lon
    }

    $summary.openRegion = $openRegion
    Save-Artifact -Name '05_open_region' -Value $openRegion

    $local = Invoke-DebugGet -Path '/debug/local'
    $summary.local = $local
    Save-Artifact -Name '06_local' -Value $local
}

$console = Invoke-DebugGet -Path '/debug/console' -Query @{
    maxEntries = $ConsoleMaxEntries
    minimumSeverity = $MinimumSeverity
}

$summary.console = $console
Save-Artifact -Name '07_console' -Value $console

if ($CaptureScreenshot) {
    $effectiveScreenshotName = if ([string]::IsNullOrWhiteSpace($ScreenshotName)) {
        '{0}_{1}' -f $Preset.ToLowerInvariant(), (Get-Date -Format 'yyyyMMdd_HHmmss')
    }
    else {
        $ScreenshotName
    }

    $screenshot = Invoke-DebugGet -Path '/debug/screenshot' -Query @{ fileName = $effectiveScreenshotName }
    $summary.screenshot = $screenshot
    Save-Artifact -Name '08_screenshot' -Value $screenshot
}

$summary.completedAt = (Get-Date).ToString('s')
$summary.verdict = Test-SmokeResults -PresetName $Preset -SummaryObject $summary -TreatWarningsAsFailures:$FailOnWarnings

Save-Artifact -Name '00_summary' -Value $summary

Write-Host ''
Write-Host 'Smoke test summary:'
$summary | ConvertTo-Json -Depth 8

if (-not $summary.verdict.passed) {
    Write-Host ('Smoke test failed for preset {0}.' -f $Preset)
    exit 1
}

exit 0