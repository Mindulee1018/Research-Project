param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [string]$InputCsv = "",
    [string]$OutputCsv = "",
    [string]$StateFile = "",
    [string]$ReportOut = "",
    [string]$CredentialsPath = "credentials.json",
    [string]$ProjectId = "",
    [string]$Location = "us-central1",
    [string]$Model = "gemini-2.5-flash-lite",
    [int]$MaxRows = 0,
    [int]$SleepMs = 100,
    [int]$Workers = 6,
    [double]$ManualReviewThreshold = 0.70,
    [switch]$ForceRerun
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

function Get-LatestRunRoot {
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

if ([string]::IsNullOrWhiteSpace($InputCsv)) {
    $runRoot = Get-LatestRunRoot -BaseRoot $ProjectRoot
    $InputCsv = Join-Path $runRoot "reports\error_cases\error_cases_all.csv"
}
if ([string]::IsNullOrWhiteSpace($OutputCsv)) {
    $OutputCsv = Join-Path (Split-Path $InputCsv -Parent) "error_cases_gemini_relabel.csv"
}
if ([string]::IsNullOrWhiteSpace($StateFile)) {
    $StateFile = Join-Path (Split-Path $InputCsv -Parent) "error_cases_gemini_relabel_state.json"
}
if ([string]::IsNullOrWhiteSpace($ReportOut)) {
    $ReportOut = Join-Path (Split-Path $InputCsv -Parent) "error_cases_gemini_relabel_report.json"
}

if (-not [System.IO.Path]::IsPathRooted($CredentialsPath)) {
    $CredentialsPath = Join-Path $ProjectRoot $CredentialsPath
}
if ((-not (Test-Path $CredentialsPath)) -and ($CredentialsPath -eq (Join-Path $ProjectRoot "credentials.json")) -and (Test-Path (Join-Path $ProjectRoot "credential.json"))) {
    $CredentialsPath = Join-Path $ProjectRoot "credential.json"
}

if ([string]::IsNullOrWhiteSpace($ProjectId) -and -not [string]::IsNullOrWhiteSpace($env:GCP_PROJECT_ID)) {
    $ProjectId = $env:GCP_PROJECT_ID
}
if ([string]::IsNullOrWhiteSpace($ProjectId) -and (Test-Path $CredentialsPath)) {
    try {
        $credJson = Get-Content $CredentialsPath -Raw | ConvertFrom-Json
        if (($credJson -isnot [System.Array]) -and (-not [string]::IsNullOrWhiteSpace($credJson.project_id))) {
            $ProjectId = $credJson.project_id
        }
    } catch {
        Write-Warning "Could not parse project_id from credential file: $CredentialsPath"
    }
}

Write-Host "[error-relabel] Config: model=$Model workers=$Workers sleep_ms=$SleepMs max_rows=$MaxRows threshold=$ManualReviewThreshold"
Write-Host "[error-relabel] Project root: $ProjectRoot"
Write-Host "[error-relabel] Input: $InputCsv"
Write-Host "[error-relabel] Output: $OutputCsv"
Write-Host "[error-relabel] State: $StateFile"

$argsList = @(
    "-m", "data_collection.pipelines.relabel_error_cases_with_gemini",
    "--input-csv", $InputCsv,
    "--output-csv", $OutputCsv,
    "--state-file", $StateFile,
    "--report-out", $ReportOut,
    "--credentials-path", $CredentialsPath,
    "--location", $Location,
    "--model", $Model,
    "--max-rows", "$MaxRows",
    "--sleep-ms", "$SleepMs",
    "--workers", "$Workers",
    "--manual-review-threshold", "$ManualReviewThreshold"
)

if (-not [string]::IsNullOrWhiteSpace($ProjectId)) {
    $argsList += @("--project-id", $ProjectId)
}
if ($ForceRerun) {
    $argsList += "--force-rerun"
}

& $py @argsList
if ($LASTEXITCODE -ne 0) {
    throw "relabel_error_cases_with_gemini failed with exit code $LASTEXITCODE"
}
