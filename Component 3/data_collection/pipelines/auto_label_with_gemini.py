import argparse
import concurrent.futures
import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from data_collection.io_utils import ensure_dir


VALID_LABELS = {"HATE", "DISINFO", "NORMAL"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto-label annotation rows with Gemini (Vertex AI) using service-account credentials."
    )
    parser.add_argument("--input-csv", default="annotation/workflow/current/annotator_a.csv")
    parser.add_argument("--output-csv", default="annotation/workflow/current/annotator_a_llm.csv")
    parser.add_argument("--state-file", default="annotation/workflow/state/gemini_label_state.json")
    parser.add_argument("--report-out", default="annotation/workflow/state/gemini_label_report.json")
    parser.add_argument("--credentials-path", default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json"))
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", ""))
    parser.add_argument("--location", default=os.environ.get("GCP_LOCATION", "us-central1"))
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite"))
    parser.add_argument("--max-rows", type=int, default=0, help="Max rows to process in this run. 0 means no limit.")
    parser.add_argument("--sleep-ms", type=int, default=100)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument("--timeout-sec", type=int, default=90)
    parser.add_argument("--checkpoint-every", type=int, default=1)
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel labeling workers.")
    parser.add_argument("--force-relabel", action="store_true", help="Relabel rows even if annotator_label is already filled.")
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
            "label_counts": {"HATE": 0, "DISINFO": 0, "NORMAL": 0, "UNLABELED": 0},
            "runs": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_resume_labels_from_output(base_rows: list[dict[str, str]], output_path: Path) -> tuple[int, int]:
    if not output_path.exists():
        return 0, 0
    by_id: dict[str, dict[str, str]] = {}
    output_row_count = 0
    with output_path.open("r", encoding="utf-8", newline="", errors="ignore") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            output_row_count += 1
            cid = str(row.get("candidate_id", "")).strip()
            if not cid:
                continue
            label = normalize_label(row.get("annotator_label", ""))
            if not label:
                continue
            by_id[cid] = {
                "annotator_label": label,
                "annotator_notes": str(row.get("annotator_notes", "")).strip(),
                "llm_confidence": str(row.get("llm_confidence", "")).strip(),
                "llm_model": str(row.get("llm_model", "")).strip(),
                "llm_labeled_at": str(row.get("llm_labeled_at", "")).strip(),
                "llm_cause_words": str(row.get("llm_cause_words", "")).strip(),
            }

    merged = 0
    for row in base_rows:
        cid = str(row.get("candidate_id", "")).strip()
        if not cid:
            continue
        prev = by_id.get(cid)
        if not prev:
            continue
        prev_label = normalize_label(prev.get("annotator_label", ""))
        if not prev_label:
            continue
        row["annotator_label"] = prev_label
        row["annotator_notes"] = str(prev.get("annotator_notes", "")).strip()
        row["llm_confidence"] = str(prev.get("llm_confidence", "")).strip()
        row["llm_model"] = str(prev.get("llm_model", "")).strip()
        row["llm_labeled_at"] = str(prev.get("llm_labeled_at", "")).strip()
        row["llm_cause_words"] = str(prev.get("llm_cause_words", "")).strip()
        merged += 1
    return merged, output_row_count


def read_project_id_from_credentials(credentials_path: Path) -> str:
    try:
        payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            project_id = str(item.get("project_id", "")).strip()
            if project_id:
                return project_id
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("project_id", "")).strip()


def load_credentials_payload(credentials_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        result: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                result.append(item)
        if result:
            return result
    raise RuntimeError(
        "credentials file must be a single service-account object or an array of service-account objects."
    )


def build_prompt(text: str, *, strict_mode: bool = False) -> str:
    strict_block = ""
    if strict_mode:
        strict_block = (
            "STRICT ENFORCEMENT:\n"
            "- If label is HATE or DISINFO, cause_words MUST contain 1 to 5 items.\n"
            "- Every cause_words item MUST be an exact word/short phrase copied from Text.\n"
            "- If you cannot extract exact cause words, set label to NORMAL and cause_words to [].\n\n"
        )

    return (
        "You are labeling Sinhala social-media content.\n"
        "Language constraint:\n"
        "- Assume comments are Sinhala and apply Sinhala linguistic/cultural context.\n"
        "- Do not use English-only rationale. Focus on Sinhala wording and intent.\n\n"
        "Labels:\n"
        "- HATE: hate speech, harassment, targeted abuse, insults, dehumanization, or attacks against a person/group (identity-based or non-identity personal attacks).\n"
        "- DISINFO: factual-looking claim that is likely false/misleading, rumor presented as fact, or urging spread of unverified factual claims.\n"
        "- NORMAL: non-harmful content, including neutral discussion/opinion without targeted abuse and without misleading factual claim.\n\n"
        "Rules:\n"
        "- Choose exactly one label from HATE, DISINFO, NORMAL.\n"
        "- Harassment is NOT a separate class; map harassment to HATE.\n"
        "- If both HATE and DISINFO appear, choose the dominant harm signal in the text.\n"
        "- If evidence is weak/ambiguous, choose NORMAL.\n"
        "- Ignore profanity if it is not targeted hate and not disinformation.\n"
        "- Use only the text below.\n\n"
        f"{strict_block}"
        "Return strict JSON only with keys: label, confidence, cause_words.\n"
        "- cause_words must be an array of exact Sinhala words/short Sinhala phrases copied from the text.\n"
        "- For NORMAL, return an empty array.\n"
        'Example: {"label":"DISINFO","confidence":0.78,"cause_words":["තහවුරු","ඇත්ත"]}\n\n'
        f"Text:\n{text}"
    )


def extract_json_from_text(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    return item
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def normalize_label(label: str) -> str:
    normalized = str(label or "").strip().upper()
    return normalized if normalized in VALID_LABELS else ""


def extract_label_from_raw_text(raw_text: str) -> str:
    text = str(raw_text or "")
    match = re.search(r'"label"\s*:\s*"(?P<label>HATE|DISINFO|NORMAL)"', text, flags=re.IGNORECASE)
    if match:
        return normalize_label(match.group("label"))
    match2 = re.search(r"\b(HATE|DISINFO|NORMAL)\b", text, flags=re.IGNORECASE)
    if match2:
        return normalize_label(match2.group(1))
    return ""


def build_vertex_endpoint(project_id: str, location: str, model: str) -> str:
    return (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/publishers/google/models/{model}:generateContent"
    )


def build_token(credentials_path: Path | None = None, credentials_info: dict[str, Any] | None = None) -> str:
    try:
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'google-auth'. Install with: pip install google-auth"
        ) from exc

    if credentials_info is not None:
        creds = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    elif credentials_path is not None:
        creds = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    else:
        raise RuntimeError("Either credentials_path or credentials_info must be provided.")
    creds.refresh(GoogleAuthRequest())
    if not creds.token:
        raise RuntimeError("Could not obtain access token from service account credentials.")
    return creds.token


def request_label(
    endpoint: str,
    token: str,
    text: str,
    timeout_sec: int,
    temperature: float,
    top_p: float,
    top_k: int,
    strict_mode: bool = False,
) -> tuple[str, float, list[str], str]:
    payload = {
        "contents": [{"role": "user", "parts": [{"text": build_prompt(text, strict_mode=strict_mode)}]}],
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
    parts = (
        body.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])
    )
    raw = str(parts[0].get("text", "")) if parts else ""
    parsed = extract_json_from_text(raw)

    label = normalize_label(str(parsed.get("label", "")))
    if not label:
        label = extract_label_from_raw_text(raw)
    confidence_raw = parsed.get("confidence", 0.0)
    cause_words_raw = parsed.get("cause_words", [])
    cause_words: list[str] = []
    if isinstance(cause_words_raw, list):
        for item in cause_words_raw:
            token = str(item).strip()
            if token:
                cause_words.append(token)
    elif isinstance(cause_words_raw, str):
        cause_words = [tok.strip() for tok in cause_words_raw.split(",") if tok.strip()]
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0

    return label, confidence, cause_words, raw


def sanitize_cause_words(cause_words: list[str], text: str) -> list[str]:
    if not cause_words:
        return []
    def has_sinhala_chars(value: str) -> bool:
        return any("\u0D80" <= ch <= "\u0DFF" for ch in value)

    cleaned: list[str] = []
    seen: set[str] = set()
    text_lower = text.lower()
    for token in cause_words:
        candidate = str(token).strip()
        if len(candidate) < 2:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        if key not in text_lower:
            continue
        if not has_sinhala_chars(candidate):
            continue
        seen.add(key)
        cleaned.append(candidate)
        if len(cleaned) >= 12:
            break
    return cleaned


def label_single_text(
    *,
    endpoint: str,
    token: str,
    credentials_path: Path,
    credentials_info: dict[str, Any] | None,
    text: str,
    timeout_sec: int,
    temperature: float,
    top_p: float,
    top_k: int,
    sleep_ms: int,
) -> tuple[str, float, list[str], str, int]:
    max_network_retries = 3
    retries = 0
    network_retries = 0
    local_token = token
    while True:
        try:
            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)
            label, confidence, cause_words_list, raw = request_label(
                endpoint=endpoint,
                token=local_token,
                text=text,
                timeout_sec=timeout_sec,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
            )
            cause_words_list = sanitize_cause_words(cause_words_list, text)
            if label in {"HATE", "DISINFO"} and not cause_words_list:
                retries += 1
                label_retry, confidence_retry, cause_words_retry, raw_retry = request_label(
                    endpoint=endpoint,
                    token=local_token,
                    text=text,
                    timeout_sec=timeout_sec,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    strict_mode=True,
                )
                cause_words_retry = sanitize_cause_words(cause_words_retry, text)
                label = label_retry or label
                confidence = confidence_retry if label_retry else confidence
                raw = raw_retry or raw
                cause_words_list = cause_words_retry
            return label, confidence, cause_words_list, raw, retries
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 401 and retries < 1:
                local_token = build_token(credentials_path=credentials_path, credentials_info=credentials_info)
                retries += 1
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


def ensure_columns(rows: list[dict[str, str]], fieldnames: list[str]) -> list[str]:
    required = ["annotator_label", "annotator_notes", "llm_confidence", "llm_model", "llm_labeled_at", "llm_cause_words"]
    output_fields = list(fieldnames)
    for col in required:
        if col not in output_fields:
            output_fields.append(col)
    for row in rows:
        for col in required:
            row.setdefault(col, "")
    return output_fields


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
    credentials_payloads = load_credentials_payload(credentials_path)

    clients: list[dict[str, Any]] = []
    for item in credentials_payloads:
        item_project_id = str(item.get("project_id", "")).strip()
        project_id = str(args.project_id or "").strip() or item_project_id
        if not project_id:
            continue
        endpoint = build_vertex_endpoint(project_id, args.location, args.model)
        token = build_token(credentials_info=item)
        clients.append(
            {
                "project_id": project_id,
                "endpoint": endpoint,
                "token": token,
                "credentials_info": item,
                "credentials_path": credentials_path,
            }
        )

    if not clients:
        fallback_project = str(args.project_id or "").strip() or read_project_id_from_credentials(credentials_path)
        if not fallback_project:
            raise SystemExit(
                "Missing GCP project ID. Set --project-id, env GCP_PROJECT_ID, or use credentials JSON containing project_id."
            )
        clients.append(
            {
                "project_id": fallback_project,
                "endpoint": build_vertex_endpoint(fallback_project, args.location, args.model),
                "token": build_token(credentials_path=credentials_path),
                "credentials_info": None,
                "credentials_path": credentials_path,
            }
        )

    rows = load_csv_rows(input_path)
    if not rows:
        raise SystemExit(f"No rows found in: {input_path}")

    resumed_count, output_row_count = merge_resume_labels_from_output(rows, output_path)
    if output_path.exists():
        print(f"Resume merge: loaded {resumed_count} labeled rows from existing output ({output_row_count} rows).")
        if output_row_count < len(rows):
            print(
                "WARNING: output CSV has fewer rows than input base CSV. "
                "Using base input rows + merged labels to prevent truncation."
            )

    state = load_state(state_path)
    processed_ids = set(state.get("processed_candidate_ids", []))
    label_counts = state.get("label_counts", {"HATE": 0, "DISINFO": 0, "NORMAL": 0, "UNLABELED": 0})
    label_counts.setdefault("HATE", 0)
    label_counts.setdefault("DISINFO", 0)
    label_counts.setdefault("NORMAL", 0)
    label_counts.setdefault("UNLABELED", 0)

    fieldnames = ensure_columns(rows, list(rows[0].keys()))
    workers = max(1, int(args.workers))
    max_rows = args.max_rows if args.max_rows and args.max_rows > 0 else 10**12
    run_processed = 0
    run_labeled = 0
    run_skipped = 0
    run_skipped_existing = 0
    run_skipped_state = 0
    run_skipped_empty = 0
    run_strict_retries = 0
    run_forced_normal_due_to_missing_cause = 0
    run_errors: list[dict[str, str]] = []
    run_started = datetime.now(timezone.utc)
    interrupted = False

    checkpoint_every = max(1, int(args.checkpoint_every))

    def persist_progress() -> None:
        write_csv_rows(output_path, fieldnames, rows)
        state["processed_candidate_ids"] = sorted(processed_ids)
        state["label_counts"] = label_counts
        save_state(state_path, state)

    work_items: list[tuple[int, str]] = []
    total_existing_labeled = 0
    total_invalid_nonempty_labels = 0
    for index, row in enumerate(rows, start=1):
        candidate_id = str(row.get("candidate_id", "")).strip()
        text = str(row.get("text", "")).strip()
        existing_raw = str(row.get("annotator_label", "")).strip()
        existing = normalize_label(existing_raw)
        if existing:
            total_existing_labeled += 1
        elif existing_raw:
            total_invalid_nonempty_labels += 1
        should_skip_existing = (not args.force_relabel) and bool(existing)
        should_skip_state = (not args.force_relabel) and candidate_id and (candidate_id in processed_ids)
        if should_skip_existing or should_skip_state:
            run_skipped += 1
            if should_skip_existing:
                run_skipped_existing += 1
            elif should_skip_state:
                run_skipped_state += 1
            continue
        if not text:
            label_counts["UNLABELED"] += 1
            run_skipped += 1
            run_skipped_empty += 1
            continue
        if len(work_items) >= max_rows:
            break
        work_items.append((index - 1, candidate_id))

    total_rows = len(rows)
    total_unlabeled = total_rows - total_existing_labeled
    state_overlap = run_skipped_state
    print("=== Gemini Auto-Label Startup ===")
    print(f"Input rows: {total_rows}")
    print(f"Already labeled rows: {total_existing_labeled}")
    print(f"Unlabeled rows: {total_unlabeled}")
    print(f"State processed IDs loaded: {len(processed_ids)}")
    print(f"State overlap with current input: {state_overlap}")
    print(f"Skipped empty-text rows: {run_skipped_empty}")
    if total_invalid_nonempty_labels > 0:
        print(f"WARNING: invalid non-empty labels found: {total_invalid_nonempty_labels}")
    print(f"Prepared {len(work_items)} rows for processing with workers={workers}.")
    print(f"Credential clients: {len(clients)}")
    print("Projects: " + ", ".join(sorted({str(c['project_id']) for c in clients})))

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_map: dict[concurrent.futures.Future, tuple[int, str]] = {}
            in_flight_limit = max(workers * 2, 8)
            submit_index = 0

            def submit_next() -> bool:
                nonlocal submit_index
                if submit_index >= len(work_items):
                    return False
                row_index, candidate_id = work_items[submit_index]
                client = clients[submit_index % len(clients)]
                submit_index += 1
                text = str(rows[row_index].get("text", "")).strip()
                future = executor.submit(
                    label_single_text,
                    endpoint=str(client["endpoint"]),
                    token=str(client["token"]),
                    credentials_path=client["credentials_path"],
                    credentials_info=client["credentials_info"],
                    text=text,
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
                    run_processed += 1
                    row = rows[row_index]
                    try:
                        label, confidence, cause_words_list, raw, strict_retries = future.result()
                        run_strict_retries += strict_retries
                    except requests.HTTPError as exc:
                        status = exc.response.status_code if exc.response is not None else None
                        run_errors.append({"candidate_id": candidate_id, "error": f"HTTPError({status}): {str(exc)}"})
                        print(f"[{run_processed}/{len(work_items)}] candidate_id={candidate_id or '<missing>'} -> ERROR HTTP {status}")
                        continue
                    except Exception as exc:  # noqa: BLE001
                        run_errors.append({"candidate_id": candidate_id, "error": str(exc)})
                        print(f"[{run_processed}/{len(work_items)}] candidate_id={candidate_id or '<missing>'} -> ERROR")
                        continue

                    if not label:
                        run_errors.append(
                            {
                                "candidate_id": candidate_id,
                                "error": "No valid label parsed from Gemini response.",
                                "raw_response": str(raw)[:500],
                            }
                        )
                        print(f"[{run_processed}/{len(work_items)}] candidate_id={candidate_id or '<missing>'} -> WARNING no label")
                        continue

                    if label in {"HATE", "DISINFO"} and not cause_words_list:
                        label = "NORMAL"
                        cause_words_list = []
                        run_forced_normal_due_to_missing_cause += 1

                    row["annotator_label"] = label
                    row["annotator_notes"] = ""
                    row["llm_confidence"] = f"{confidence:.4f}"
                    row["llm_model"] = args.model
                    row["llm_labeled_at"] = datetime.now(timezone.utc).isoformat()
                    if label == "NORMAL":
                        cause_words_list = []
                    cause_words_csv = ", ".join(cause_words_list[:12])
                    row["llm_cause_words"] = cause_words_csv if label in {"HATE", "DISINFO"} else ""

                    label_counts[label] += 1
                    if candidate_id:
                        processed_ids.add(candidate_id)
                    run_labeled += 1
                    print(f"[{run_processed}/{len(work_items)}] candidate_id={candidate_id or '<missing>'} -> {label}")

                    if run_labeled % checkpoint_every == 0:
                        persist_progress()
                        print(f"Checkpoint saved at {run_labeled} labeled rows.")

                while len(future_map) < in_flight_limit and submit_next():
                    pass
    except KeyboardInterrupt:
        interrupted = True
        print("Interrupted by user. Saving progress...")
    finally:
        persist_progress()

    run_finished = datetime.now(timezone.utc)
    run_report = {
        "started_at": run_started.isoformat(),
        "finished_at": run_finished.isoformat(),
        "duration_seconds": round((run_finished - run_started).total_seconds(), 3),
        "input_csv": str(input_path),
        "output_csv": str(output_path),
        "state_file": str(state_path),
        "project_id": args.project_id if str(args.project_id or "").strip() else "",
        "project_ids": sorted({str(c["project_id"]) for c in clients}),
        "location": args.location,
        "model": args.model,
        "counts": {
            "rows_total": len(rows),
            "run_processed": run_processed,
            "run_labeled": run_labeled,
            "run_skipped": run_skipped,
            "run_skipped_existing_labeled": run_skipped_existing,
            "run_skipped_from_state": run_skipped_state,
            "run_skipped_empty_text": run_skipped_empty,
            "run_errors": len(run_errors),
            "run_strict_retries": run_strict_retries,
            "run_forced_normal_due_to_missing_cause_words": run_forced_normal_due_to_missing_cause,
            "interrupted": interrupted,
        },
        "label_counts_cumulative": label_counts,
        "errors": run_errors[:500],
    }

    state["processed_candidate_ids"] = sorted(processed_ids)
    state["label_counts"] = label_counts
    state.setdefault("runs", []).append(run_report)
    save_state(state_path, state)

    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(run_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Gemini auto-label run completed.")
    print(f"Output CSV: {output_path}")
    print(f"State file: {state_path}")
    print(f"Run report: {report_path}")
    print(
        "Run counts: "
        f"processed={run_processed}, labeled={run_labeled}, skipped={run_skipped}, errors={len(run_errors)}"
    )
    if total_rows > 0:
        final_labeled = sum(1 for row in rows if normalize_label(row.get("annotator_label", "")))
        final_remaining = total_rows - final_labeled
        print(
            f"Final status: labeled={final_labeled}/{total_rows} "
            f"({(100.0 * final_labeled / total_rows):.2f}%), remaining={final_remaining}"
        )


if __name__ == "__main__":
    main()
