"""Backward-compatible import shim for the complaint parser module."""

from complaint_parsing import (  # noqa: F401
    get_translation_config,
    load_dotenv,
    normalize_lines,
    parse_document,
    process_document_bytes,
    process_document_sample,
)
