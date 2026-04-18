param(
    [string]$BaseUrl = 'http://127.0.0.1:8080',
    [int]$H3Resolution = 2,
    [switch]$AsJson,
    [switch]$FailFast
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-GenerationStats {
    param(
        [Parameter(Mandatory = $true)][string]$Coherence,
        [Parameter(Mandatory = $true)][double]$WaterLevel,
        [Parameter(Mandatory = $true)][double]$AtmosphereDensity,
        [Parameter(Mandatory = $true)][int]$Seed,
        [Parameter(Mandatory = $true)][int]$Resolution
    )

    $coherenceValue = switch ($Coherence.ToLowerInvariant()) {
        'none' { 0 }
        'ocean' { 1 }
        'arid' { 2 }
        'frozen' { 3 }
        'coast' { 4 }
        'basin' { 5 }
        default { throw "Unknown coherence preset: $Coherence" }
    }

    $query = @{
        coherence = $coherenceValue
        water_level = $WaterLevel
        atmosphere_density = $AtmosphereDensity
        seed = $Seed
        h3_resolution = $Resolution
    }

    $pairs = foreach ($entry in $query.GetEnumerator()) {
        $key = [System.Uri]::EscapeDataString([string]$entry.Key)
        $value = [System.Uri]::EscapeDataString([string]$entry.Value)
        "$key=$value"
    }

    $uri = '{0}/debug/generation-stats?{1}' -f $BaseUrl.TrimEnd('/'), ($pairs -join '&')
    return Invoke-RestMethod -Method Get -Uri $uri
}

function Get-Pct {
    param(
        [Parameter(Mandatory = $true)]$Map,
        [Parameter(Mandatory = $true)][string]$Key
    )

    if ($null -eq $Map) {
        return 0.0
    }

    $prop = $Map.PSObject.Properties[$Key]
    if ($null -eq $prop -or $null -eq $prop.Value) {
        return 0.0
    }

    return [double]$prop.Value.pct
}

function New-Check {
    param(
        [Parameter(Mandatory = $true)][string]$Preset,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Passed,
        [Parameter(Mandatory = $true)][string]$Message
    )

    [pscustomobject]@{
        preset = $Preset
        check = $Name
        passed = $Passed
        message = $Message
    }
}

$profiles = @(
    [pscustomobject]@{ Name = 'Coast';  WaterLevel = 0.71; AtmosphereDensity = 0.70; Seed = 1004 }
    [pscustomobject]@{ Name = 'Ocean';  WaterLevel = 0.85; AtmosphereDensity = 0.65; Seed = 1011 }
    [pscustomobject]@{ Name = 'Arid';   WaterLevel = 0.03; AtmosphereDensity = 0.12; Seed = 1021 }
    [pscustomobject]@{ Name = 'Frozen'; WaterLevel = 0.35; AtmosphereDensity = 0.30; Seed = 1031 }
    [pscustomobject]@{ Name = 'Basin';  WaterLevel = 0.18; AtmosphereDensity = 0.45; Seed = 1041 }
)

$results = [System.Collections.Generic.List[object]]::new()
$checks = [System.Collections.Generic.List[object]]::new()

foreach ($presetProfile in $profiles) {
    $stats = Invoke-GenerationStats -Coherence $presetProfile.Name -WaterLevel $presetProfile.WaterLevel -AtmosphereDensity $presetProfile.AtmosphereDensity -Seed $presetProfile.Seed -Resolution $H3Resolution

    $row = [pscustomobject]@{
        preset = $presetProfile.Name
        seed = $presetProfile.Seed
        atmo = $presetProfile.AtmosphereDensity
        waterLevel = $presetProfile.WaterLevel
        dryPct = [double]$stats.quality.dry_pct
        humidPct = [double]$stats.quality.humid_pct
        saturatedPct = [double]$stats.quality.saturated_pct
        habitablePct = [double]$stats.quality.habitable_pct
        coldPct = [double]$stats.quality.cold_pct
        hotPct = [double]$stats.quality.hot_pct
        vegetationPct = Get-Pct -Map $stats.terrain -Key 'Vegetation'
        waterPct = (Get-Pct -Map $stats.terrain -Key 'Eau') + (Get-Pct -Map $stats.water_classification -Key 'OpenOcean')
        openOceanPct = Get-Pct -Map $stats.water_classification -Key 'OpenOcean'
        frozenPct = Get-Pct -Map $stats.water_classification -Key 'FrozenWater'
        coastPct = Get-Pct -Map $stats.water_classification -Key 'Coast'
        inlandPct = Get-Pct -Map $stats.water_classification -Key 'InlandWater'
        basinPct = Get-Pct -Map $stats.terrain_class -Key 'Basin'
        ridgePct = Get-Pct -Map $stats.terrain_class -Key 'Ridge'
        tempMin = [double]$stats.temperature.min
        tempMax = [double]$stats.temperature.max
        tempAvg = [double]$stats.temperature.avg
    }

    $results.Add($row) | Out-Null

    switch ($presetProfile.Name) {
        'Coast' {
            $checks.Add((New-Check -Preset $presetProfile.Name -Name 'coast-band-present' -Passed ($row.coastPct -ge 5.0) -Message ('Coast should keep at least 5% coastal tiles, got {0:N1}%' -f $row.coastPct))) | Out-Null
            $checks.Add((New-Check -Preset $presetProfile.Name -Name 'vegetation-present' -Passed ($row.vegetationPct -ge 5.0) -Message ('Coast should keep at least 5% vegetation, got {0:N1}%' -f $row.vegetationPct))) | Out-Null
        }
        'Ocean' {
            $checks.Add((New-Check -Preset $presetProfile.Name -Name 'ocean-dominant' -Passed ($row.openOceanPct -ge 45.0) -Message ('Ocean should have at least 45% open ocean, got {0:N1}%' -f $row.openOceanPct))) | Out-Null
            $checks.Add((New-Check -Preset $presetProfile.Name -Name 'not-overdry' -Passed ($row.dryPct -le 25.0) -Message ('Ocean should not be dry above 25%, got {0:N1}%' -f $row.dryPct))) | Out-Null
        }
        'Arid' {
            $checks.Add((New-Check -Preset $presetProfile.Name -Name 'dry-dominant' -Passed ($row.dryPct -ge 60.0) -Message ('Arid should have at least 60% dry tiles, got {0:N1}%' -f $row.dryPct))) | Out-Null
            $checks.Add((New-Check -Preset $presetProfile.Name -Name 'limited-vegetation' -Passed ($row.vegetationPct -le 15.0) -Message ('Arid should keep vegetation under 15%, got {0:N1}%' -f $row.vegetationPct))) | Out-Null
        }
        'Frozen' {
            $checks.Add((New-Check -Preset $presetProfile.Name -Name 'cold-dominant' -Passed ($row.coldPct -ge 40.0) -Message ('Frozen should have at least 40% cold tiles, got {0:N1}%' -f $row.coldPct))) | Out-Null
            $checks.Add((New-Check -Preset $presetProfile.Name -Name 'ice-present' -Passed ($row.frozenPct -ge 5.0) -Message ('Frozen should have at least 5% frozen water, got {0:N1}%' -f $row.frozenPct))) | Out-Null
        }
        'Basin' {
            $checks.Add((New-Check -Preset $presetProfile.Name -Name 'inland-water-present' -Passed ($row.inlandPct -ge 5.0) -Message ('Basin should have at least 5% inland water, got {0:N1}%' -f $row.inlandPct))) | Out-Null
            $checks.Add((New-Check -Preset $presetProfile.Name -Name 'basin-shapes-present' -Passed ($row.basinPct -ge 9.5) -Message ('Basin should keep at least 9.5% terrainClass Basin, got {0:N1}%' -f $row.basinPct))) | Out-Null
        }
    }

    if ($FailFast -and ($checks | Where-Object { -not $_.passed } | Select-Object -First 1)) {
        break
    }
}

$failedChecks = @($checks | Where-Object { -not $_.passed })

if ($AsJson) {
    [pscustomobject]@{
        ok = ($failedChecks.Count -eq 0)
        results = $results
        checks = $checks
    } | ConvertTo-Json -Depth 8
    if ($failedChecks.Count -gt 0) {
        exit 1
    }
    exit 0
}

Write-Host ''
Write-Host 'Generation preset summary:'
$results | Format-Table preset, atmo, waterLevel, dryPct, humidPct, saturatedPct, habitablePct, coldPct, hotPct, vegetationPct, openOceanPct, frozenPct, coastPct, inlandPct, basinPct, tempAvg -AutoSize

Write-Host ''
if ($failedChecks.Count -eq 0) {
    Write-Host 'All generation checks passed.' -ForegroundColor Green
    exit 0
}

Write-Host 'Generation checks failed:' -ForegroundColor Red
$failedChecks | Format-Table preset, check, message -AutoSize
exit 1