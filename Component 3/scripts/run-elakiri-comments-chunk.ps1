param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [int]$ChunkSize = 1000,
    [int]$ListingPages = 25,
    [int]$ListingStartPage = 0,
    [int]$ListingEndPage = 0,
    [int]$MaxThreadPages = 2,
    [int]$SleepMs = 100,
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

$datasetPath = Join-Path $ProjectRoot "datasets\sources\elakiri_comments.csv"
$statePath = Join-Path $ProjectRoot "datasets\runtime\state\elakiri_comments_state.json"
$logPath = Join-Path $ProjectRoot "datasets\runtime\logs\elakiri_comments.log"
$summaryPath = Join-Path $ProjectRoot "datasets\runtime\summaries\elakiri_comments_summary.json"
$currentRows = 0
if (Test-Path $datasetPath) {
    $currentRows = (Import-Csv $datasetPath | Measure-Object).Count
}

$targetRows = $currentRows + $ChunkSize

Write-Host "[elakiri] Current rows: $currentRows"
Write-Host "[elakiri] Chunk size: $ChunkSize"
Write-Host "[elakiri] Target rows after this run: $targetRows"

$argsList = @(
    "-m", "data_collection.scrapers.elakiri_comments_scraper",
    "--output-csv", "$datasetPath",
    "--state-path", "$statePath",
    "--log-path", "$logPath",
    "--summary-path", "$summaryPath",
    "--listing-pages", "$ListingPages",
    "--max-thread-pages", "$MaxThreadPages",
    "--sleep-ms", "$SleepMs",
    "--target-total-rows", "$targetRows"
)

if ($ListingStartPage -gt 0 -and $ListingEndPage -gt 0) {
    $argsList += "--listing-start-page"
    $argsList += "$ListingStartPage"
    $argsList += "--listing-end-page"
    $argsList += "$ListingEndPage"
}

if ($IncludeNonSinhala) {
    $argsList += "--include-non-sinhala"
}

& $py @argsList
if ($LASTEXITCODE -ne 0) {
    throw "elakiri_comments_scraper failed with exit code $LASTEXITCODE"
}
