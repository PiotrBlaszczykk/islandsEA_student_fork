param(
    [string]$Remote = 'plgblaszczykk@login01.ares.cyfronet.pl',
    [string]$RemoteCampaignDir = '/net/afscra/people/plgblaszczykk/torus_random',
    [string]$Destination = '',
    [switch]$Extract
)

$ErrorActionPreference = 'Stop'
if ($Remote -notmatch '^[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+$') {
    throw 'Remote must be user@hostname.'
}
if ($RemoteCampaignDir -notmatch '^/[A-Za-z0-9_./-]+$') {
    throw 'RemoteCampaignDir must be an absolute Linux path without shell characters.'
}
if (-not $Destination) {
    $repo = Split-Path $PSScriptRoot -Parent
    $workspace = Split-Path (Split-Path $repo -Parent) -Parent
    $Destination = Join-Path $workspace 'artifacts/torus_random'
}

$archive = Join-Path $Destination 'torus_random.tar.gz'
$checksum = "$archive.sha256"
$directory = Join-Path $Destination 'torus_random'
foreach ($path in @($archive, $checksum, $directory)) {
    if (Test-Path -LiteralPath $path) {
        throw "Destination already exists: $path. Choose another -Destination."
    }
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null

# One remote source pattern means one scp connection and one password prompt.
& scp "${Remote}:$RemoteCampaignDir/torus_random.tar.gz*" $Destination
if ($LASTEXITCODE -ne 0) {
    throw 'Campaign download failed; inspect partial files before retrying.'
}
if (-not (Test-Path -LiteralPath $archive -PathType Leaf) -or
    -not (Test-Path -LiteralPath $checksum -PathType Leaf)) {
    throw 'Campaign archive or checksum is missing after scp.'
}
$fields = (Get-Content -LiteralPath $checksum -Raw).Trim() -split '\s+'
if ($fields.Count -ne 2 -or $fields[1] -ne 'torus_random.tar.gz' -or
    $fields[0] -notmatch '^[0-9a-fA-F]{64}$') {
    throw 'Malformed campaign checksum.'
}
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash
if ($actual -ne $fields[0]) {
    throw 'Campaign SHA-256 mismatch. Do not extract.'
}
Write-Host "TORUS_RANDOM_SHA256_OK=$archive"

if ($Extract) {
    & tar -xzf $archive -C $Destination
    if ($LASTEXITCODE -ne 0) { throw 'Campaign extraction failed.' }
    $summary = Join-Path $directory 'campaign_summary.json'
    if (-not (Test-Path -LiteralPath $summary -PathType Leaf)) {
        throw 'Campaign summary is missing after extraction.'
    }
    $data = Get-Content -LiteralPath $summary -Raw | ConvertFrom-Json
    if ($data.valid -ne $true -or $data.valid_runs -ne 120 -or $data.expected_runs -ne 120) {
        throw 'Campaign summary is not a valid 120-run result.'
    }
    $nested = @(Get-ChildItem -LiteralPath (Join-Path $directory 'runs') -Recurse -Filter 'run_*.tar.gz' -File)
    if ($nested.Count -ne 120) {
        throw "Expected 120 nested run archives, found $($nested.Count)."
    }
    if (@($data.runs).Count -ne 120) {
        throw 'Campaign summary does not list exactly 120 runs.'
    }
    foreach ($run in $data.runs) {
        $relative = [string]$run.archive
        if ($relative -notmatch '^runs/(r\d{2}|b\d{2})_[A-Za-z0-9_]+/repeat-[123]/run_[0-9]+\.tar\.gz$') {
            throw "Unsafe nested archive path: $relative"
        }
        $nestedPath = Join-Path $directory ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $nestedPath -PathType Leaf)) {
            throw "Nested archive is missing: $relative"
        }
        $nestedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $nestedPath).Hash
        if ($nestedHash -ne [string]$run.archive_sha256) {
            throw "Nested archive SHA-256 mismatch: $relative"
        }
    }
    Write-Host 'TORUS_RANDOM_NESTED_SHA256_OK=120'
    Write-Host "TORUS_RANDOM_DIRECTORY=$directory"
}
Write-Host "TORUS_RANDOM_DOWNLOAD_OK=$archive"
