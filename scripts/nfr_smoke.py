#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Sample:
    ok: bool
    status: int
    latency_ms: float
    error: str | None = None


def _request(url: str, timeout: float) -> Sample:
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read()
            status = response.getcode()
            ok = 200 <= status < 500
    except urllib.error.HTTPError as exc:
        status = exc.code
        ok = exc.code < 500
        error = str(exc)
    except Exception as exc:
        status = 0
        ok = False
        error = str(exc)
    else:
        error = None
    latency_ms = (time.perf_counter() - start) * 1000
    return Sample(ok=ok, status=status, latency_ms=latency_ms, error=error)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((percentile / 100) * (len(ordered) - 1))))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description="IQW NFR smoke/load evidence runner")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--path", default="/health")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--p95-ms", type=float, default=500.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/" + args.path.lstrip("/")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        samples = list(executor.map(lambda _: _request(url, args.timeout), range(args.requests)))

    latencies = [sample.latency_ms for sample in samples]
    failures = [sample for sample in samples if not sample.ok]
    error_rate = len(failures) / len(samples) if samples else 1.0
    result = {
        "url": url,
        "requests": len(samples),
        "concurrency": args.concurrency,
        "ok": len(samples) - len(failures),
        "failed": len(failures),
        "error_rate": error_rate,
        "latency_ms": {
            "min": min(latencies) if latencies else 0.0,
            "mean": statistics.mean(latencies) if latencies else 0.0,
            "p95": _percentile(latencies, 95),
            "max": max(latencies) if latencies else 0.0,
        },
        "thresholds": {
            "p95_ms": args.p95_ms,
            "max_error_rate": args.max_error_rate,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["latency_ms"]["p95"] > args.p95_ms:
        return 2
    if error_rate > args.max_error_rate:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
