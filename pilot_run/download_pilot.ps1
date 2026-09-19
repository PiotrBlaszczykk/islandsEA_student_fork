param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+$')]
    [string]$JobId,

    [string]$Remote = 'plgblaszczykk@login01.ares.cyfronet.pl',
    [string]$Destination = '',

    [switch]$LogsOnly
)

$ErrorActionPreference = 'Stop'

if (-not $Destination) {
    $projectRoot = Split-Path $PSScriptRoot -Parent
    $mainCodebase = Split-Path $projectRoot -Parent
    $summerRoot = Split-Path $mainCodebase -Parent
    $Destination = Join-Path $summerRoot 'artifacts\pilot_runs'
}

$remoteScratchOutput = & ssh $Remote 'printf "%s" "$SCRATCH"'
$sshExitCode = $LASTEXITCODE
$remoteScratch = ([string]$remoteScratchOutput).Trim()
if ($sshExitCode -ne 0 -or -not $remoteScratch.StartsWith('/')) {
    throw "Could not read `$SCRATCH on $Remote."
}

$remoteDirectory = "$remoteScratch/islandsEA/results/pilot_runs/$JobId"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$localRun = Join-Path $Destination $JobId
if ($LogsOnly -and -not (Test-Path -LiteralPath $localRun -PathType Container)) {
    throw "Cannot download logs because the pilot directory is missing: $localRun"
}
if (-not $LogsOnly -and (Test-Path -LiteralPath $localRun)) {
    throw "Destination already exists: $localRun. Move it or specify another -Destination."
}

if (-not $LogsOnly) {
    Write-Host "Downloading ${Remote}:$remoteDirectory"
    & scp -r "${Remote}:$remoteDirectory" $Destination
    if ($LASTEXITCODE -ne 0) {
        throw "scp exited with code $LASTEXITCODE."
    }
}

$checksumFiles = Get-ChildItem -Path $localRun -Recurse -Filter '*.sha256'
if ($checksumFiles.Count -ne 3) {
    throw "Expected 3 SHA-256 files (one per repeat), found $($checksumFiles.Count)."
}
foreach ($checksumFile in $checksumFiles) {
    $expected = ((Get-Content $checksumFile.FullName -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    $archiveName = ((Get-Content $checksumFile.FullName -Raw).Trim() -split '\s+')[1]
    $archivePath = Join-Path $checksumFile.DirectoryName $archiveName
    if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
        throw "Archive referenced by $($checksumFile.FullName) is missing: $archiveName"
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Invalid SHA-256: $archivePath"
    }
    Write-Host "SHA256_OK $archivePath"
}

$summary = Join-Path $localRun 'pilot_summary.json'
if (-not (Test-Path -LiteralPath $summary -PathType Leaf)) {
    throw "pilot_summary.json is missing from $localRun."
}
$summaryData = Get-Content -LiteralPath $summary -Raw | ConvertFrom-Json
if ($summaryData.valid -ne $true) {
    throw "Downloaded pilot does not have valid=true in pilot_summary.json."
}
if ($summaryData.valid_repeats -ne 3 -or $summaryData.expected_repeats -ne 3) {
    throw "Downloaded pilot does not contain three valid repeats."
}

$submission = Join-Path $localRun 'submission.json'
if (-not (Test-Path -LiteralPath $submission -PathType Leaf)) {
    throw "submission.json is missing from $localRun."
}
$submissionData = Get-Content -LiteralPath $submission -Raw | ConvertFrom-Json
$arrayJobId = [string]$submissionData.array_job_id
$finalizerJobId = [string]$submissionData.finalizer_job_id
if ($arrayJobId -notmatch '^\d+$' -or $finalizerJobId -notmatch '^\d+$') {
    throw "submission.json does not contain valid array and finalizer job IDs."
}

$localLogDirectory = Join-Path $localRun 'slurm_logs'
New-Item -ItemType Directory -Force -Path $localLogDirectory | Out-Null
$remoteLogRoot = "$remoteScratch/islandsEA/logs/slurm"
$logNames = @(
    "pilot-${arrayJobId}_1.out",
    "pilot-${arrayJobId}_1.err",
    "pilot-${arrayJobId}_2.out",
    "pilot-${arrayJobId}_2.err",
    "pilot-${arrayJobId}_3.out",
    "pilot-${arrayJobId}_3.err",
    "pilot-finalize-${finalizerJobId}.out",
    "pilot-finalize-${finalizerJobId}.err"
)
$remoteLogSources = @(
    $logNames | ForEach-Object { "${Remote}:$remoteLogRoot/$_" }
)
Write-Host "Downloading $($logNames.Count) SLURM logs from $Remote"
& scp @remoteLogSources $localLogDirectory
if ($LASTEXITCODE -ne 0) {
    throw "SLURM log download failed with code $LASTEXITCODE."
}
$missingLogs = @(
    $logNames | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $localLogDirectory $_) -PathType Leaf)
    }
)
if ($missingLogs.Count -ne 0) {
    throw "SLURM log download is incomplete: $($missingLogs -join ', ')"
}

Write-Host "PILOT_LOG_DOWNLOAD_OK=$localLogDirectory"
Write-Host "PILOT_DOWNLOAD_OK=$localRun"
