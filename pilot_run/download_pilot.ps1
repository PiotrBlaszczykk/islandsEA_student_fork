param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+$')]
    [string]$JobId,

    [string]$Remote = 'plgblaszczykk@login01.ares.cyfronet.pl',
    [string]$Destination = ''
)

$ErrorActionPreference = 'Stop'

if (-not $Destination) {
    $projectRoot = Split-Path $PSScriptRoot -Parent
    $mainCodebase = Split-Path $projectRoot -Parent
    $summerRoot = Split-Path $mainCodebase -Parent
    $Destination = Join-Path $summerRoot 'artifacts\pilot_runs'
}

$remoteScratch = (& ssh $Remote 'printf "%s" "$SCRATCH"').Trim()
if ($LASTEXITCODE -ne 0 -or -not $remoteScratch.StartsWith('/')) {
    throw "Nie udało się odczytać `$SCRATCH na $Remote."
}

$remoteDirectory = "$remoteScratch/islandsEA/results/pilot_runs/$JobId"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$localRun = Join-Path $Destination $JobId
if (Test-Path -LiteralPath $localRun) {
    throw "Katalog docelowy już istnieje: $localRun. Przenieś go lub wskaż inne -Destination."
}

Write-Host "Pobieram ${Remote}:$remoteDirectory"
& scp -r "${Remote}:$remoteDirectory" $Destination
if ($LASTEXITCODE -ne 0) {
    throw "scp zakończył się kodem $LASTEXITCODE."
}

$checksumFiles = Get-ChildItem -Path $localRun -Recurse -Filter '*.sha256'
if ($checksumFiles.Count -ne 3) {
    throw "Oczekiwano 3 plików SHA-256 (po jednym na repeat), znaleziono $($checksumFiles.Count)."
}
foreach ($checksumFile in $checksumFiles) {
    $expected = ((Get-Content $checksumFile.FullName -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    $archiveName = ((Get-Content $checksumFile.FullName -Raw).Trim() -split '\s+')[1]
    $archivePath = Join-Path $checksumFile.DirectoryName $archiveName
    if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
        throw "Brak archiwum wskazanego przez $($checksumFile.FullName): $archiveName"
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Błędny SHA-256: $archivePath"
    }
    Write-Host "SHA256_OK $archivePath"
}

$summary = Join-Path $localRun 'pilot_summary.json'
if (-not (Test-Path -LiteralPath $summary -PathType Leaf)) {
    throw "Brak pilot_summary.json w $localRun."
}
$summaryData = Get-Content -LiteralPath $summary -Raw | ConvertFrom-Json
if ($summaryData.valid -ne $true) {
    throw "Pobrany pilot nie ma valid=true w pilot_summary.json."
}
if ($summaryData.valid_repeats -ne 3 -or $summaryData.expected_repeats -ne 3) {
    throw "Pobrany pilot nie zawiera trzech poprawnych powtórzeń."
}

Write-Host "PILOT_DOWNLOAD_OK=$localRun"
