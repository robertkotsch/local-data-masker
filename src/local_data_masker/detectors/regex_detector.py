"""Detect sensitive data categories in tabular columns.

Detection combines two signals: the column name (e.g. "email", "dob") and the
shape of the values themselves (e.g. an email regex). Column name hints are
checked first because they are cheap and unambiguous; value patterns serve as
a fallback for unlabeled or generically named columns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\-\s().]{6,}[0-9]$")
DATE_RE = re.compile(r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}$|^\d{1,2}[/-]\d{1,2}[/-]\d{4}$")
IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$")

# Column-name keywords that exclude a column from the "name" category even
# though they contain the substring "name" (e.g. "company_name").
NAME_EXCLUSIONS = (
    "company",
    "course",
    "project",
    "department",
    "product",
    "file",
    "document",
    "supplier",
    "organization",
    "organisation",
)

CATEGORY_NAME = "name"
CATEGORY_EMAIL = "email"
CATEGORY_PHONE = "phone"
CATEGORY_DATE_OF_BIRTH = "date_of_birth"
CATEGORY_DATE = "date"
CATEGORY_IBAN = "iban"
CATEGORY_ID = "id"


@dataclass(frozen=True)
class ColumnClassification:
    column: str
    category: str | None
    confidence: float


def _matches_ratio(values: list[str], pattern: re.Pattern) -> float:
    candidates = [v for v in values if v.strip()]
    if not candidates:
        return 0.0
    matches = sum(1 for v in candidates if pattern.match(v.strip()))
    return matches / len(candidates)


def classify_column(column: str, values: list[str]) -> ColumnClassification:
    name = column.strip().lower()

    if "email" in name or "e-mail" in name:
        return ColumnClassification(column, CATEGORY_EMAIL, 0.95)
    if "iban" in name:
        return ColumnClassification(column, CATEGORY_IBAN, 0.95)
    if "phone" in name or "tel" in name or "mobile" in name:
        return ColumnClassification(column, CATEGORY_PHONE, 0.9)
    if "dob" in name or "birth" in name:
        return ColumnClassification(column, CATEGORY_DATE_OF_BIRTH, 0.9)
    if "date" in name:
        return ColumnClassification(column, CATEGORY_DATE, 0.85)
    if "id" in name.split("_") or name.endswith("id") or "number" in name:
        return ColumnClassification(column, CATEGORY_ID, 0.8)
    if "name" in name and not any(excl in name for excl in NAME_EXCLUSIONS):
        return ColumnClassification(column, CATEGORY_NAME, 0.85)

    # Fall back to value-shape detection for unlabeled columns.
    email_ratio = _matches_ratio(values, EMAIL_RE)
    if email_ratio >= 0.6:
        return ColumnClassification(column, CATEGORY_EMAIL, round(email_ratio, 2))

    iban_ratio = _matches_ratio(values, IBAN_RE)
    if iban_ratio >= 0.6:
        return ColumnClassification(column, CATEGORY_IBAN, round(iban_ratio, 2))

    phone_ratio = _matches_ratio(values, PHONE_RE)
    if phone_ratio >= 0.6:
        return ColumnClassification(column, CATEGORY_PHONE, round(phone_ratio, 2))

    date_ratio = _matches_ratio(values, DATE_RE)
    if date_ratio >= 0.6:
        return ColumnClassification(column, CATEGORY_DATE, round(date_ratio, 2))

    return ColumnClassification(column, None, 0.0)


def classify_dataframe(df: pd.DataFrame) -> list[ColumnClassification]:
    classifications = []
    for column in df.columns:
        values = df[column].astype(str).tolist()
        classifications.append(classify_column(str(column), values))
    return classifications
