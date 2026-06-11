"""One-shot recovery: move parse_records/case_documents binaries from local-disk
object storage into GCS, then rewrite their URIs from local:// to gs://.

Run dry-run first (default), then again with --apply.

Uses the psql CLI for DB I/O (no extra Python deps required) and google-cloud-storage
for uploads (already in the project's requirements).
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from google.cloud import storage

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_ROOT = REPO_ROOT / ".object-storage"


@dataclass
class Row:
    table: str
    id: str
    file_name: str
    file_storage_uri: str


def psql_query(db_url: str, sql: str) -> list[list[str]]:
    result = subprocess.run(
        ["psql", db_url, "-tAF", "\t", "-c", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.split("\t") for line in result.stdout.strip().splitlines() if line]


def psql_exec(db_url: str, sql: str, params: list[str]) -> int:
    full = "BEGIN; " + sql + " ; SELECT 'ROWS:' || row_count FROM (SELECT pg_catalog.pg_stat_get_xact_tuples_updated(0) AS row_count) s; COMMIT;"
    cmd = ["psql", db_url, "-tA", "-v", "ON_ERROR_STOP=1"]
    for i, p in enumerate(params, start=1):
        cmd.extend(["-v", f"p{i}={p}"])
    cmd.extend(["-c", full])
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith("ROWS:"):
            return int(line.split(":", 1)[1])
    return 0


def fetch_rows(db_url: str) -> list[Row]:
    rows: list[Row] = []
    for table in ("parse_records", "case_documents"):
        sql = (
            f"SELECT id, COALESCE(file_name,'document'), file_storage_uri "
            f"FROM {table} WHERE file_storage_uri LIKE 'local://%' ORDER BY id"
        )
        for rid, fname, uri in psql_query(db_url, sql):
            rows.append(Row(table=table, id=rid, file_name=fname, file_storage_uri=uri))
    return rows


def update_uri(db_url: str, table: str, row_id: str, old_uri: str, new_uri: str) -> int:
    """Update single row by id+old_uri; return affected rowcount."""
    safe = old_uri.replace("'", "''")
    new_safe = new_uri.replace("'", "''")
    rid_safe = row_id.replace("'", "''")
    sql = (
        f"WITH upd AS (UPDATE {table} SET file_storage_uri = '{new_safe}' "
        f"WHERE id = '{rid_safe}' AND file_storage_uri = '{safe}' RETURNING 1) "
        "SELECT count(*) FROM upd"
    )
    rows = psql_query(db_url, sql)
    return int(rows[0][0]) if rows else 0


def local_path(uri: str) -> Path:
    return LOCAL_ROOT / uri.removeprefix("local://")


def gcs_key(uri: str) -> str:
    return uri.removeprefix("local://")


def detect_content_type(name: str) -> str:
    guess, _ = mimetypes.guess_type(name)
    return guess or "application/octet-stream"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True, help="GCS bucket name")
    ap.add_argument("--db-url", default=os.environ.get("RECOVERY_DB_URL"),
                    help="libpq URL (default $RECOVERY_DB_URL)")
    ap.add_argument("--apply", action="store_true", help="actually upload + update DB")
    args = ap.parse_args()

    if not args.db_url:
        print("ERROR: --db-url or RECOVERY_DB_URL required", file=sys.stderr)
        return 2

    client = storage.Client()
    bucket = client.bucket(args.bucket)

    rows = fetch_rows(args.db_url)
    print(f"Found {len(rows)} rows with local:// URIs across parse_records + case_documents")

    plan: list[tuple[Row, Path, str, str]] = []
    missing: list[Row] = []

    for row in rows:
        src = local_path(row.file_storage_uri)
        if not src.exists():
            missing.append(row)
            continue
        key = gcs_key(row.file_storage_uri)
        gs_uri = f"gs://{args.bucket}/{key}"
        plan.append((row, src, key, gs_uri))

    print(f"  recoverable: {len(plan)}")
    print(f"  missing on disk: {len(missing)}")
    for m in missing:
        print(f"    - {m.table}/{m.id}  {m.file_storage_uri}")

    print("\nUpload + URI rewrite plan:")
    for row, src, key, gs_uri in plan:
        size = src.stat().st_size
        print(f"  {row.table:16s}  {row.id}  {size:>8d}B  -> {gs_uri}")

    if not args.apply:
        print("\nDRY-RUN (no changes). Re-run with --apply to execute.")
        return 0

    print("\nExecuting...")
    uploaded_count = 0
    updated_count = 0
    for row, src, key, gs_uri in plan:
        blob = bucket.blob(key)
        if blob.exists():
            print(f"  GCS object already present: {key}")
        else:
            blob.upload_from_filename(str(src), content_type=detect_content_type(row.file_name))
            uploaded_count += 1
            print(f"  uploaded: {key}")

        n = update_uri(args.db_url, row.table, row.id, row.file_storage_uri, gs_uri)
        if n != 1:
            raise RuntimeError(
                f"Expected 1 row updated for {row.table}.{row.id}, got {n}"
            )
        updated_count += 1

    print(f"\nUploaded {uploaded_count} new objects.")
    print(f"Updated {updated_count} DB rows.")
    if missing:
        print(f"Left {len(missing)} unrecoverable rows untouched (binaries gone).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
