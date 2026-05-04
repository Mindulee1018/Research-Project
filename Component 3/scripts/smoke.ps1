Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "[smoke] Python syntax checks..."
if (Test-Path ".venv\Scripts\python.exe") {
    $py = ".\.venv\Scripts\python.exe"
} else {
    $py = "python"
}

& $py -m py_compile backend\main.py
& $py -m py_compile backend\app\service\moderation_service.py
& $py -m py_compile data_collection\run_ingestion.py
& $py -m py_compile data_collection\runner.py
& $py -m py_compile data_collection\progress_report.py
& $py -m py_compile data_collection\build_annotation_queue.py
& $py -m py_compile data_collection\scrapers\elakiri_comments_scraper.py

Write-Host "[smoke] Frontend lint..."
npm run lint --prefix frontend

Write-Host "[smoke] Smoke checks passed."
