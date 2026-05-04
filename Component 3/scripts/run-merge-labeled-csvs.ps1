param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [string]$MasterCsv = "annotation/workflow/current/annotator_a_llm.csv",
    [string]$IncomingCsv,
    [string]$OutputCsv = "annotation/workflow/current/annotator_a_llm.csv",
    [string]$BackupCsv = "",
    [string]$ReportOut = "",
    [switch]$PreferIncoming
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($IncomingCsv)) {
    throw "IncomingCsv is required."
}

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
if (-not [System.IO.Path]::IsPathRooted($MasterCsv)) {
    $MasterCsv = Join-Path $ProjectRoot $MasterCsv
}
if (-not [System.IO.Path]::IsPathRooted($IncomingCsv)) {
    $IncomingCsv = Join-Path $ProjectRoot $IncomingCsv
}
if (-not [System.IO.Path]::IsPathRooted($OutputCsv)) {
    $OutputCsv = Join-Path $ProjectRoot $OutputCsv
}
if ([string]::IsNullOrWhiteSpace($BackupCsv)) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $BackupCsv = Join-Path $ProjectRoot "annotation\workflow\state\annotator_a_llm.before_merge_$stamp.csv"
}
if (-not [System.IO.Path]::IsPathRooted($BackupCsv)) {
    $BackupCsv = Join-Path $ProjectRoot $BackupCsv
}
if ([string]::IsNullOrWhiteSpace($ReportOut)) {
    $ReportOut = Join-Path $ProjectRoot "annotation\workflow\state\merge_labeled_csvs_report.json"
}
if (-not [System.IO.Path]::IsPathRooted($ReportOut)) {
    $ReportOut = Join-Path $ProjectRoot $ReportOut
}

Write-Host "[merge-labeled-csvs] Master: $MasterCsv"
Write-Host "[merge-labeled-csvs] Incoming: $IncomingCsv"
Write-Host "[merge-labeled-csvs] Output: $OutputCsv"
Write-Host "[merge-labeled-csvs] Backup: $BackupCsv"
Write-Host "[merge-labeled-csvs] Report: $ReportOut"

$argsList = @(
    "-m", "data_collection.pipelines.merge_labeled_csvs",
    "--master-csv", $MasterCsv,
    "--incoming-csv", $IncomingCsv,
    "--output-csv", $OutputCsv,
    "--backup-csv", $BackupCsv,
    "--report-out", $ReportOut
)

if ($PreferIncoming) {
    $argsList += "--prefer-incoming"
}

& $py @argsList
if ($LASTEXITCODE -ne 0) {
    throw "merge_labeled_csvs failed with exit code $LASTEXITCODE"
}
