param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [string]$RunId = "",
    [string]$InputCsv = "",
    [string[]]$ExistingLabelCsv = @("datasets/labeled/annotator_a_llm.csv"),
    [string]$OutputDir = "",
    [string]$SplitDir = "",
    [double]$HoldoutRatio = 0.15,
    [switch]$PreserveExistingHoldout = $true,
    [string]$ExistingHoldoutCsv = "",
    [switch]$UpdateCurrent = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $repoRoot
} else {
    $env:PYTHONPATH = "$repoRoot;$($env:PYTHONPATH)"
}

if (Test-Path ".venv\Scripts\python.exe") {
    $py = ".\.venv\Scripts\python.exe"
} elseif (Test-Path "venv\Scripts\python.exe") {
    $py = ".\venv\Scripts\python.exe"
} else {
    $py = "python"
}

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = (Get-Date).ToString("preprocess_yyyyMMdd_HHmmss")
}

if ([string]::IsNullOrWhiteSpace($InputCsv)) {
    $InputCsv = Join-Path $ProjectRoot "datasets\preprocessing\final_cleaned_dataset.csv"
} elseif (-not [System.IO.Path]::IsPathRooted($InputCsv)) {
    $InputCsv = Join-Path $ProjectRoot $InputCsv
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $ProjectRoot "annotation\workflow\runs\$RunId"
} elseif (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir = Join-Path $ProjectRoot $OutputDir
}

if ([string]::IsNullOrWhiteSpace($SplitDir)) {
    $SplitDir = Join-Path $ProjectRoot "datasets\splits\runs\$RunId"
} elseif (-not [System.IO.Path]::IsPathRooted($SplitDir)) {
    $SplitDir = Join-Path $ProjectRoot $SplitDir
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $SplitDir | Out-Null

$labelArgs = @()
foreach ($path in $ExistingLabelCsv) {
    if (-not [string]::IsNullOrWhiteSpace($path)) {
        $labelPath = $path
        if (-not [System.IO.Path]::IsPathRooted($labelPath)) {
            $labelPath = Join-Path $ProjectRoot $labelPath
        }
        $labelArgs += @("--existing-label-csv", $labelPath)
    }
}

if ([string]::IsNullOrWhiteSpace($ExistingHoldoutCsv)) {
    $ExistingHoldoutCsv = Join-Path $ProjectRoot "datasets\splits\current\locked_unseen_holdout.csv"
} elseif (-not [System.IO.Path]::IsPathRooted($ExistingHoldoutCsv)) {
    $ExistingHoldoutCsv = Join-Path $ProjectRoot $ExistingHoldoutCsv
}

$extraArgs = @()
if ($PreserveExistingHoldout) {
    $extraArgs += "--preserve-existing-holdout"
}

Write-Host "[refresh-holdout] project_root=$ProjectRoot"
Write-Host "[refresh-holdout] run_id=$RunId"
Write-Host "[refresh-holdout] input_csv=$InputCsv"
Write-Host "[refresh-holdout] output_dir=$OutputDir"
Write-Host "[refresh-holdout] split_dir=$SplitDir"

& $py -m data_collection.pipelines.refresh_labeling_with_locked_holdout `
    --input-csv $InputCsv `
    --output-dir $OutputDir `
    --split-dir $SplitDir `
    --holdout-ratio $HoldoutRatio `
    --existing-holdout-csv $ExistingHoldoutCsv `
    @extraArgs `
    @labelArgs
if ($LASTEXITCODE -ne 0) {
    throw "refresh_labeling_with_locked_holdout failed with exit code $LASTEXITCODE"
}

if ($UpdateCurrent) {
    $workflowCurrent = Join-Path $ProjectRoot "annotation\workflow\current"
    $splitCurrent = Join-Path $ProjectRoot "datasets\splits\current"
    New-Item -ItemType Directory -Force -Path $workflowCurrent | Out-Null
    New-Item -ItemType Directory -Force -Path $splitCurrent | Out-Null
    Copy-Item -Path (Join-Path $OutputDir "*") -Destination $workflowCurrent -Force -Recurse
    Copy-Item -Path (Join-Path $SplitDir "*") -Destination $splitCurrent -Force -Recurse
    Write-Host "[refresh-holdout] updated current workflow: $workflowCurrent"
    Write-Host "[refresh-holdout] updated current splits: $splitCurrent"
}
