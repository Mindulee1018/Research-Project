param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [string]$MasterCsv = "annotation/workflow/current/annotator_a_llm.csv",
    [string]$RelabelsCsv = "",
    [string]$OutputCsv = "annotation/workflow/current/annotator_a_llm.csv",
    [string]$BackupCsv = "",
    [string]$ReportOut = "",
    [switch]$SkipManualReview,
    [switch]$ApplyKeep,
    [string]$ApprovedOnlyColumn = ""
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

if (-not [System.IO.Path]::IsPathRooted($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}

function Resolve-RunRoot {
    param([string]$BaseRoot)
    $latestRunFile = Join-Path $BaseRoot "training\artifacts\runs\latest_run.txt"
    if (-not (Test-Path $latestRunFile)) {
        throw "latest_run.txt not found: $latestRunFile"
    }
    $runRoot = (Get-Content $latestRunFile -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($runRoot)) {
        throw "latest_run.txt is empty: $latestRunFile"
    }
    return $runRoot
}

if (-not [System.IO.Path]::IsPathRooted($MasterCsv)) {
    $MasterCsv = Join-Path $ProjectRoot $MasterCsv
}
if ([string]::IsNullOrWhiteSpace($RelabelsCsv)) {
    $runRoot = Resolve-RunRoot -BaseRoot $ProjectRoot
    $RelabelsCsv = Join-Path $runRoot "reports\error_cases\error_cases_gemini_relabel.csv"
}
if (-not [System.IO.Path]::IsPathRooted($RelabelsCsv)) {
    $RelabelsCsv = Join-Path $ProjectRoot $RelabelsCsv
}
if (-not [System.IO.Path]::IsPathRooted($OutputCsv)) {
    $OutputCsv = Join-Path $ProjectRoot $OutputCsv
}
if ([string]::IsNullOrWhiteSpace($BackupCsv)) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $BackupCsv = Join-Path $ProjectRoot "annotation\workflow\state\annotator_a_llm.before_error_relabels_$stamp.csv"
}
if (-not [System.IO.Path]::IsPathRooted($BackupCsv)) {
    $BackupCsv = Join-Path $ProjectRoot $BackupCsv
}
if ([string]::IsNullOrWhiteSpace($ReportOut)) {
    $runRoot = Resolve-RunRoot -BaseRoot $ProjectRoot
    $ReportOut = Join-Path $runRoot "reports\error_cases\apply_error_relabels_report.json"
}
if (-not [System.IO.Path]::IsPathRooted($ReportOut)) {
    $ReportOut = Join-Path $ProjectRoot $ReportOut
}

Write-Host "[apply-error-relabels] Master: $MasterCsv"
Write-Host "[apply-error-relabels] Relabels: $RelabelsCsv"
Write-Host "[apply-error-relabels] Output: $OutputCsv"
Write-Host "[apply-error-relabels] Backup: $BackupCsv"
Write-Host "[apply-error-relabels] Report: $ReportOut"

$argsList = @(
    "-m", "data_collection.pipelines.apply_error_relabels",
    "--master-csv", $MasterCsv,
    "--relabels-csv", $RelabelsCsv,
    "--output-csv", $OutputCsv,
    "--backup-csv", $BackupCsv,
    "--report-out", $ReportOut
)

if ($SkipManualReview) {
    $argsList += "--skip-manual-review"
}
if ($ApplyKeep) {
    $argsList += "--apply-keep"
}
if (-not [string]::IsNullOrWhiteSpace($ApprovedOnlyColumn)) {
    $argsList += @("--approved-only-column", $ApprovedOnlyColumn)
}

& $py @argsList
if ($LASTEXITCODE -ne 0) {
    throw "apply_error_relabels failed with exit code $LASTEXITCODE"
}
