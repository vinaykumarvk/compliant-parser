#!/usr/bin/env python3
"""Backfill checklist analysis into stored parse records."""

from __future__ import annotations

import argparse
import asyncio
import copy
import logging
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import _build_checklist_analysis_payload
from complaint_parsing import load_dotenv
from database import dispose_engine, get_engine, parse_records, petition_checklist_questions
from petition_assistance import evaluate_checklist_questions


logger = logging.getLogger("backfill_checklist_analysis")


async def backfill(args: argparse.Namespace) -> int:
    load_dotenv()
    engine = await get_engine()
    updated = 0
    skipped = 0
    failed = 0

    try:
        async with engine.begin() as conn:
            question_rows = (
                await conn.execute(
                    sa.select(*petition_checklist_questions.c)
                    .where(petition_checklist_questions.c.is_active == sa.true())
                    .order_by(
                        petition_checklist_questions.c.checklist_version.desc(),
                        petition_checklist_questions.c.display_order.asc(),
                        petition_checklist_questions.c.category.asc(),
                    )
                )
            ).mappings().all()
            questions = [dict(row) for row in question_rows]
            logger.info("Loaded %s active checklist question(s).", len(questions))
            if not questions:
                logger.warning("No active checklist questions found; no parse records will be updated.")
                return 1 if args.fail_on_error else 0

            query = (
                sa.select(
                    parse_records.c.id,
                    parse_records.c.file_name,
                    parse_records.c.parsed_output,
                    parse_records.c.created_at,
                )
                .order_by(parse_records.c.created_at.desc())
            )
            if args.record_id:
                query = query.where(parse_records.c.id == args.record_id)
            if args.limit:
                query = query.limit(args.limit)

            rows = (await conn.execute(query)).all()
            logger.info("Found %s parse record(s) to inspect.", len(rows))

            for row in rows:
                payload = row.parsed_output if isinstance(row.parsed_output, dict) else None
                if not payload:
                    skipped += 1
                    logger.info("SKIP %s %s: parsed_output is not a JSON object.", row.id, row.file_name)
                    continue
                if args.skip_existing and isinstance(payload.get("checklist_analysis"), dict):
                    skipped += 1
                    logger.info("SKIP %s %s: checklist_analysis already exists.", row.id, row.file_name)
                    continue

                try:
                    evaluations = evaluate_checklist_questions(payload, questions, purpose=args.purpose)
                    analysis = _build_checklist_analysis_payload(
                        payload,
                        evaluations,
                        purpose=args.purpose,
                    )
                    next_payload = copy.deepcopy(payload)
                    next_payload["checklist_analysis"] = analysis
                    if args.dry_run:
                        skipped += 1
                        logger.info(
                            "DRY %s %s: would store %s evaluation(s), readiness=%s.",
                            row.id,
                            row.file_name,
                            len(analysis.get("evaluations") or []),
                            analysis.get("readiness_score"),
                        )
                        continue

                    await conn.execute(
                        parse_records.update()
                        .where(parse_records.c.id == row.id)
                        .values(parsed_output=next_payload)
                    )
                    updated += 1
                    logger.info(
                        "OK %s %s: stored %s evaluation(s), readiness=%s.",
                        row.id,
                        row.file_name,
                        len(analysis.get("evaluations") or []),
                        analysis.get("readiness_score"),
                    )
                except Exception as exc:
                    failed += 1
                    logger.exception("FAIL %s %s: %s", row.id, row.file_name, exc)
                    if args.fail_on_error:
                        raise
    finally:
        await dispose_engine()

    logger.info("Done. updated=%s skipped=%s failed=%s", updated, skipped, failed)
    return 1 if failed and args.fail_on_error else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Inspect records without updating the DB.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of records to inspect.")
    parser.add_argument("--record-id", help="Only process one parse_records.id.")
    parser.add_argument("--purpose", default="petition", help="Checklist purpose to evaluate.")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Do not update records that already have checklist_analysis.",
    )
    parser.add_argument("--fail-on-error", action="store_true", help="Exit non-zero if any record fails.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(asyncio.run(backfill(parse_args())))


if __name__ == "__main__":
    main()
