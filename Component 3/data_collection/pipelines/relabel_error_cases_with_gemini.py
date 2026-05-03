import argparse
import concurrent.futures
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from data_collection.io_utils import ensure_dir
from data_collection.pipelines.auto_label_with_gemini import (
    build_token,
    build_vertex_endpoint,
    extract_json_from_text,
    load_credentials_payload,
    normalize_label,
    read_project_id_from_credentials,
    sanitize_cause_words,
)


VALID_ACTIONS = {"KEEP", "CHANGE"}
VALID_LABELS = {"HATE", "DISINFO", "NORMAL"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Relabel model error cases with Gemini (Vertex AI) using constrained adjudication."
    )
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--credentials-path", default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json"))
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", ""))
    parser.add_argument("--location", default=os.environ.get("GCP_LOCATION", "us-central1"))
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite"))
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--sleep-ms", type=int, default=100)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument("--timeout-sec", type=int, default=90)
    parser.add_argument("--checkpoint-every", type=int, default=1)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--force-rerun", action="store_true")
    parser.add_argument("--manual-review-threshold", type=float, default=0.70)
    return parser.parse_args()


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="", errors="ignore") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "processed_candidate_ids": [],
            "runs": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_columns(rows: list[dict[str, str]], fieldnames: list[str]) -> list[str]:
    required = [
        "relabel_action",
        "relabel_label",
        "relabel_confidence",
        "relabel_reason",
        "relabel_cause_words",
        "relabel_needs_manual_review",
        "relabel_model",
        "relabel_reviewed_at",
    ]
    output_fields = list(fieldnames)
    for col in required:
        if col not in output_fields:
            output_fields.append(col)
    for row in rows:
        for col in required:
            row.setdefault(col, "")
    return output_fields


def merge_resume_from_output(base_rows: list[dict[str, str]], output_path: Path) -> tuple[int, int]:
    if not output_path.exists():
        return 0, 0
    by_id: dict[str, dict[str, str]] = {}
    output_row_count = 0
    with output_path.open("r", encoding="utf-8", newline="", errors="ignore") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            output_row_count += 1
            cid = str(row.get("candidate_id", "")).strip()
            action = str(row.get("relabel_action", "")).strip().upper()
            if not cid or action not in VALID_ACTIONS:
                continue
            by_id[cid] = {
                "relabel_action": action,
                "relabel_label": str(row.get("relabel_label", "")).strip().upper(),
                "relabel_confidence": str(row.get("relabel_confidence", "")).strip(),
                "relabel_reason": str(row.get("relabel_reason", "")).strip(),
                "relabel_cause_words": str(row.get("relabel_cause_words", "")).strip(),
                "relabel_needs_manual_review": str(row.get("relabel_needs_manual_review", "")).strip(),
                "relabel_model": str(row.get("relabel_model", "")).strip(),
                "relabel_reviewed_at": str(row.get("relabel_reviewed_at", "")).strip(),
            }
    merged = 0
    for row in base_rows:
        cid = str(row.get("candidate_id", "")).strip()
        if not cid or cid not in by_id:
            continue
        row.update(by_id[cid])
        merged += 1
    return merged, output_row_count


def format_probabilities(row: dict[str, str]) -> str:
    parts: list[str] = []
    for label in ["DISINFO", "HATE", "NORMAL"]:
        value = str(row.get(f"prob_{label}", "")).strip()
        if value:
            parts.append(f"{label}={value}")
    return ", ".join(parts) if parts else "not available"


def build_prompt(row: dict[str, str]) -> str:
    text = str(row.get("text") or row.get("clean_text") or "").strip()
    current_label = normalize_label(str(row.get("y_true", "")))
    model_label = normalize_label(str(row.get("y_pred_tuned") or row.get("y_pred", "")))
    source = str(row.get("source", "")).strip()
    cause_words = str(row.get("llm_cause_words", "")).strip()
    probs = format_probabilities(row)

    return (
        "You are adjudicating Sinhala social-media moderation labels.\n"
        "Task: resolve disagreement between an existing prior label and the current model prediction.\n\n"
        "Hard constraints:\n"
        "- Use Sinhala meaning and Sinhala social-media context only.\n"
        "- Do not invent hidden context.\n"
        "- The existing prior label may also be wrong. Do not assume it is correct.\n"
        "- Compare the text itself against both labels and choose the better-supported outcome.\n"
        "- If both the prior label and model prediction look weak or ambiguous, choose the safer label based on the text and set needs_manual_review=true.\n"
        "- HATE includes targeted abuse, harassment, humiliation, dehumanization, or directed attacks against a person/group.\n"
        "- DISINFO includes likely false or misleading factual claims, rumor stated as fact, or urging spread of unverified claims.\n"
        "- NORMAL includes non-harmful opinion, neutral discussion, jokes without targeted abuse, and unsupported weak suspicion.\n"
        "- If both harms appear, choose the dominant harm only.\n"
        "- Profanity alone is not enough for HATE unless it is targeted.\n"
        "- For HATE or DISINFO, cause_words must be exact Sinhala words/short phrases copied from the text.\n"
        "- If exact Sinhala cause words cannot be copied, use an empty cause_words array.\n\n"
        "Output rules:\n"
        "- Return strict JSON only.\n"
        "- action must be KEEP or CHANGE.\n"
        "- label must be one of NORMAL, HATE, DISINFO.\n"
        "- If action is KEEP, label must match the existing prior label.\n"
        "- If action is CHANGE, label must be different from the existing prior label.\n"
        "- reason must be short and concrete.\n"
        "- confidence must be a number between 0 and 1.\n"
        "- needs_manual_review must be true when ambiguity remains.\n\n"
        'JSON schema: {"action":"KEEP|CHANGE","label":"NORMAL|HATE|DISINFO","confidence":0.0,"needs_manual_review":false,"reason":"...","cause_words":["..."]}\n\n'
        f"Source: {source or 'unknown'}\n"
        f"Existing prior label: {current_label or 'unknown'}\n"
        f"Model prediction: {model_label or 'unknown'}\n"
        f"Model probabilities: {probs}\n"
        f"Existing cause words: {cause_words or 'none'}\n\n"
        f"Text:\n{text}"
    )


def request_adjudication(
    *,
    endpoint: str,
    token: str,
    prompt: str,
    timeout_sec: int,
    temperature: float,
    top_p: float,
    top_k: int,
) -> tuple[str, str, float, bool, str, list[str], str]:
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "topP": top_p,
            "topK": top_k,
            "responseMimeType": "application/json",
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout_sec)
    response.raise_for_status()
    body = response.json()
    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
    raw = str(parts[0].get("text", "")) if parts else ""
    parsed = extract_json_from_text(raw)

    action = str(parsed.get("action", "")).strip().upper()
    if action not in VALID_ACTIONS:
        action = ""
    label = normalize_label(str(parsed.get("label", "")))
    confidence_raw = parsed.get("confidence", 0.0)
    needs_manual_review = bool(parsed.get("needs_manual_review", False))
    reason = str(parsed.get("reason", "")).strip()
    cause_words_raw = parsed.get("cause_words", [])
    cause_words: list[str] = []
    if isinstance(cause_words_raw, list):
        for item in cause_words_raw:
            value = str(item).strip()
            if value:
                cause_words.append(value)
    elif isinstance(cause_words_raw, str):
        cause_words = [item.strip() for item in cause_words_raw.split(",") if item.strip()]
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    return action, label, confidence, needs_manual_review, reason, cause_words, raw


def adjudicate_single_row(
    *,
    endpoint: str,
    token: str,
    credentials_path: Path,
    credentials_info: dict[str, Any] | None,
    row: dict[str, str],
    timeout_sec: int,
    temperature: float,
    top_p: float,
    top_k: int,
    sleep_ms: int,
) -> tuple[str, str, float, bool, str, list[str], str]:
    max_network_retries = 3
    local_token = token
    network_retries = 0
    while True:
        try:
            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)
            prompt = build_prompt(row)
            return request_adjudication(
                endpoint=endpoint,
                token=local_token,
                prompt=prompt,
                timeout_sec=timeout_sec,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
            )
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 401:
                local_token = build_token(credentials_path=credentials_path, credentials_info=credentials_info)
                continue
            if status in {429, 500, 502, 503, 504} and network_retries < max_network_retries:
                network_retries += 1
                time.sleep(min(2**network_retries, 8))
                continue
            raise
        except requests.RequestException:
            if network_retries < max_network_retries:
                network_retries += 1
                time.sleep(min(2**network_retries, 8))
                continue
            raise


def build_clients(credentials_path: Path, project_id_arg: str, location: str, model: str) -> list[dict[str, Any]]:
    credentials_payloads = load_credentials_payload(credentials_path)
    clients: list[dict[str, Any]] = []
    for item in credentials_payloads:
        item_project_id = str(item.get("project_id", "")).strip()
        project_id = str(project_id_arg or "").strip() or item_project_id
        if not project_id:
            continue
        clients.append(
            {
                "project_id": project_id,
                "endpoint": build_vertex_endpoint(project_id, location, model),
                "token": build_token(credentials_info=item),
                "credentials_info": item,
                "credentials_path": credentials_path,
            }
        )
    if clients:
        return clients
    fallback_project = str(project_id_arg or "").strip() or read_project_id_from_credentials(credentials_path)
    if not fallback_project:
        raise SystemExit(
            "Missing GCP project ID. Set --project-id, env GCP_PROJECT_ID, or use credentials JSON containing project_id."
        )
    return [
        {
            "project_id": fallback_project,
            "endpoint": build_vertex_endpoint(fallback_project, location, model),
            "token": build_token(credentials_path=credentials_path),
            "credentials_info": None,
            "credentials_path": credentials_path,
        }
    ]


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)
    state_path = Path(args.state_file)
    report_path = Path(args.report_out)
    credentials_path = Path(args.credentials_path)

    if not input_path.exists():
        raise SystemExit(f"Input CSV not found: {input_path}")
    if not credentials_path.exists():
        raise SystemExit(f"Credentials file not found: {credentials_path}")

    rows = load_csv_rows(input_path)
    if not rows:
        raise SystemExit(f"No rows found in: {input_path}")

    resumed_count, output_row_count = merge_resume_from_output(rows, output_path)
    if output_path.exists():
        print(f"Resume merge: loaded {resumed_count} reviewed rows from existing output ({output_row_count} rows).")

    fieldnames = ensure_columns(rows, list(rows[0].keys()))
    state = load_state(state_path)
    processed_ids = set(state.get("processed_candidate_ids", []))
    clients = build_clients(credentials_path, args.project_id, args.location, args.model)

    work_items: list[tuple[int, str]] = []
    existing_reviewed = 0
    skipped_empty = 0
    max_rows = args.max_rows if args.max_rows > 0 else 10**12
    for index, row in enumerate(rows):
        candidate_id = str(row.get("candidate_id", "")).strip()
        text = str(row.get("text") or row.get("clean_text") or "").strip()
        reviewed = str(row.get("relabel_action", "")).strip().upper() in VALID_ACTIONS
        if reviewed:
            existing_reviewed += 1
        if (reviewed or (candidate_id and candidate_id in processed_ids)) and not args.force_rerun:
            continue
        if not text:
            skipped_empty += 1
            continue
        if len(work_items) >= max_rows:
            break
        work_items.append((index, candidate_id))

    print("=== Gemini Error Relabel Startup ===")
    print(f"Input rows: {len(rows)}")
    print(f"Already reviewed rows: {existing_reviewed}")
    print(f"State processed IDs loaded: {len(processed_ids)}")
    print(f"Skipped empty-text rows: {skipped_empty}")
    print(f"Prepared {len(work_items)} rows for processing with workers={max(1, int(args.workers))}.")
    print("Projects: " + ", ".join(sorted({str(c['project_id']) for c in clients})))

    run_processed = 0
    run_reviewed = 0
    run_kept = 0
    run_changed = 0
    run_manual_review = 0
    run_errors: list[dict[str, str]] = []
    run_started = datetime.now(timezone.utc)
    checkpoint_every = max(1, int(args.checkpoint_every))
    workers = max(1, int(args.workers))

    def persist_progress() -> None:
        write_csv_rows(output_path, fieldnames, rows)
        state["processed_candidate_ids"] = sorted(processed_ids)
        save_state(state_path, state)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map: dict[concurrent.futures.Future, tuple[int, str]] = {}
        submit_index = 0
        in_flight_limit = max(workers * 2, 8)

        def submit_next() -> bool:
            nonlocal submit_index
            if submit_index >= len(work_items):
                return False
            row_index, candidate_id = work_items[submit_index]
            client = clients[submit_index % len(clients)]
            submit_index += 1
            future = executor.submit(
                adjudicate_single_row,
                endpoint=str(client["endpoint"]),
                token=str(client["token"]),
                credentials_path=client["credentials_path"],
                credentials_info=client["credentials_info"],
                row=rows[row_index],
                timeout_sec=args.timeout_sec,
                temperature=args.temperature,
                top_p=args.top_p,
                top_k=args.top_k,
                sleep_ms=args.sleep_ms,
            )
            future_map[future] = (row_index, candidate_id)
            return True

        while len(future_map) < in_flight_limit and submit_next():
            pass

        while future_map:
            done, _ = concurrent.futures.wait(
                future_map.keys(),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            for future in done:
                row_index, candidate_id = future_map.pop(future)
                row = rows[row_index]
                run_processed += 1
                try:
                    action, label, confidence, needs_manual_review, reason, cause_words, raw = future.result()
                except requests.HTTPError as exc:
                    status = exc.response.status_code if exc.response is not None else None
                    run_errors.append({"candidate_id": candidate_id, "error": f"HTTPError({status}): {str(exc)}"})
                    print(f"[{run_processed}/{len(work_items)}] candidate_id={candidate_id or '<missing>'} -> ERROR HTTP {status}")
                    continue
                except Exception as exc:  # noqa: BLE001
                    run_errors.append({"candidate_id": candidate_id, "error": str(exc)})
                    print(f"[{run_processed}/{len(work_items)}] candidate_id={candidate_id or '<missing>'} -> ERROR")
                    continue

                current_label = normalize_label(str(row.get("y_true", "")))
                if not action or not label:
                    run_errors.append(
                        {
                            "candidate_id": candidate_id,
                            "error": "No valid action/label parsed from Gemini response.",
                            "raw_response": str(raw)[:800],
                        }
                    )
                    print(f"[{run_processed}/{len(work_items)}] candidate_id={candidate_id or '<missing>'} -> WARNING no decision")
                    continue

                if action == "KEEP" and current_label:
                    label = current_label
                if label in {"HATE", "DISINFO"}:
                    cause_words = sanitize_cause_words(cause_words, str(row.get("text") or row.get("clean_text") or ""))
                else:
                    cause_words = []
                if confidence < args.manual_review_threshold:
                    needs_manual_review = True

                row["relabel_action"] = action
                row["relabel_label"] = label
                row["relabel_confidence"] = f"{confidence:.4f}"
                row["relabel_reason"] = reason
                row["relabel_cause_words"] = ", ".join(cause_words[:12])
                row["relabel_needs_manual_review"] = "true" if needs_manual_review else "false"
                row["relabel_model"] = args.model
                row["relabel_reviewed_at"] = datetime.now(timezone.utc).isoformat()

                if candidate_id:
                    processed_ids.add(candidate_id)
                run_reviewed += 1
                run_kept += 1 if action == "KEEP" else 0
                run_changed += 1 if action == "CHANGE" else 0
                run_manual_review += 1 if needs_manual_review else 0
                print(
                    f"[{run_processed}/{len(work_items)}] candidate_id={candidate_id or '<missing>'} "
                    f"-> action={action} label={label} manual_review={str(needs_manual_review).lower()}"
                )

                if run_reviewed % checkpoint_every == 0:
                    persist_progress()
                    print(f"Checkpoint saved at {run_reviewed} reviewed rows.")

            while len(future_map) < in_flight_limit and submit_next():
                pass

    persist_progress()

    run_finished = datetime.now(timezone.utc)
    run_report = {
        "started_at": run_started.isoformat(),
        "finished_at": run_finished.isoformat(),
        "duration_seconds": round((run_finished - run_started).total_seconds(), 3),
        "input_csv": str(input_path),
        "output_csv": str(output_path),
        "state_file": str(state_path),
        "project_ids": sorted({str(c["project_id"]) for c in clients}),
        "location": args.location,
        "model": args.model,
        "manual_review_threshold": args.manual_review_threshold,
        "counts": {
            "rows_total": len(rows),
            "run_processed": run_processed,
            "run_reviewed": run_reviewed,
            "run_kept": run_kept,
            "run_changed": run_changed,
            "run_manual_review": run_manual_review,
            "run_errors": len(run_errors),
        },
        "errors": run_errors[:500],
    }

    state.setdefault("runs", []).append(run_report)
    state["processed_candidate_ids"] = sorted(processed_ids)
    save_state(state_path, state)
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(run_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Gemini error relabel run completed.")
    print(f"Output CSV: {output_path}")
    print(f"State file: {state_path}")
    print(f"Run report: {report_path}")
    print(
        "Run counts: "
        f"processed={run_processed}, reviewed={run_reviewed}, kept={run_kept}, "
        f"changed={run_changed}, manual_review={run_manual_review}, errors={len(run_errors)}"
    )


if __name__ == "__main__":
    main()
