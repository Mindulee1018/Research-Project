param(
    [string]$ProjectRoot = "D:\client-projects\sl-social-media-risk-analysis",
    [string]$RunId = "",
    [double]$SinhalaThreshold = 0.2,
    [int]$MinTextChars = 8,
    [int]$MaxTextChars = 1200,
    [double]$HoldoutRatio = 0.15,
    [switch]$UpdateCurrent = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = (Get-Date).ToString("preprocess_yyyyMMdd_HHmmss")
}

$cleanedOutput = Join-Path $ProjectRoot "datasets\preprocessing\runs\$RunId\final_cleaned_dataset.csv"
$cleanedSummary = Join-Path $ProjectRoot "datasets\preprocessing\runs\$RunId\final_cleaned_dataset_summary.json"
$workflowOutputDir = Join-Path $ProjectRoot "annotation\workflow\runs\$RunId"
$splitOutputDir = Join-Path $ProjectRoot "datasets\splits\runs\$RunId"

Write-Host "[preprocess-v2] project_root=$ProjectRoot"
Write-Host "[preprocess-v2] run_id=$RunId"
Write-Host "[preprocess-v2] Building final cleaned dataset..."
$finalScript = Join-Path $PSScriptRoot "run-final-cleaned-dataset.ps1"
& $finalScript `
    -ProjectRoot $ProjectRoot `
    -RunId $RunId `
    -SinhalaThreshold $SinhalaThreshold `
    -MinTextChars $MinTextChars `
    -MaxTextChars $MaxTextChars `
    -OutputCsv $cleanedOutput `
    -SummaryPath $cleanedSummary `
    -UpdateCurrent:$UpdateCurrent

Write-Host "[preprocess-v2] Refreshing labeling workflow + locked holdout..."
$refreshScript = Join-Path $PSScriptRoot "run-refresh-labeling-with-holdout.ps1"
& $refreshScript `
    -ProjectRoot $ProjectRoot `
    -RunId $RunId `
    -InputCsv $cleanedOutput `
    -OutputDir $workflowOutputDir `
    -SplitDir $splitOutputDir `
    -HoldoutRatio $HoldoutRatio `
    -PreserveExistingHoldout `
    -UpdateCurrent:$UpdateCurrent

Write-Host "[preprocess-v2] Done."
