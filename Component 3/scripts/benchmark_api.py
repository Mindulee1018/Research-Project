import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


DEFAULT_TEXTS = [
    "එයාව මිනිස්සුන්ගේ ඉස්සරහා අපහාස කරන්න ඕන.",
    "මේක 100% ඇත්තක්, හැමෝටම දැන්ම share කරන්න.",
    "මෙම පණිවිඩය තහවුරු කරගෙන පසුව බෙදාගන්න.",
]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * p))
    return float(ordered[idx])


def call_moderate(base_url: str, text: str, timeout_sec: float) -> tuple[bool, float, int]:
    url = f"{base_url.rstrip('/')}/api/moderate"
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8")
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if resp.status != 200:
                return False, elapsed_ms, resp.status
            parsed = json.loads(body)
            ok = bool(parsed.get("success", False))
            return ok, elapsed_ms, resp.status
    except urllib.error.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return False, elapsed_ms, int(exc.code)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return False, elapsed_ms, 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark /api/moderate latency and throughput.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="Backend base URL.")
    parser.add_argument("--requests", type=int, default=500, help="Total request count.")
    parser.add_argument("--workers", type=int, default=16, help="Concurrent workers.")
    parser.add_argument("--timeout-sec", type=float, default=20.0, help="Request timeout seconds.")
    parser.add_argument(
        "--output-json",
        default="evaluation/benchmarks/latest_api_benchmark.json",
        help="Output JSON path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    total = max(int(args.requests), 1)
    workers = max(int(args.workers), 1)

    print(f"[benchmark] base_url={args.base_url} total_requests={total} workers={workers}")
    wall_start = time.perf_counter()
    latencies_ms: list[float] = []
    successes = 0
    failures = 0
    status_counts: dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = []
        for idx in range(total):
            text = DEFAULT_TEXTS[idx % len(DEFAULT_TEXTS)]
            futures.append(pool.submit(call_moderate, args.base_url, text, args.timeout_sec))

        for i, future in enumerate(as_completed(futures), start=1):
            ok, elapsed_ms, status = future.result()
            latencies_ms.append(elapsed_ms)
            status_key = str(status)
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
            if ok:
                successes += 1
            else:
                failures += 1
            if i % 25 == 0 or i == total:
                print(
                    f"[benchmark] progress {i}/{total} | success={successes} fail={failures} "
                    f"last_ms={elapsed_ms:.2f}"
                )

    wall_sec = max(time.perf_counter() - wall_start, 1e-9)
    rps = total / wall_sec
    projected_posts_per_day = rps * 86400.0
    summary = {
        "base_url": args.base_url,
        "requests_total": total,
        "workers": workers,
        "success_count": successes,
        "failure_count": failures,
        "status_counts": status_counts,
        "wall_time_sec": wall_sec,
        "throughput_rps": rps,
        "throughput_posts_per_day_projection": projected_posts_per_day,
        "latency_ms": {
            "mean": statistics.fmean(latencies_ms) if latencies_ms else 0.0,
            "median": statistics.median(latencies_ms) if latencies_ms else 0.0,
            "p90": percentile(latencies_ms, 0.90),
            "p95": percentile(latencies_ms, 0.95),
            "p99": percentile(latencies_ms, 0.99),
            "min": min(latencies_ms) if latencies_ms else 0.0,
            "max": max(latencies_ms) if latencies_ms else 0.0,
        },
        "targets": {
            "single_post_under_2s_p95": percentile(latencies_ms, 0.95) < 2000.0 if latencies_ms else False,
            "throughput_over_10k_per_day": projected_posts_per_day >= 10000.0,
        },
        "generated_at_unix": int(time.time()),
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[benchmark] done")
    print(json.dumps(summary["latency_ms"], ensure_ascii=False))
    print(f"[benchmark] throughput_rps={summary['throughput_rps']:.2f}")
    print(f"[benchmark] projected_posts_per_day={summary['throughput_posts_per_day_projection']:.0f}")
    print(f"[benchmark] output={output_path}")


if __name__ == "__main__":
    main()
