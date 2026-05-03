param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [string]$RunId = "",
    [string]$ModelSource = "",
    [string]$ReportsSource = "",
    [switch]$CopyOnly = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = (Get-Date).ToString("run_yyyyMMdd_HHmmss")
}

if ([string]::IsNullOrWhiteSpace($ModelSource)) {
    $ModelSource = Join-Path $ProjectRoot "training\artifacts\models_phase5_sbert"
}
if ([string]::IsNullOrWhiteSpace($ReportsSource)) {
    $ReportsSource = Join-Path $ProjectRoot "training\artifacts\reports_phase5_sbert"
}

$runsRoot = Join-Path $ProjectRoot "training\artifacts\runs"
$runRoot = Join-Path $runsRoot $RunId
$modelDest = Join-Path $runRoot "model"
$reportsDest = Join-Path $runRoot "reports"
$latestRun = Join-Path $runsRoot "latest_run.txt"

if (Test-Path $runRoot) {
    throw "Run folder already exists: $runRoot"
}

New-Item -ItemType Directory -Force -Path $runsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null

Write-Host "[migrate-artifacts] project_root=$ProjectRoot"
Write-Host "[migrate-artifacts] run_id=$RunId"

if (Test-Path $ModelSource) {
    if ($CopyOnly) {
        Copy-Item -Path $ModelSource -Destination $modelDest -Recurse -Force
        Write-Host "[migrate-artifacts] copied model folder -> $modelDest"
    } else {
        Move-Item -Path $ModelSource -Destination $modelDest -Force
        Write-Host "[migrate-artifacts] moved model folder -> $modelDest"
    }
} else {
    Write-Host "[migrate-artifacts] model source not found, skipped: $ModelSource"
}

if (Test-Path $ReportsSource) {
    if ($CopyOnly) {
        Copy-Item -Path $ReportsSource -Destination $reportsDest -Recurse -Force
        Write-Host "[migrate-artifacts] copied reports folder -> $reportsDest"
    } else {
        Move-Item -Path $ReportsSource -Destination $reportsDest -Force
        Write-Host "[migrate-artifacts] moved reports folder -> $reportsDest"
    }
} else {
    New-Item -ItemType Directory -Force -Path $reportsDest | Out-Null
    Write-Host "[migrate-artifacts] reports source not found, created empty: $reportsDest"
}

Set-Content -Path $latestRun -Value $runRoot -Encoding utf8
Write-Host "[migrate-artifacts] updated latest_run.txt -> $latestRun"
Write-Host "[migrate-artifacts] done"
