param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [string]$InputCsv = "annotation/workflow/current/annotator_a.csv",
    [string]$OutputCsv = "annotation/workflow/current/annotator_a_llm.csv",
    [string]$StateFile = "annotation/workflow/state/gemini_label_state.json",
    [string]$ReportOut = "annotation/workflow/state/gemini_label_report.json",
    [string]$CredentialsPath = "credentials.json",
    [string]$ProjectId = "",
    [string]$Location = "us-central1",
    [string]$Model = "gemini-2.5-flash-lite",
    [int]$MaxRows = 0,
    [int]$SleepMs = 100,
    [int]$Workers = 6
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $repoRoot
} else {
    $env:PYTHONPATH = "$repoRoot;$($env:PYTHONPATH)"
}

if (-not [System.IO.Path]::IsPathRooted($InputCsv)) {
    $InputCsv = Join-Path $ProjectRoot $InputCsv
}
if (-not [System.IO.Path]::IsPathRooted($OutputCsv)) {
    $OutputCsv = Join-Path $ProjectRoot $OutputCsv
}
if (-not [System.IO.Path]::IsPathRooted($StateFile)) {
    $StateFile = Join-Path $ProjectRoot $StateFile
}
if (-not [System.IO.Path]::IsPathRooted($ReportOut)) {
    $ReportOut = Join-Path $ProjectRoot $ReportOut
}
if (-not [System.IO.Path]::IsPathRooted($CredentialsPath)) {
    $CredentialsPath = Join-Path $ProjectRoot $CredentialsPath
}

if (Test-Path ".venv\Scripts\python.exe") {
    $py = ".\.venv\Scripts\python.exe"
} elseif (Test-Path "venv\Scripts\python.exe") {
    $py = ".\venv\Scripts\python.exe"
} else {
    $py = "python"
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

# Resume is handled by Python via candidate_id merge from output CSV.
if (Test-Path $OutputCsv) {
    Write-Host "[auto-label] Resume source detected: $OutputCsv"
}

Write-Host "[auto-label] Config: model=$Model workers=$Workers sleep_ms=$SleepMs max_rows=$MaxRows"
Write-Host "[auto-label] Project root: $ProjectRoot"
Write-Host "[auto-label] Input: $InputCsv"
Write-Host "[auto-label] Output: $OutputCsv"
Write-Host "[auto-label] State: $StateFile"

$argsList = @(
    "-m", "data_collection.pipelines.auto_label_with_gemini",
    "--input-csv", $InputCsv,
    "--output-csv", $OutputCsv,
    "--state-file", $StateFile,
    "--report-out", $ReportOut,
    "--credentials-path", $CredentialsPath,
    "--location", $Location,
    "--model", $Model,
    "--max-rows", "$MaxRows",
    "--sleep-ms", "$SleepMs",
    "--workers", "$Workers"
)

if (-not [string]::IsNullOrWhiteSpace($ProjectId)) {
    $argsList += @("--project-id", $ProjectId)
}

& $py @argsList
if ($LASTEXITCODE -ne 0) {
    throw "auto_label_with_gemini failed with exit code $LASTEXITCODE"
}
