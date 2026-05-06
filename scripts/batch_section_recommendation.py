#!/usr/bin/env python3
"""Batch BNS section recommendation for existing documents lacking analysis."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from complaint_parsing import load_dotenv

logger = logging.getLogger("batch_section_recommendation")


async def run(args: argparse.Namespace) -> int:
    load_dotenv()
    from ai_workflows import batch_recommend_sections

    result = await batch_recommend_sections(
        limit=args.limit,
        concurrency=args.concurrency,
        delay_ms=args.delay_ms,
        dry_run=args.dry_run,
        user_id="system:batch-cli",
    )
    print(json.dumps(result, indent=2, default=str))
    return 1 if result.get("failed") else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=500, help="Max documents to process.")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel KIS/LLM calls.")
    parser.add_argument("--delay-ms", type=int, default=200, help="Delay between calls in ms.")
    parser.add_argument("--dry-run", action="store_true", help="Only count candidates without processing.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(asyncio.run(run(parse_args())))


if __name__ == "__main__":
    main()
