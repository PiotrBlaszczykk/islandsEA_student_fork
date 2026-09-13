param(
    [string]$Remote = "plgblaszczykk@athena.cyfronet.pl",
    [string]$RemotePath = "~/artifacts/athena_duagnostics.txt",
    [string]$Destination = ""
)

$ErrorActionPreference = "Stop"

if (-not $Destination) {
    $RepositoryRoot = Split-Path -Parent $PSScriptRoot
    $MainCodebase = Split-Path -Parent $RepositoryRoot
    $Destination = Join-Path $MainCodebase "athena_diagnostics.txt"
}

$Destination = [System.IO.Path]::GetFullPath($Destination)
$DestinationDirectory = Split-Path -Parent $Destination
New-Item -ItemType Directory -Force -Path $DestinationDirectory | Out-Null

$RemoteSource = "${Remote}:$RemotePath"
Write-Host "Downloading $RemoteSource"
Write-Host "Destination: $Destination"
& scp -- $RemoteSource $Destination
if ($LASTEXITCODE -ne 0) {
    throw "scp failed with exit code $LASTEXITCODE"
}

$Report = Get-Content -Raw -LiteralPath $Destination
if ($Report -notmatch "ATHENA_LOGIN_DIAGNOSTICS_COMPLETE=1") {
    throw "Downloaded report is missing the login diagnostics completion marker."
}
if ($Report -notmatch "ATHENA_GPU_PROBE_COMPLETE=1") {
    Write-Warning "GPU probe has not completed yet. Re-run this downloader after the probe job finishes."
    exit 2
}

Write-Host "ATHENA_DIAGNOSTICS_DOWNLOAD_OK=$Destination"
