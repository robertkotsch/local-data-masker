"""Write a JSON audit report describing every replacement made."""

from __future__ import annotations

import json
from pathlib import Path

from local_data_masker.maskers.replacer import Replacement


def build_report(source_file: str, masked_file: str, replacements: list[Replacement], omit_originals: bool) -> dict:
    return {
        "source_file": source_file,
        "masked_file": masked_file,
        "replacements": [
            {
                "sheet": r.sheet,
                "column": r.column,
                "row": r.row,
                "category": r.category,
                **({} if omit_originals else {"original": r.original}),
                "masked": r.masked,
                "confidence": r.confidence,
            }
            for r in replacements
        ],
    }


def write_report(reports: list[dict], path: Path) -> None:
    path.write_text(json.dumps(reports, indent=2), encoding="utf-8")
