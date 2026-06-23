"""Read CSV and Excel files into pandas DataFrames."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xls"}


class UnsupportedFileError(ValueError):
    pass


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_SUFFIXES


def load_table(path: Path) -> dict[str, pd.DataFrame]:
    """Load a CSV or Excel file.

    Returns a mapping of sheet name to DataFrame. CSV files yield a single
    sheet named "Sheet1" so callers can treat both formats uniformly.
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return {"Sheet1": pd.read_csv(path, dtype=str, keep_default_na=False)}
    if suffix in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None, dtype=str, keep_default_na=False)
        return dict(sheets)
    raise UnsupportedFileError(f"Unsupported file type: {path.suffix}")
