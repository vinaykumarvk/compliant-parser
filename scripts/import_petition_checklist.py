#!/usr/bin/env python3
"""Import the petition scrutiny checklist PDF into petition_checklist_questions."""

from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from complaint_parsing import load_dotenv
from database import dispose_engine, get_engine, initialize_database, petition_checklist_questions


DEFAULT_PDF = ROOT / "docs" / "Petition checklist.pdf"


SECTION_CATEGORY_MAP = {
    "Receipt, jurisdiction, and basic FIR scrutiny": ("general", "petition,fir"),
    "Informant/complainant details": ("informant", "petition,fir,court_preparation"),
    "Victim details": ("victim", "petition,fir,investigation,court_preparation"),
    "Accused/suspect details": ("accused", "petition,fir,investigation,court_preparation"),
    "Incident essentials: who, what, when, where, how, why": ("incident", "petition,fir,investigation,court_preparation"),
    "Scene of offence and local surroundings": ("scene", "petition,investigation,court_preparation"),
    "Delay, first disclosure, and post-incident conduct": ("delay_disclosure", "petition,investigation,court_preparation"),
    "Witnesses": ("witnesses", "petition,investigation,court_preparation"),
    "Physical, documentary, medical, and digital evidence": ("evidence", "petition,investigation,court_preparation"),
    "Medical and forensic requirements": ("medical_forensic", "investigation,court_preparation"),
    "Legal ingredient check": ("legal_ingredients", "fir,court_preparation"),
    "Court-proofing questions": ("court_proofing", "court_preparation"),
}

OFFENCE_HEADINGS = {
    "Missing person, kidnapping, abduction, elopement, trafficking": "missing_person",
    "Sexual offences involving adult victims": "sexual_offence",
    "POCSO / child sexual offence": "pocso",
    "SC/ST Prevention of Atrocities cases": "sc_st_atrocity",
    "Murder, suspicious death, attempt to murder, grievous hurt": "murder_grievous_hurt",
    "Theft, house-breaking, burglary, robbery, dacoity": "theft",
    "Cheating, fraud, forgery, breach of trust, financial crime": "financial_crime",
    "Cybercrime and digital harassment": "cybercrime",
    "Domestic violence, cruelty, dowry, matrimonial offences": "domestic_violence",
    "Criminal intimidation, extortion, stalking, harassment": "intimidation_harassment",
    "Road accident, hit-and-run, rash/negligent driving": "road_accident",
    "Riot, unlawful assembly, group assault, communal/caste/public order offences": "public_order",
    "Land/property trespass, criminal intimidation in civil disputes": "land_property",
    "NDPS/contraband/special statute complaints": "special_statute",
    "Corruption/bribery/public servant complaint": "corruption",
}


def _pdf_to_text(path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", str(path), "-"],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def _clean_line(value: str) -> str:
    value = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _severity_from_marker(marker: str) -> str:
    return "mandatory" if marker == "E" else "recommended"


def _section_metadata(section: str, offence_type: str | None) -> tuple[str, str]:
    if offence_type:
        return "specific_offence", "petition,investigation,court_preparation"
    return SECTION_CATEGORY_MAP.get(section, ("general", "petition"))


def _finalize_item(
    items: list[dict[str, Any]],
    buffer: list[str],
    *,
    checklist_version: int,
    section: str,
    offence_type: str | None,
    display_order: int,
) -> int:
    if not buffer:
        return display_order
    text = _clean_line(" ".join(buffer))
    if not text:
        return display_order
    match = re.match(r"(.+?(?:\?|\.))\s*([EG])(?:\s|$)(.*)", text)
    if match:
        question = _clean_line(match.group(1))
        severity = _severity_from_marker(match.group(2))
        guidance = _clean_line(match.group(3))
    elif section == "Court-proofing questions":
        court_match = re.match(r"(.+?\?)\s*(.*)", text)
        if not court_match:
            return display_order
        question = _clean_line(court_match.group(1))
        severity = "recommended"
        guidance = _clean_line(court_match.group(2))
    else:
        return display_order
    category, purpose = _section_metadata(section, offence_type)
    display_order += 1
    items.append(
        {
            "id": str(uuid.uuid4()),
            "checklist_version": checklist_version,
            "category": category,
            "purpose": purpose,
            "offence_type": offence_type,
            "question_text": question,
            "expected_field_key": None,
            "severity": severity,
            "source_section": section,
            "guidance": guidance or None,
            "display_order": display_order,
            "is_active": True,
            "created_by": "checklist_import",
        }
    )
    return display_order


def extract_checklist_items(text: str, *, checklist_version: int = 1) -> list[dict[str, Any]]:
    lines = [_clean_line(line) for line in text.replace("\f", "\n").splitlines()]
    items: list[dict[str, Any]] = []
    buffer: list[str] = []
    section = "Universal checklist"
    offence_type: str | None = None
    in_crime_specific = False
    in_court_proofing = False
    display_order = 0

    heading_continuation = ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("2. Crime-specific"):
            display_order = _finalize_item(items, buffer, checklist_version=checklist_version, section=section, offence_type=offence_type, display_order=display_order)
            buffer = []
            in_crime_specific = True
            in_court_proofing = False
            offence_type = None
            section = "Crime-specific add-on questions"
            continue
        if line.startswith("3. Court-proofing"):
            display_order = _finalize_item(items, buffer, checklist_version=checklist_version, section=section, offence_type=offence_type, display_order=display_order)
            buffer = []
            in_crime_specific = False
            in_court_proofing = True
            offence_type = None
            section = "Court-proofing questions"
            continue
        if line.startswith("4. Suggested") or line.startswith("5. Final"):
            display_order = _finalize_item(items, buffer, checklist_version=checklist_version, section=section, offence_type=offence_type, display_order=display_order)
            buffer = []
            in_crime_specific = False
            in_court_proofing = False
            offence_type = None
            section = line
            continue

        subsection = re.match(r"^([A-O])\.\s+(.+)$", line)
        if subsection:
            display_order = _finalize_item(items, buffer, checklist_version=checklist_version, section=section, offence_type=offence_type, display_order=display_order)
            buffer = []
            heading = subsection.group(2).strip()
            if heading.endswith(",") or heading.endswith("and"):
                heading_continuation = heading
                continue
            heading_continuation = ""
            section = heading
            offence_type = OFFENCE_HEADINGS.get(section) if in_crime_specific else None
            if in_court_proofing:
                section = "Court-proofing questions"
            continue
        if heading_continuation:
            section = (heading_continuation + " " + line).strip()
            heading_continuation = ""
            offence_type = OFFENCE_HEADINGS.get(section) if in_crime_specific else None
            continue

        numbered = re.match(r"^(\d+)\.\s*(.+)$", line)
        if numbered and not re.match(r"^\d+\.\s+(Universal|Crime-specific|Court-proofing|Suggested|Final)\b", line):
            display_order = _finalize_item(items, buffer, checklist_version=checklist_version, section=section, offence_type=offence_type, display_order=display_order)
            buffer = [numbered.group(2)]
            continue
        if buffer:
            buffer.append(line)

    _finalize_item(items, buffer, checklist_version=checklist_version, section=section, offence_type=offence_type, display_order=display_order)
    return items


async def import_items(items: list[dict[str, Any]], *, dry_run: bool = False) -> dict[str, int]:
    engine = await get_engine()
    inserted = 0
    updated = 0
    skipped = 0
    async with engine.begin() as conn:
        for item in items:
            existing = await conn.execute(
                sa.select(petition_checklist_questions.c.id).where(
                    petition_checklist_questions.c.checklist_version == item["checklist_version"],
                    petition_checklist_questions.c.question_text == item["question_text"],
                )
            )
            existing_id = existing.scalar()
            if dry_run:
                skipped += 1
                continue
            values = {key: value for key, value in item.items() if key != "id"}
            if existing_id:
                await conn.execute(
                    petition_checklist_questions.update()
                    .where(petition_checklist_questions.c.id == existing_id)
                    .values(**values, updated_by="checklist_import", updated_at=sa.func.now())
                )
                updated += 1
            else:
                await conn.execute(petition_checklist_questions.insert().values(**item))
                inserted += 1
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


async def main_async() -> int:
    args = parse_args()
    load_dotenv()
    await initialize_database()
    text = _pdf_to_text(args.pdf)
    items = extract_checklist_items(text, checklist_version=args.version)
    result = await import_items(items, dry_run=args.dry_run)
    await dispose_engine()
    print(f"Extracted {len(items)} checklist item(s). inserted={result['inserted']} updated={result['updated']} skipped={result['skipped']}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
