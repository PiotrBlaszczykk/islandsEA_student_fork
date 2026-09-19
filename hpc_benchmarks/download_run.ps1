param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+(?:_[0-9]+)?$')]
    [string]$JobId,
    [Parameter(Mandatory = $true)]
    [ValidateSet('ares', 'athena')]
    [string]$Platform,
    [string]$Remote = '',
    [string]$Destination = '',
    [string]$RemoteExportRoot = '',
    [string]$Python = 'python',
    [switch]$Extract
)

$ErrorActionPreference = 'Stop'
if (-not $Remote) {
    $Remote = if ($Platform -eq 'ares') { 'plgblaszczykk@login01.ares.cyfronet.pl' } else { 'plgblaszczykk@athena.cyfronet.pl' }
}
if ($Remote -notmatch '^[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+$') {
    throw 'Remote must be user@hostname.'
}
if (-not $Destination) {
    $repo = Split-Path $PSScriptRoot -Parent
    $workspace = Split-Path (Split-Path $repo -Parent) -Parent
    $Destination = Join-Path $workspace "artifacts/run_wyniki/$Platform"
}
if (-not $RemoteExportRoot) {
    $scratchOutput = & ssh $Remote 'printf "%s" "$SCRATCH"'
    if ($LASTEXITCODE -ne 0) { throw 'Could not resolve remote SCRATCH.' }
    $scratch = ([string]$scratchOutput).Trim()
    $RemoteExportRoot = "$scratch/islandsEA/exports"
}
if ($RemoteExportRoot -notmatch '^/[A-Za-z0-9_./-]+$') {
    throw 'RemoteExportRoot must be an absolute Linux path without shell characters.'
}
$name = "run_$JobId.tar.gz"
$archive = Join-Path $Destination $name
$checksum = "$archive.sha256"
$directory = Join-Path $Destination "run_$JobId"
foreach ($path in @($archive, $checksum, "$archive.part", "$checksum.part", $directory)) {
    if (Test-Path -LiteralPath $path) { throw "Destination already exists: $path. Choose another -Destination." }
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
& scp "${Remote}:$RemoteExportRoot/$name" "$archive.part"
if ($LASTEXITCODE -ne 0) { throw 'Archive download failed; partial file retained.' }
& scp "${Remote}:$RemoteExportRoot/$name.sha256" "$checksum.part"
if ($LASTEXITCODE -ne 0) { throw 'Checksum download failed; partial files retained.' }
$record = (Get-Content -LiteralPath "$checksum.part" -Raw).Trim() -split '\s+'
if ($record.Count -ne 2 -or $record[1] -ne $name -or $record[0] -notmatch '^[0-9a-fA-F]{64}$') {
    throw 'Malformed checksum file.'
}
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath "$archive.part").Hash
if ($actual -ne $record[0]) { throw 'Archive SHA-256 mismatch; do not extract.' }
Move-Item -LiteralPath "$archive.part" -Destination $archive
Move-Item -LiteralPath "$checksum.part" -Destination $checksum
Write-Host "SHA256_OK=$archive"
if ($Extract) {
    # The Python verifier checks all payload hashes and rejects traversal/links
    # before the system tar writes anything to the destination.
    & $Python (Join-Path $PSScriptRoot 'run_bundle.py') verify $archive
    if ($LASTEXITCODE -ne 0) { throw 'Bundle payload verification failed; archive retained without extraction.' }
    & tar -xzf $archive -C $Destination
    if ($LASTEXITCODE -ne 0) { throw 'Extraction failed.' }
    Write-Host "RUN_DIRECTORY=$directory"
}
Write-Host "RUN_DOWNLOAD_OK=$archive"
