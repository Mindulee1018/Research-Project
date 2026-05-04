import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from data_collection.io_utils import ensure_dir, write_csv, write_json, write_jsonl
from data_collection.models import IngestedRecord, SourceRecord
from data_collection.normalize import clean_text, is_likely_sinhala
from data_collection.sources.elakiri import ElakiriAdapter
from data_collection.sources.gossip_lanka import GossipLankaAdapter
from data_collection.sources.youtube import YouTubeAdapter
from data_collection.validators import deduplicate, validate_record


ADAPTERS = {
    "youtube": YouTubeAdapter(),
    "gossip_lanka": GossipLankaAdapter(),
    "elakiri": ElakiriAdapter(),
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_record_id(source: str, source_item_id_or_url: str, clean: str) -> str:
    payload = f"{source}|{source_item_id_or_url}|{clean}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _to_ingested(
    *,
    run_id: str,
    source: str,
    item: SourceRecord,
    scraped_at: str,
) -> IngestedRecord:
    cleaned = clean_text(item.raw_text)
    return IngestedRecord(
        record_id=_build_record_id(source, item.source_item_id_or_url, cleaned),
        run_id=run_id,
        source=source,
        source_item_id_or_url=item.source_item_id_or_url,
        scraped_at=scraped_at,
        published_at=item.published_at,
        author_id=item.author_id,
        raw_text=item.raw_text,
        clean_text=cleaned,
        is_sinhala=is_likely_sinhala(cleaned),
        metadata=item.metadata,
    )


def _resolve_run_id(run_id: str | None) -> str:
    if run_id:
        return run_id
    return "ingest_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def run_ingestion(config: Dict, run_id: str | None = None) -> Dict:
    started_at = _utc_now_iso()
    resolved_run_id = _resolve_run_id(run_id)

    output_dir = Path(config.get("output_dir", "data_collection/output")).resolve()
    run_dir = output_dir / resolved_run_id
    ensure_dir(run_dir)

    sources_config = dict(config.get("sources", {}))
    if not sources_config:
        raise ValueError("Config must define at least one source under 'sources'.")

    source_counts: Dict[str, int] = {}
    raw_records: List[IngestedRecord] = []
    invalid_records = 0

    for source_name, source_conf_raw in sources_config.items():
        if source_name not in ADAPTERS:
            raise ValueError(f"Unsupported source in config: {source_name}")
        source_conf = dict(source_conf_raw or {})
        if source_conf.get("enabled", True) is False:
            continue

        source_conf.setdefault("base_dir", str(Path(".").resolve()))
        scraped_at = _utc_now_iso()
        adapter = ADAPTERS[source_name]
        items = adapter.load(source_conf)
        source_counts[source_name] = len(items)

        for item in items:
            record = _to_ingested(
                run_id=resolved_run_id,
                source=source_name,
                item=item,
                scraped_at=scraped_at,
            )
            is_valid, _ = validate_record(record)
            if not is_valid:
                invalid_records += 1
                continue
            raw_records.append(record)

    deduped_records, dedup_dropped = deduplicate(raw_records)

    records_jsonl_path = run_dir / "records.jsonl"
    records_csv_path = run_dir / "records.csv"
    manifest_path = run_dir / "manifest.json"

    write_jsonl(records_jsonl_path, deduped_records)
    write_csv(records_csv_path, deduped_records)

    completed_at = _utc_now_iso()
    manifest = {
        "run_id": resolved_run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "source_counts": source_counts,
        "total_records_before_validation": len(raw_records) + invalid_records,
        "invalid_records_dropped": invalid_records,
        "dedup_records_dropped": dedup_dropped,
        "total_records_after_dedup": len(deduped_records),
        "output_files": {
            "records_jsonl": str(records_jsonl_path),
            "records_csv": str(records_csv_path),
        },
    }
    write_json(manifest_path, manifest)

    return {
        "run_dir": str(run_dir),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
    }

