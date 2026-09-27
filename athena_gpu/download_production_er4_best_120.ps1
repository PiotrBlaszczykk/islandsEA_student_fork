param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+$')]
    [string]$ArrayJobId,
    [string]$Remote = 'plgblaszczykk@athena.cyfronet.pl',
    [string]$RemoteCampaignDir = '',
    [string]$Destination = ''
)

$ErrorActionPreference = 'Stop'
$CampaignName = "er4_best_$ArrayJobId"
if ($Remote -notmatch '^[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+$') {
    throw 'Remote must be user@hostname.'
}
if (-not $Destination) {
    $repo = Split-Path $PSScriptRoot -Parent
    $workspace = Split-Path (Split-Path $repo -Parent) -Parent
    $Destination = Join-Path $workspace 'artifacts/run_wyniki/athena'
}
if (-not $RemoteCampaignDir) {
    $scratchOutput = & ssh $Remote 'printf "%s" "$SCRATCH"'
    if ($LASTEXITCODE -ne 0) { throw 'Could not resolve remote SCRATCH.' }
    $scratch = ([string]$scratchOutput).Trim()
    $RemoteCampaignDir = "$scratch/islandsEA/campaigns/$CampaignName"
}
if ($RemoteCampaignDir -notmatch '^/[A-Za-z0-9_./-]+$' -or
    (-not $RemoteCampaignDir.EndsWith("/$CampaignName"))) {
    throw 'RemoteCampaignDir must be the absolute directory for this exact array ID.'
}

$Target = Join-Path $Destination $CampaignName
if (Test-Path -LiteralPath $Target) {
    throw "Destination already exists: $Target. Preserve it and choose another -Destination."
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
& scp -r "${Remote}:${RemoteCampaignDir}" $Destination
if ($LASTEXITCODE -ne 0) {
    throw "Campaign download failed; partial data may remain at $Target."
}
if (-not (Test-Path -LiteralPath $Target -PathType Container)) {
    throw "SCP did not create the expected campaign directory: $Target"
}

$PlanPath = Join-Path $Target 'campaign_plan.json'
if (-not (Test-Path -LiteralPath $PlanPath -PathType Leaf)) {
    throw 'Campaign plan is missing.'
}
$Plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
if ($Plan.schema -ne 'islandsea-er4-best-athena-campaign-v1' -or
    $Plan.campaign -ne 'er4_best' -or
    [string]$Plan.array_job_id -ne $ArrayJobId -or
    $Plan.benchmark_count -ne 40 -or $Plan.repeat_count -ne 3 -or
    $Plan.task_count -ne 120 -or @($Plan.tasks).Count -ne 120 -or
    $Plan.configuration.dimension -ne 200 -or
    $Plan.configuration.islands -ne 144 -or
    $Plan.configuration.evaluations_per_island -ne 8000 -or
    $Plan.configuration.migration.selection -ne 'best' -or
    $Plan.configuration.migration.acceptance -ne 'plain' -or
    $Plan.configuration.topology.name -ne 'er4' -or
    $Plan.configuration.topology.adjacency_sha256 -ne '469cc283543dcc60d5bf8f07db2eabfb12cab34637f4a6d26bca51d07f85cccc') {
    throw 'Campaign plan does not match the approved Athena ER4/best 120-task study.'
}

$SeenBenchmarks = @{}
$SeenJobIds = @{}
$VerifiedRuns = @()
for ($i = 0; $i -lt 120; $i++) {
    $Task = $Plan.tasks[$i]
    $TaskId = $i + 1
    $ExpectedRepeat = ($i % 3) + 1
    if ($Task.task_id -ne $TaskId -or $Task.repeat -ne $ExpectedRepeat -or
        $Task.dimension -ne 200 -or [string]$Task.benchmark -notmatch '^[rb][0-9]{2}_[A-Za-z0-9_]+$') {
        throw "Invalid campaign task matrix at task $TaskId."
    }
    $Benchmark = [string]$Task.benchmark
    if (-not $SeenBenchmarks.ContainsKey($Benchmark)) { $SeenBenchmarks[$Benchmark] = 0 }
    $SeenBenchmarks[$Benchmark]++
    $RecordPath = Join-Path $Target ('tasks/task-{0:D3}.json' -f $TaskId)
    if (-not (Test-Path -LiteralPath $RecordPath -PathType Leaf)) {
        throw "Missing completed task record: $RecordPath"
    }
    $Record = Get-Content -LiteralPath $RecordPath -Raw | ConvertFrom-Json
    if ($Record.schema -ne $Plan.schema -or $Record.status -ne 'completed' -or
        [string]$Record.array_job_id -ne $ArrayJobId -or
        $Record.task_id -ne $TaskId -or $Record.benchmark -ne $Benchmark -or
        $Record.dimension -ne 200 -or $Record.repeat -ne $ExpectedRepeat -or
        $Record.topology -ne 'er4' -or $Record.migrant_selection -ne 'best' -or
        $Record.migrant_acceptance -ne 'plain' -or
        $Record.bundle_complete -ne $true -or $Record.validation -ne 'passed' -or
        [string]$Record.git_commit -notmatch '^[0-9a-fA-F]{40}$') {
        throw "Task record $TaskId does not match its plan or scientific validation."
    }
    $JobId = [string]$Record.job_id
    if ($JobId -notmatch '^[0-9]+$' -or $SeenJobIds.ContainsKey($JobId)) {
        throw "Invalid or duplicate SLURM job ID in task $TaskId."
    }
    $SeenJobIds[$JobId] = $true
    $ExpectedArchive = "runs/$Benchmark/repeat-$ExpectedRepeat/run_$JobId.tar.gz"
    if ([string]$Record.archive -ne $ExpectedArchive -or
        [string]$Record.archive_sha256 -notmatch '^[0-9a-fA-F]{64}$') {
        throw "Unsafe or incorrect archive mapping in task $TaskId."
    }
    $Archive = Join-Path $Target ($ExpectedArchive -replace '/', [IO.Path]::DirectorySeparatorChar)
    $Checksum = "$Archive.sha256"
    if (-not (Test-Path -LiteralPath $Archive -PathType Leaf) -or
        -not (Test-Path -LiteralPath $Checksum -PathType Leaf)) {
        throw "Archive or checksum is missing for task $TaskId."
    }
    $Fields = (Get-Content -LiteralPath $Checksum -Raw).Trim() -split '\s+'
    if ($Fields.Count -ne 2 -or $Fields[1] -ne "run_$JobId.tar.gz" -or
        $Fields[0] -ne [string]$Record.archive_sha256) {
        throw "Checksum record differs for task $TaskId."
    }
    $Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash
    if ($Actual -ne [string]$Record.archive_sha256) {
        throw "Archive SHA-256 mismatch for task $TaskId."
    }
    $VerifiedRuns += [pscustomobject]@{
        task_id = $TaskId
        job_id = $JobId
        benchmark = $Benchmark
        repeat = $ExpectedRepeat
        archive = $ExpectedArchive
        archive_sha256 = [string]$Record.archive_sha256
        git_commit = [string]$Record.git_commit
    }
}
if ($SeenBenchmarks.Count -ne 40 -or @($SeenBenchmarks.Values | Where-Object { $_ -ne 3 }).Count -ne 0) {
    throw 'The campaign does not contain three repeats of each of 40 benchmarks.'
}
if (@(Get-ChildItem -LiteralPath (Join-Path $Target 'runs') -Recurse -File -Filter 'run_*.tar.gz').Count -ne 120) {
    throw 'The campaign does not contain exactly 120 run archives.'
}
$Summary = [ordered]@{
    schema = 'islandsea-er4-best-athena-download-v1'
    verification_source = 'local-download'
    checked_utc = [DateTime]::UtcNow.ToString('o')
    array_job_id = $ArrayJobId
    valid = $true
    expected_runs = 120
    valid_runs = 120
    git_commits_observed = @($VerifiedRuns.git_commit | Sort-Object -Unique)
    runs = $VerifiedRuns
}
$SummaryPath = Join-Path $Target 'campaign_summary.json'
$SummaryJson = $Summary | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText($SummaryPath, "$SummaryJson`n", (New-Object Text.UTF8Encoding($false)))
Write-Host "ATHENA_ER4_BEST_VALID_RUNS=120"
Write-Host "ATHENA_ER4_BEST_DOWNLOAD_OK=$Target"
