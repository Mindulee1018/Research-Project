param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [int]$ChunkSize = 500,
    [int]$MaxPages = 250,
    [int]$SleepMs = 250,
    [string]$DateFrom = "",
    [string]$DateTo = "",
    [int]$StartThread = 0,
    [int]$EndThread = 0,
    [string]$ThreadUrlTemplate = "https://www.gossiplankanews.com/2026/03/blog-post_{thread}.html",
    [switch]$IncludeNonSinhala
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

$datasetPath = Join-Path $ProjectRoot "datasets\sources\gossip_lanka_comments.csv"
$statePath = Join-Path $ProjectRoot "datasets\runtime\state\gossip_lanka_comments_state.json"
$logPath = Join-Path $ProjectRoot "datasets\runtime\logs\gossip_lanka_comments.log"
$summaryPath = Join-Path $ProjectRoot "datasets\runtime\summaries\gossip_lanka_comments_summary.json"
$currentRows = 0
if (Test-Path $datasetPath) {
    $currentRows = (Import-Csv $datasetPath | Measure-Object).Count
}

$targetRows = $currentRows + $ChunkSize

Write-Host "[gossip_lanka] Current rows: $currentRows"
Write-Host "[gossip_lanka] Chunk size: $ChunkSize"
Write-Host "[gossip_lanka] Target rows after this run: $targetRows"

$argsList = @(
    "-m", "data_collection.scrapers.gossip_lanka_comments_scraper",
    "--output-csv", "$datasetPath",
    "--state-path", "$statePath",
    "--log-path", "$logPath",
    "--summary-path", "$summaryPath",
    "--max-pages", "$MaxPages",
    "--sleep-ms", "$SleepMs",
    "--target-total-rows", "$targetRows"
)

if ($StartThread -gt 0 -and $EndThread -gt 0) {
    $argsList += "--start-thread"
    $argsList += "$StartThread"
    $argsList += "--end-thread"
    $argsList += "$EndThread"
    $argsList += "--thread-url-template"
    $argsList += "$ThreadUrlTemplate"
}

if ($DateFrom -ne "" -and $DateTo -ne "") {
    $argsList += "--date-from"
    $argsList += "$DateFrom"
    $argsList += "--date-to"
    $argsList += "$DateTo"
}

if ($IncludeNonSinhala) {
    $argsList += "--include-non-sinhala"
}

& $py @argsList
if ($LASTEXITCODE -ne 0) {
    throw "gossip_lanka_comments_scraper failed with exit code $LASTEXITCODE"
}
