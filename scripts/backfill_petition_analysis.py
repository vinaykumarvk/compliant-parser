"""Backfill petition_analysis for pre-existing cases.

Reads each case that has no petition_analysis yet, gathers data from:
  1. The case's own columns (brief_facts, offence_type, date_of_occurrence, case_type)
  2. Audit logs (AI_Analysis entries linked to the case) for suggestion_id, provider, model
  3. CaseIntakeSuggestion audit logs (matched by suggestion_id) for risk_flags / rationale

Then writes a petition_analysis JSON payload to the case row.

Usage:
    python scripts/backfill_petition_analysis.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine


async def run_backfill(dry_run: bool = False) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # Try loading from .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL=") and not line.startswith("#"):
                        database_url = line.split("=", 1)[1]
                        break
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    engine = create_async_engine(database_url, echo=False)

    async with engine.begin() as conn:
        # 1. Get all cases without petition_analysis
        cases_rows = await conn.execute(sa.text("""
            SELECT id, case_type, offence_type, brief_facts, date_of_occurrence
            FROM cases
            WHERE petition_analysis IS NULL AND is_deleted = false
            ORDER BY created_at
        """))
        cases = cases_rows.fetchall()
        print(f"Found {len(cases)} cases without petition_analysis")

        if not cases:
            print("Nothing to backfill.")
            return

        # 2. Get AI_Analysis audit logs linked to cases
        case_audit_rows = await conn.execute(sa.text("""
            SELECT entity_id, action_details
            FROM audit_logs
            WHERE action_type = 'AI_Analysis'
              AND entity_type = 'Case'
        """))
        case_audits: dict[str, dict] = {}
        for row in case_audit_rows.fetchall():
            try:
                details = json.loads(row[1]) if isinstance(row[1], str) else row[1]
                case_audits[row[0]] = details
            except (json.JSONDecodeError, TypeError):
                pass

        # 3. Get CaseIntakeSuggestion audit logs (for risk_flags, rationale)
        suggestion_audit_rows = await conn.execute(sa.text("""
            SELECT entity_id, action_details
            FROM audit_logs
            WHERE action_type = 'AI_Analysis'
              AND entity_type = 'CaseIntakeSuggestion'
        """))
        suggestion_audits: dict[str, dict] = {}
        for row in suggestion_audit_rows.fetchall():
            try:
                details = json.loads(row[1]) if isinstance(row[1], str) else row[1]
                suggestion_audits[row[0]] = details
            except (json.JSONDecodeError, TypeError):
                pass

        # 4. Build and apply petition_analysis for each case
        updated = 0
        skipped = 0
        for case_row in cases:
            case_id = case_row[0]
            case_type = case_row[1]
            offence_type = case_row[2]
            brief_facts = case_row[3]
            date_of_occurrence = case_row[4]

            # Skip cases with no useful data at all
            if not brief_facts and not offence_type:
                skipped += 1
                continue

            # Build payload from case data
            payload: dict = {
                "brief_facts": brief_facts,
                "offence_type": offence_type,
                "case_type": case_type,
                "date_of_occurrence": date_of_occurrence.isoformat() if date_of_occurrence else None,
                "risk_flags": [],
                "backfilled": True,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }

            # Enrich from audit log if available
            audit = case_audits.get(case_id)
            if audit:
                payload["suggestion_id"] = audit.get("suggestion_id")
                payload["rationale"] = audit.get("rationale")
                # Provider info
                payload["offence_confidence"] = audit.get("offence_confidence")

                # Try to get richer data from the suggestion audit
                suggestion_id = audit.get("suggestion_id")
                if suggestion_id and suggestion_id in suggestion_audits:
                    sug = suggestion_audits[suggestion_id]
                    payload["risk_flags"] = sug.get("risk_flags", [])

            if dry_run:
                print(f"  [DRY RUN] Case {case_id[:8]}... offence={offence_type or '(none)'} "
                      f"has_audit={'yes' if audit else 'no'}")
            else:
                await conn.execute(
                    sa.text("UPDATE cases SET petition_analysis = :pa WHERE id = :id"),
                    {"pa": json.dumps(payload, default=str), "id": case_id},
                )
                updated += 1

        print(f"\nBackfill complete: {updated} updated, {skipped} skipped (no facts/offence)")
        if dry_run:
            print("(Dry run — no changes committed)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill petition_analysis for existing cases")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()
    asyncio.run(run_backfill(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
