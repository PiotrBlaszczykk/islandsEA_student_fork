param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+$')]
    [string]$ArrayJobId,
    [string]$Remote = 'plgblaszczykk@athena.cyfronet.pl',
    [string]$RemoteCampaignDir = '',
    [string]$Destination = '',
    [switch]$Extract
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
    -not $RemoteCampaignDir.EndsWith("/$CampaignName")) {
    throw 'RemoteCampaignDir must be the absolute directory for this exact array ID.'
}

$Archive = Join-Path $Destination "$CampaignName.tar.gz"
$Checksum = "$Archive.sha256"
$Directory = Join-Path $Destination $CampaignName
foreach ($path in @($Archive, $Checksum)) {
    if (Test-Path -LiteralPath $path) {
        throw "Destination already exists: $path. Preserve it and choose another -Destination."
    }
}
if ($Extract -and (Test-Path -LiteralPath $Directory)) {
    throw "Destination already exists: $Directory. Preserve it and choose another -Destination."
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null

# One remote wildcard is one scp connection/password prompt for the two files.
& scp "${Remote}:${RemoteCampaignDir}/${CampaignName}.tar.gz*" $Destination
if ($LASTEXITCODE -ne 0) {
    throw 'Campaign download failed; inspect partial files before retrying.'
}
if (-not (Test-Path -LiteralPath $Archive -PathType Leaf) -or
    -not (Test-Path -LiteralPath $Checksum -PathType Leaf)) {
    throw 'Campaign archive or checksum is missing after scp.'
}
$fields = (Get-Content -LiteralPath $Checksum -Raw).Trim() -split '\s+'
if ($fields.Count -ne 2 -or $fields[1] -ne "$CampaignName.tar.gz" -or
    $fields[0] -notmatch '^[0-9a-fA-F]{64}$') {
    throw 'Malformed campaign checksum.'
}
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash
if ($actual -ne $fields[0]) {
    throw 'Campaign SHA-256 mismatch. Do not extract.'
}
Write-Host "ATHENA_ER4_BEST_SHA256_OK=$Archive"

if ($Extract) {
    $members = @(& tar -tf $Archive)
    if ($LASTEXITCODE -ne 0) { throw 'Could not list campaign archive.' }
    if ($members.Count -eq 0 -or @($members | Where-Object {
        $_ -notlike "$CampaignName/*" -or $_ -match '(^|/)\.\.(/|$)' -or $_ -match '\\'
    }).Count -ne 0) {
        throw 'Unsafe or unexpected campaign archive root.'
    }
    & tar -xzf $Archive -C $Destination
    if ($LASTEXITCODE -ne 0) { throw 'Campaign extraction failed.' }
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
        throw 'Campaign directory is missing after extraction.'
    }

    $PlanPath = Join-Path $Directory 'campaign_plan.json'
    $SummaryPath = Join-Path $Directory 'campaign_summary.json'
    if (-not (Test-Path -LiteralPath $PlanPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $SummaryPath -PathType Leaf)) {
        throw 'Campaign plan or summary is missing after extraction.'
    }
    $Plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
    $Summary = Get-Content -LiteralPath $SummaryPath -Raw | ConvertFrom-Json
    if ($Plan.schema -ne 'islandsea-er4-best-athena-campaign-v1' -or
        $Plan.campaign -ne 'er4_best' -or [string]$Plan.array_job_id -ne $ArrayJobId -or
        $Plan.task_count -ne 120 -or $Plan.benchmark_count -ne 40 -or
        $Plan.repeat_count -ne 3 -or @($Plan.tasks).Count -ne 120 -or
        $Plan.configuration.dimension -ne 200 -or
        $Plan.configuration.islands -ne 144 -or
        $Plan.configuration.topology.name -ne 'er4' -or
        $Plan.configuration.topology.adjacency_sha256 -ne '469cc283543dcc60d5bf8f07db2eabfb12cab34637f4a6d26bca51d07f85cccc' -or
        $Plan.configuration.migration.selection -ne 'best' -or
        $Plan.configuration.migration.acceptance -ne 'plain') {
        throw 'Campaign plan differs from the approved ER4/best study.'
    }
    if ($Summary.schema -ne $Plan.schema -or $Summary.campaign -ne 'er4_best' -or
        [string]$Summary.array_job_id -ne $ArrayJobId -or $Summary.valid -ne $true -or
        @($Summary.errors).Count -ne 0 -or $Summary.expected_runs -ne 120 -or
        $Summary.valid_runs -ne 120 -or @($Summary.runs).Count -ne 120) {
        throw 'Campaign summary does not certify 120 valid runs.'
    }

    $runsRoot = Join-Path $Directory 'runs'
    $recordsRoot = Join-Path $Directory 'tasks'
    $validationsRoot = Join-Path $Directory 'validations'
    if (-not (Test-Path -LiteralPath $runsRoot -PathType Container) -or
        -not (Test-Path -LiteralPath $recordsRoot -PathType Container) -or
        -not (Test-Path -LiteralPath $validationsRoot -PathType Container)) {
        throw 'Campaign runs, task records or validations are missing.'
    }
    $nested = @(Get-ChildItem -LiteralPath $runsRoot -Recurse -File -Filter 'run_*.tar.gz')
    $nestedChecksums = @(Get-ChildItem -LiteralPath $runsRoot -Recurse -File -Filter 'run_*.tar.gz.sha256')
    $recordFiles = @(Get-ChildItem -LiteralPath $recordsRoot -File -Filter 'task-*.json')
    $validationFiles = @(Get-ChildItem -LiteralPath $validationsRoot -File -Filter 'task-*.json')
    if ($nested.Count -ne 120 -or $nestedChecksums.Count -ne 120 -or
        $recordFiles.Count -ne 120 -or $validationFiles.Count -ne 120) {
        throw 'Campaign extraction does not have exactly 120 bundles, checksums, records and validations.'
    }
    $seenJobs = @{}
    $seenBenchmarks = @{}
    for ($i = 0; $i -lt 120; $i++) {
        $task = $Plan.tasks[$i]
        $entry = $Summary.runs[$i]
        $taskId = $i + 1
        $repeat = ($i % 3) + 1
        $benchmark = [string]$task.benchmark
        if ($task.task_id -ne $taskId -or $task.repeat -ne $repeat -or
            $benchmark -notmatch '^[rb][0-9]{2}_[A-Za-z0-9_]+$') {
            throw "Invalid campaign task matrix at task $taskId."
        }
        if (-not $seenBenchmarks.ContainsKey($benchmark)) { $seenBenchmarks[$benchmark] = 0 }
        $seenBenchmarks[$benchmark]++
        $recordPath = Join-Path $recordsRoot ('task-{0:D3}.json' -f $taskId)
        $validationPath = Join-Path $validationsRoot ('task-{0:D3}.json' -f $taskId)
        if (-not (Test-Path -LiteralPath $recordPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $validationPath -PathType Leaf)) {
            throw "Missing record or validation for task $taskId."
        }
        $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        $validation = Get-Content -LiteralPath $validationPath -Raw | ConvertFrom-Json
        $jobId = [string]$record.job_id
        if ($jobId -notmatch '^[0-9]+$' -or $seenJobs.ContainsKey($jobId)) {
            throw "Invalid or duplicate real SLURM job ID for task $taskId."
        }
        $seenJobs[$jobId] = $true
        $relative = "runs/$benchmark/repeat-$repeat/run_$jobId.tar.gz"
        if ($record.schema -ne $Plan.schema -or $record.status -ne 'completed' -or
            [string]$record.array_job_id -ne $ArrayJobId -or $record.task_id -ne $taskId -or
            $record.benchmark -ne $benchmark -or $record.repeat -ne $repeat -or
            $record.validation -ne 'passed' -or $record.bundle_complete -ne $true -or
            [string]$record.archive -ne $relative -or
            $entry.task_id -ne $taskId -or [string]$entry.job_id -ne $jobId -or
            $entry.benchmark -ne $benchmark -or $entry.repeat -ne $repeat -or
            [string]$entry.archive -ne $relative -or
            [string]$entry.archive_sha256 -ne [string]$record.archive_sha256 -or
            $validation.status -ne 'passed' -or $validation.valid -ne $true -or
            @($validation.errors).Count -ne 0 -or $validation.benchmark -ne $benchmark -or
            $validation.repeat -ne $repeat) {
            throw "Record, summary or scientific validation mismatch for task $taskId."
        }
        $nestedPath = Join-Path $Directory ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        $nestedChecksum = "$nestedPath.sha256"
        if (-not (Test-Path -LiteralPath $nestedPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $nestedChecksum -PathType Leaf)) {
            throw "Missing nested archive or checksum for task $taskId."
        }
        $innerFields = (Get-Content -LiteralPath $nestedChecksum -Raw).Trim() -split '\s+'
        if ($innerFields.Count -ne 2 -or $innerFields[1] -ne "run_$jobId.tar.gz" -or
            $innerFields[0] -notmatch '^[0-9a-fA-F]{64}$' -or
            $innerFields[0] -ne [string]$record.archive_sha256) {
            throw "Malformed nested checksum for task $taskId."
        }
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $nestedPath).Hash -ne $innerFields[0]) {
            throw "Nested archive SHA-256 mismatch for task $taskId."
        }
    }
    if ($seenBenchmarks.Count -ne 40 -or
        @($seenBenchmarks.Values | Where-Object { $_ -ne 3 }).Count -ne 0) {
        throw 'Campaign is not exactly 40 benchmarks x three repeats.'
    }
    Write-Host 'ATHENA_ER4_BEST_NESTED_SHA256_OK=120'
    Write-Host "ATHENA_ER4_BEST_DIRECTORY=$Directory"
}
Write-Host "ATHENA_ER4_BEST_DOWNLOAD_OK=$Archive"
