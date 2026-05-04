param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [int]$ChunkSize = 500,
    [int]$MaxVideos = 100,
    [int]$DiscoveryOverscanMultiplier = 5,
    [switch]$NoRelatedDiscovery,
    [int]$RelatedFrontierSize = 120,
    [int]$MaxRelatedSeedVideos = 80,
    [int]$MaxCommentsPerVideo = 300,
    [int]$MaxSeedPages = 20,
    [int]$SleepMs = 350,
    [double]$SinhalaThreshold = 0.2,
    [switch]$IncludeNonSinhala,
    [switch]$IgnoreResume
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

$datasetPath = Join-Path $ProjectRoot "datasets\sources\youtube_comments.csv"
$statePath = Join-Path $ProjectRoot "datasets\runtime\state\youtube_comments_state.json"
$logPath = Join-Path $ProjectRoot "datasets\runtime\logs\youtube_comments.log"
$summaryPath = Join-Path $ProjectRoot "datasets\runtime\summaries\youtube_comments_summary.json"
$currentRows = 0
if (Test-Path $datasetPath) {
    $currentRows = (Import-Csv $datasetPath | Measure-Object).Count
}

$targetRows = $currentRows + $ChunkSize

Write-Host "[youtube] Current rows: $currentRows"
Write-Host "[youtube] Requested additional rows: $ChunkSize"
Write-Host "[youtube] Target rows after this run: $targetRows"

$argsList = @(
    "-m", "data_collection.scrapers.youtube_comments_scraper",
    "--output-csv", "$datasetPath",
    "--state-path", "$statePath",
    "--log-path", "$logPath",
    "--summary-path", "$summaryPath",
    "--max-videos", "$MaxVideos",
    "--discovery-overscan-multiplier", "$DiscoveryOverscanMultiplier",
    "--max-comments-per-video", "$MaxCommentsPerVideo",
    "--max-seed-pages", "$MaxSeedPages",
    "--sleep-ms", "$SleepMs",
    "--sinhala-threshold", "$SinhalaThreshold",
    "--target-total-rows", "$targetRows"
)

if (-not $NoRelatedDiscovery) {
    $argsList += "--related-discovery"
    $argsList += "--related-frontier-size"
    $argsList += "$RelatedFrontierSize"
    $argsList += "--max-related-seed-videos"
    $argsList += "$MaxRelatedSeedVideos"
}
if ($IncludeNonSinhala) {
    $argsList += "--include-non-sinhala"
}
if ($IgnoreResume) {
    $argsList += "--ignore-resume"
}

& $py @argsList
if ($LASTEXITCODE -ne 0) {
    throw "youtube_comments_scraper failed with exit code $LASTEXITCODE"
}
