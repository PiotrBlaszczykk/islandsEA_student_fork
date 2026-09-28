param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+$')]
    [string]$ArrayJobId,
    [string]$Remote = 'plgblaszczykk@athena.cyfronet.pl',
    [string]$RemoteCampaignDir = '',
    [string]$Destination = ''
)

$ErrorActionPreference = 'Stop'
if ($Remote -notmatch '^[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+$') {
    throw 'Remote must be user@hostname.'
}
$CampaignName = "er4_random_$ArrayJobId"
if (-not $RemoteCampaignDir) {
    $RemoteCampaignDir = "/net/tscratch/people/plgblaszczykk/islandsEA/campaigns/$CampaignName"
}
if ($RemoteCampaignDir -notmatch '^/[A-Za-z0-9_./-]+$' -or
    $RemoteCampaignDir.TrimEnd('/').Split('/')[-1] -ne $CampaignName) {
    throw "RemoteCampaignDir must end with $CampaignName and contain no shell characters."
}
if (-not $Destination) {
    $repo = Split-Path $PSScriptRoot -Parent
    $workspace = Split-Path (Split-Path $repo -Parent) -Parent
    $Destination = Join-Path $workspace 'artifacts/run_wyniki/athena'
}
$LocalCampaign = Join-Path $Destination $CampaignName
if (Test-Path -LiteralPath $LocalCampaign) {
    throw "Destination already exists: $LocalCampaign. Refusing to overwrite."
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null

# One recursive source, one SSH/SCP connection. This copies only the campaign
# plan, records and 120 portable bundles; it never starts a cluster job.
& scp -r "${Remote}:${RemoteCampaignDir}" $Destination
if ($LASTEXITCODE -ne 0) {
    throw 'Campaign download failed. Inspect the partial destination before retrying.'
}
$PlanPath = Join-Path $LocalCampaign 'campaign_plan.json'
$TasksRoot = Join-Path $LocalCampaign 'tasks'
$RunsRoot = Join-Path $LocalCampaign 'runs'
if (-not (Test-Path -LiteralPath $PlanPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $TasksRoot -PathType Container) -or
    -not (Test-Path -LiteralPath $RunsRoot -PathType Container)) {
    throw 'Downloaded campaign has no plan, task records or runs directory.'
}
$Plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
if ($Plan.campaign -ne 'er4_random' -or [string]$Plan.array_job_id -ne $ArrayJobId -or
    $Plan.task_count -ne 120 -or $Plan.benchmark_count -ne 40 -or
    $Plan.repeat_count -ne 3 -or $Plan.configuration.topology.name -ne 'er4' -or
    $Plan.configuration.migration.selection -ne 'random' -or
    $Plan.configuration.migration.acceptance -ne 'plain') {
    throw 'Downloaded plan is not the requested ER4/random 40x3 campaign.'
}
$Tasks = @(Get-ChildItem -LiteralPath $TasksRoot -File -Filter 'task-*.json')
$Archives = @(Get-ChildItem -LiteralPath $RunsRoot -Recurse -File -Filter 'run_*.tar.gz')
$Checksums = @(Get-ChildItem -LiteralPath $RunsRoot -Recurse -File -Filter 'run_*.tar.gz.sha256')
if ($Tasks.Count -ne 120 -or $Archives.Count -ne 120 -or $Checksums.Count -ne 120) {
    throw "Incomplete download: tasks=$($Tasks.Count), archives=$($Archives.Count), checksums=$($Checksums.Count)."
}
foreach ($Archive in $Archives) {
    $Sidecar = "$($Archive.FullName).sha256"
    if (-not (Test-Path -LiteralPath $Sidecar -PathType Leaf)) {
        throw "Missing checksum: $Sidecar"
    }
    $Fields = (Get-Content -LiteralPath $Sidecar -Raw).Trim() -split '\s+'
    if ($Fields.Count -ne 2 -or $Fields[0] -notmatch '^[0-9a-fA-F]{64}$' -or
        $Fields[1] -ne $Archive.Name) {
        throw "Malformed checksum: $Sidecar"
    }
    $Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive.FullName).Hash
    if ($Actual -ne $Fields[0]) {
        throw "Archive SHA-256 mismatch: $($Archive.FullName)"
    }
}
Write-Host 'ATHENA_ER4_RANDOM_DOWNLOADED_ARCHIVES_SHA256_OK=120/120'
Write-Host "ATHENA_ER4_RANDOM_DOWNLOAD_OK=$LocalCampaign"
Write-Host 'Final aggregate (after all scientific validations):'
Write-Host "python -m athena_gpu.finalize_downloaded_er4 --campaign-dir '$LocalCampaign' --array-job-id $ArrayJobId --strategy random"
