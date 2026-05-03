# Data Collection

Phase 2 ingestion implementation lives here.

## Current Progress (2026-03-14)
- `elakiri_comments.csv`: 10,552 rows
- `gossip_lanka_comments.csv`: 12,810 rows
- `youtube_comments.csv`: 13,337 rows

## Mandatory Sources
- `sources/youtube/`
- `sources/gossip_lanka/`
- `sources/elakiri/`

## Run Ingestion
Run Elakiri from a fixed listing page range:

```powershell
./scripts/run-elakiri-comments-chunk.ps1 -ChunkSize 1000 -ListingStartPage 50 -ListingEndPage 30 -MaxThreadPages 2 -SleepMs 100
```

Run Gossip Lanka in fixed thread-range mode (no discovery expansion):

```powershell
./scripts/run-gossip-lanka-comments-chunk.ps1 -ChunkSize 500 -StartThread 420 -EndThread 520 -ThreadUrlTemplate 'https://www.gossiplankanews.com/2026/03/blog-post_{thread}.html'
```

Run Gossip Lanka in date-range mode using monthly archive routes:

```powershell
./scripts/run-gossip-lanka-comments-chunk.ps1 -ChunkSize 500 -DateFrom 2026-02 -DateTo 2026-03 -SleepMs 200
```

Default range mode filters discovered real article URLs by `blog-post_<id>` and avoids 404-heavy blind URL generation.
Use `--direct-thread-range` only if you explicitly want template-based URL expansion.

Run Gossip Lanka in chunk mode, for example `+500` rows per run:

```powershell
./scripts/run-gossip-lanka-comments-chunk.ps1 -ChunkSize 500
```

Run Elakiri in chunk mode, for example `+1000` rows per run:

```powershell
./scripts/run-elakiri-comments-chunk.ps1 -ChunkSize 1000
```

Run YouTube in chunk mode, for example `+500` rows per run:

```powershell
./scripts/run-youtube-comments-chunk.ps1 -ChunkSize 500
```

Build one final cleaned dataset directly from the three source CSVs:

```powershell
./scripts/run-final-cleaned-dataset.ps1 -SinhalaThreshold 0.2 -MinTextChars 8 -MaxTextChars 1200
```

Refresh labeling workflow while preserving existing labels and locking unseen holdout:

```powershell
./scripts/run-refresh-labeling-with-holdout.ps1
```

Outputs:
- `datasets/splits/current/train_dev_pool.csv`
- `datasets/splits/current/locked_unseen_holdout.csv`
- refreshed `annotation/workflow/current/*.csv` with existing labels prefilled

Auto-label annotation rows with Gemini (Vertex AI), resumable:

```powershell
./scripts/run-auto-label-gemini.ps1
```

To continue from where it stopped, run the same command again.
Use `-MaxRows <n>` only if you explicitly want chunked runs.
Use `-Workers <n>` to increase/decrease parallel labeling throughput (default 6).

YouTube chunk mode now enables related discovery by default to branch into fresh candidates from known Sinhala videos/channels:

```powershell
./scripts/run-youtube-comments-chunk.ps1 -ChunkSize 1000 -MaxVideos 150 -DiscoveryOverscanMultiplier 8 -RelatedFrontierSize 200 -MaxRelatedSeedVideos 120
```

If you want seed-only behavior, disable it:

```powershell
./scripts/run-youtube-comments-chunk.ps1 -ChunkSize 1000 -NoRelatedDiscovery
```

Track progress against target tier:

```powershell
python -m data_collection.progress_report --tier minimum
```

Build annotation queue from all runs:

```powershell
python -m data_collection.build_annotation_queue --sinhala-only
```

Build comment-only annotation queue from one run:

```powershell
python -m data_collection.build_annotation_queue --run-ids <run_id> --sinhala-only --comments-only --target data/annotation_queue/comment_candidates_<run_id>.csv
```

## Output
Each run writes to:

- `data_collection/output/<run_id>/records.jsonl`
- `data_collection/output/<run_id>/records.csv`
- `data_collection/output/<run_id>/manifest.json`

The manifest includes source coverage counts, validation/dedup drop counts, and output paths.

The dedicated Elakiri scraper writes to:

- `datasets/sources/elakiri_comments.csv`
- `datasets/runtime/state/elakiri_comments_state.json`
- `datasets/runtime/logs/elakiri_comments.log`
- `datasets/runtime/summaries/elakiri_comments_summary.json`

The dedicated Gossip Lanka scraper writes to:

- `datasets/sources/gossip_lanka_comments.csv`
- `datasets/runtime/state/gossip_lanka_comments_state.json`
- `datasets/runtime/logs/gossip_lanka_comments.log`
- `datasets/runtime/summaries/gossip_lanka_comments_summary.json`

The dedicated YouTube scraper writes to:

- `datasets/sources/youtube_comments.csv`
- `datasets/runtime/state/youtube_comments_state.json`
- `datasets/runtime/logs/youtube_comments.log`
- `datasets/runtime/summaries/youtube_comments_summary.json`

## Data Contract (per record)
- `source`
- `source_item_id_or_url`
- `scraped_at`
- `raw_text`
- `clean_text`
- `is_sinhala`
- `run_id`

## Source Adapter Modes
- File mode:
  - YouTube: `input_csv`
  - Gossip Lanka: `input_csv` or `input_json`
  - Elakiri: `input_csv` or `input_json`
- Live mode:
  - `urls` (inline list) or `urls_file` (text file, one URL per line)
  - `crawl: true` + `max_pages` for multi-page site crawl (Gossip Lanka / Elakiri)
  - YouTube API comments mode: `video_ids` + `api_key` (or env `YOUTUBE_API_KEY`)
