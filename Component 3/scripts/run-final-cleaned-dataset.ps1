param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [string]$RunId = "",
    [string]$ElakiriPath = "",
    [string]$GossipPath = "",
    [string]$YouTubePath = "",
    [double]$SinhalaThreshold = 0.2,
    [int]$MinTextChars = 8,
    [int]$MaxTextChars = 1200,
    [string]$OutputCsv = "",
    [string]$SummaryPath = "",
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
} else {
    $py = "python"
}

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = (Get-Date).ToString("preprocess_yyyyMMdd_HHmmss")
}

$runDir = Join-Path $ProjectRoot "datasets\preprocessing\runs\$RunId"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

if ([string]::IsNullOrWhiteSpace($OutputCsv)) {
    $OutputCsv = Join-Path $runDir "final_cleaned_dataset.csv"
} elseif (-not [System.IO.Path]::IsPathRooted($OutputCsv)) {
    $OutputCsv = Join-Path $ProjectRoot $OutputCsv
}

if ([string]::IsNullOrWhiteSpace($SummaryPath)) {
    $SummaryPath = Join-Path $runDir "final_cleaned_dataset_summary.json"
} elseif (-not [System.IO.Path]::IsPathRooted($SummaryPath)) {
    $SummaryPath = Join-Path $ProjectRoot $SummaryPath
}

if ([string]::IsNullOrWhiteSpace($ElakiriPath)) {
    $ElakiriPath = Join-Path $ProjectRoot "datasets\sources\elakiri_comments.csv"
} elseif (-not [System.IO.Path]::IsPathRooted($ElakiriPath)) {
    $ElakiriPath = Join-Path $ProjectRoot $ElakiriPath
}

if ([string]::IsNullOrWhiteSpace($GossipPath)) {
    $GossipPath = Join-Path $ProjectRoot "datasets\sources\gossip_lanka_comments.csv"
} elseif (-not [System.IO.Path]::IsPathRooted($GossipPath)) {
    $GossipPath = Join-Path $ProjectRoot $GossipPath
}

if ([string]::IsNullOrWhiteSpace($YouTubePath)) {
    $YouTubePath = Join-Path $ProjectRoot "datasets\sources\youtube_comments.csv"
} elseif (-not [System.IO.Path]::IsPathRooted($YouTubePath)) {
    $YouTubePath = Join-Path $ProjectRoot $YouTubePath
}

Write-Host "[final-cleaned] project_root=$ProjectRoot"
Write-Host "[final-cleaned] run_id=$RunId"
Write-Host "[final-cleaned] output_csv=$OutputCsv"
Write-Host "[final-cleaned] summary_path=$SummaryPath"
Write-Host "[final-cleaned] sources=[$ElakiriPath, $GossipPath, $YouTubePath]"

& $py -m data_collection.pipelines.build_final_cleaned_dataset `
    --elakiri-path $ElakiriPath `
    --gossip-path $GossipPath `
    --youtube-path $YouTubePath `
    --sinhala-threshold $SinhalaThreshold `
    --min-text-chars $MinTextChars `
    --max-text-chars $MaxTextChars `
    --output-csv $OutputCsv `
    --summary-path $SummaryPath
if ($LASTEXITCODE -ne 0) {
    throw "build_final_cleaned_dataset failed with exit code $LASTEXITCODE"
}

if ($UpdateCurrent) {
    $currentCsv = Join-Path $ProjectRoot "datasets\preprocessing\final_cleaned_dataset.csv"
    $currentSummary = Join-Path $ProjectRoot "datasets\preprocessing\final_cleaned_dataset_summary.json"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $currentCsv) | Out-Null
    Copy-Item -Force $OutputCsv $currentCsv
    Copy-Item -Force $SummaryPath $currentSummary
    Write-Host "[final-cleaned] updated current dataset: $currentCsv"
}
