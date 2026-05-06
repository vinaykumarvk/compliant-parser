#!/usr/bin/env python3
"""Backfill refined English translations for stored parse records."""

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

from complaint_parsing import (
    _extract_local_language_ocr_text,
    _normalize_language_code,
    _normalize_whitespace,
    _refine_english_translation,
    get_translation_config,
    load_dotenv,
)
from database import dispose_engine, get_engine, parse_records


logger = logging.getLogger("backfill_translation_refinement")


def _source_is_english(detected_language: str, translation_status: str) -> bool:
    return (
        _normalize_language_code(detected_language) == "en"
        or str(translation_status or "").lower() == "not_needed"
    )


def _should_skip_existing_refinement(
    *,
    existing_refined: str,
    raw_english: str,
    refinement_status: str,
    force: bool,
) -> bool:
    if force or not existing_refined:
        return False
    normalized_status = str(refinement_status or "").lower()
    if normalized_status in {"refined", "edited"}:
        return True
    if existing_refined != _normalize_whitespace(raw_english):
        return True
    return False


def _raw_english_from_payload(payload: dict[str, Any]) -> str:
    text = payload.get("text") if isinstance(payload.get("text"), dict) else {}
    language = payload.get("language") if isinstance(payload.get("language"), dict) else {}
    existing_raw = _normalize_whitespace(text.get("raw_english_translation") or "")
    if existing_raw:
        return existing_raw

    english_text = _normalize_whitespace(text.get("english_text") or "")
    detected = _normalize_language_code(language.get("detected"))
    status = str(language.get("translation_status") or "").lower()
    if detected == "en" or status in {"translated", "success", "not_needed"}:
        return english_text
    return ""


def _update_payload_with_refinement(
    payload: dict[str, Any],
    *,
    raw_english: str,
    local_ocr: str,
    refinement: dict[str, Any],
) -> dict[str, Any]:
    next_payload = copy.deepcopy(payload)
    text = next_payload.setdefault("text", {})
    language = next_payload.setdefault("language", {})
    meta = next_payload.setdefault("meta", {})

    text.setdefault("raw_english_translation", raw_english)
    if local_ocr:
        text["local_language_ocr_text"] = local_ocr

    refined_text = _normalize_whitespace(refinement.get("refined_text") or "")
    if refined_text:
        text["refined_english_translation"] = refined_text

    if refinement.get("status") == "refined" and refined_text:
        text["analysis_english_text"] = refined_text
        meta["text_used_for_extraction"] = "refined_english_translation"
    elif raw_english and not text.get("analysis_english_text"):
        text["analysis_english_text"] = raw_english
        meta["text_used_for_extraction"] = "raw_english_translation"

    language["translation_refinement_status"] = refinement.get("status")
    language["translation_refinement_provider"] = refinement.get("provider")
    language["translation_refinement_model"] = refinement.get("model")
    language["translation_refinement_error"] = refinement.get("error")
    language["refinement_privacy_controls"] = refinement.get("privacy_controls", {})
    return next_payload


async def backfill(args: argparse.Namespace) -> int:
    load_dotenv()
    config = get_translation_config()
    config["refinement_enabled"] = True
    if args.provider:
        config["refinement_provider"] = args.provider
    if args.model:
        config["refinement_model"] = args.model
    include_english = bool(getattr(args, "include_english", False)) or not bool(
        getattr(args, "skip_english", False)
    )

    engine = await get_engine()
    updated = 0
    skipped = 0
    failed = 0

    try:
        async with engine.begin() as conn:
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
                payload = row.parsed_output if isinstance(row.parsed_output, dict) else {}
                text = payload.get("text") if isinstance(payload.get("text"), dict) else {}
                language = payload.get("language") if isinstance(payload.get("language"), dict) else {}
                detected = _normalize_language_code(language.get("detected"))
                translation_status = str(language.get("translation_status") or "").lower()
                refinement_status = str(language.get("translation_refinement_status") or "").lower()
                source_is_english = _source_is_english(detected, translation_status)
                existing_refined = _normalize_whitespace(text.get("refined_english_translation") or "")
                raw_english = _raw_english_from_payload(payload)
                ocr_text = _normalize_whitespace(text.get("ocr_text") or "")
                local_ocr = _extract_local_language_ocr_text(ocr_text, detected)

                if not raw_english:
                    skipped += 1
                    logger.info("SKIP %s %s: no raw English text available.", row.id, row.file_name)
                    continue

                if source_is_english and not include_english:
                    skipped += 1
                    logger.info("SKIP %s %s: source text is already English.", row.id, row.file_name)
                    continue

                if _should_skip_existing_refinement(
                    existing_refined=existing_refined,
                    raw_english=raw_english,
                    refinement_status=refinement_status,
                    force=args.force,
                ):
                    skipped += 1
                    logger.info("SKIP %s %s: refined English already exists.", row.id, row.file_name)
                    continue

                if args.dry_run:
                    skipped += 1
                    logger.info(
                        "DRY %s %s: would refine %s chars using %s/%s.",
                        row.id,
                        row.file_name,
                        len(raw_english),
                        config["refinement_provider"],
                        config["refinement_model"],
                    )
                    continue

                refinement = await asyncio.to_thread(
                    _refine_english_translation,
                    raw_english,
                    ocr_text,
                    detected,
                    translation_status,
                    config,
                    source_is_english and include_english,
                )
                if refinement.get("status") != "refined":
                    failed += 1
                    logger.warning(
                        "FAIL %s %s: %s (%s)",
                        row.id,
                        row.file_name,
                        refinement.get("status"),
                        refinement.get("error"),
                    )
                    if args.store_failures:
                        next_payload = _update_payload_with_refinement(
                            payload,
                            raw_english=raw_english,
                            local_ocr=local_ocr,
                            refinement=refinement,
                        )
                        await conn.execute(
                            parse_records.update()
                            .where(parse_records.c.id == row.id)
                            .values(parsed_output=next_payload)
                        )
                    continue

                next_payload = _update_payload_with_refinement(
                    payload,
                    raw_english=raw_english,
                    local_ocr=local_ocr,
                    refinement=refinement,
                )
                await conn.execute(
                    parse_records.update()
                    .where(parse_records.c.id == row.id)
                    .values(parsed_output=next_payload)
                )
                updated += 1
                logger.info("OK %s %s: refined translation stored.", row.id, row.file_name)
    finally:
        await dispose_engine()

    logger.info("Done. updated=%s skipped=%s failed=%s", updated, skipped, failed)
    return 1 if failed and args.fail_on_error else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Inspect records without updating the DB.")
    parser.add_argument("--force", action="store_true", help="Regenerate even when refined text already exists.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of records to inspect.")
    parser.add_argument("--record-id", help="Only process one parse_records.id.")
    parser.add_argument("--provider", choices=["openai", "gemini"], help="Override refinement provider.")
    parser.add_argument("--model", help="Override refinement model.")
    parser.add_argument(
        "--include-english",
        action="store_true",
        help="Deprecated; English-source records are included by default.",
    )
    parser.add_argument(
        "--skip-english",
        action="store_true",
        help="Do not run AI refinement for records whose source text is already English.",
    )
    parser.add_argument("--store-failures", action="store_true", help="Store unavailable/failed refinement metadata.")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit non-zero if any record fails.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(asyncio.run(backfill(parse_args())))


if __name__ == "__main__":
    main()
