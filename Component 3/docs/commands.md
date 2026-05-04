# Scrapper run 
### Make sure to update source URLS

./scripts/run-gossip-lanka-comments-chunk.ps1 -ChunkSize 20000 -DateFrom 2022-01 -DateTo 2024-01 -MaxPages 400 -SleepMs 250
./scripts/run-elakiri-comments-chunk.ps1 -ChunkSize 3050 -ListingPages 200 -MaxThreadPages 5 -SleepMs 100
./scripts/run-youtube-comments-chunk.ps1 -ChunkSize 10000 -MaxVideos 1000 -MaxCommentsPerVideo 1000

# Update final datasets with newly scrapped data
./scripts/run-preprocess-v2.ps1 -ProjectRoot "D:\client-projects\sl-social-media-risk-analysis"

# If artifacts were copied manually and need run-style naming
./scripts/run-migrate-artifacts-to-runs.ps1 -ProjectRoot "D:\client-projects\sl-social-media-risk-analysis"

# Run dataset labeling
./scripts/run-auto-label-gemini.ps1 -Workers 100 -SleepMs 0

# Benchmark backend latency + throughput (NFR evidence)
./scripts/run-api-benchmark.ps1 -BaseUrl "http://127.0.0.1:5000" -Requests 1000 -Workers 20 -OutputJson "evaluation/benchmarks/api_benchmark_run.json"
