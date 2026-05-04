# Phase 2: Ingestion Implementation

## Current Status Snapshot (2026-03-14)
- Dedicated source datasets currently available:
  - `data/datasets/elakiri_comments.csv`: 10,552 comments
  - `data/datasets/gossip_lanka_comments.csv`: 12,810 comments
  - `data/datasets/youtube_comments.csv`: 13,337 comments
- Resume/dedup behavior is active for all dedicated scrapers via state files under `data_collection/state/`.
- Current focus: Phase 3 annotation and adjudication using the frozen snapshot.

## Implemented
- Unified ingestion entrypoint: `python -m data_collection.run_ingestion`
- Source adapters:
  - `YouTubeAdapter`
  - `GossipLankaAdapter`
  - `ElakiriAdapter`
- Shared normalization and HTML text extraction utilities.
- Record validation + deduplication.
- Run manifest generation with source counts and drop statistics.

## Config Path
- Legacy Phase 2 `live_*` ingestion configs were removed after scraper pipeline hardening.
- Active configs are source seed/targets under `data_collection/configs/`.

## Output Contract
Each ingestion run writes:
- `records.jsonl`
- `records.csv`
- `manifest.json`

## Current Adapter Input Modes
- YouTube: CSV (`input_csv`) or YouTube Data API comments (`video_ids` + `api_key`)
- Gossip Lanka: JSON or CSV (`input_json` or `input_csv`)
- Elakiri: JSON or CSV (`input_json` or `input_csv`)
- All sources additionally support live URL mode via `urls` or `urls_file`.
- Gossip Lanka and Elakiri support crawl mode: `crawl=true`, `max_pages`, `allowed_domains`, `include_url_regex`.

## Live Run Verification
- Command:
  - `python -m data_collection.run_ingestion --config <your_phase2_config.json>`
- Verified run id: `ingest_20260313_201930`
- Source coverage in manifest:
  - youtube: 1
  - gossip_lanka: 1
  - elakiri: 1
- Records written to:
  - `data_collection/output/ingest_20260313_201930/`

## Real Crawl Verification (all 3 sources)
- Command:
  - `python -m data_collection.run_ingestion --config <your_phase2_config.json>`
- Verified run id: `ingest_20260313_205009`
- Source coverage in manifest:
  - youtube: 1
  - gossip_lanka: 42
  - elakiri: 16
- Records written to:
  - `data_collection/output/ingest_20260313_205009/`

## Target Tracking
- Use:
  - `python -m data_collection.progress_report --tier minimum`
- This compares collected raw counts against tier targets from `collection_targets.json`.

## Annotation Queue Build
- Use:
  - `python -m data_collection.build_annotation_queue --sinhala-only`
- Output:
  - `data/annotation_queue/raw_candidates.csv`
- Example run-specific queue:
  - `python -m data_collection.build_annotation_queue --run-ids ingest_20260313_205009 --sinhala-only --target data/annotation_queue/raw_candidates_run_205009.csv`

## Strict Comment-Only Mode
- Implemented through the dedicated source comment scrapers (`elakiri`, `gossip_lanka`, `youtube`).

## Next Extension (Phase 2.1)
- Add HTTP retry/backoff and robots/rate-limit controls per source.
- Add richer metadata (`source_url`, `language`, `collector_version`, `raw_payload_ref`).

## Exit Criteria to Close Phase 2
- YouTube dedicated dataset reaches agreed threshold for this cycle.
- One final verification pass confirms:
  - source-specific CSV integrity (no malformed rows)
  - resume-safe rerun behavior
  - comment-only content quality spot-check
- Freeze a Phase 2 dataset snapshot for Phase 3 labeling kickoff.

## Phase 2 Exit Evidence
- Frozen snapshot created:
  - `data/datasets/frozen/freeze_20260314_114841/`
- Snapshot source row counts:
  - elakiri: 10,552
  - gossip_lanka: 12,810
  - youtube: 13,337
