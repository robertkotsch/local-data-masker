"""Apply detected classifications to a DataFrame, producing masked data and
an audit trail of replacements."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from local_data_masker.detectors.custom_rules import MaskingProfile
from local_data_masker.detectors.regex_detector import (
    CATEGORY_DATE,
    CATEGORY_DATE_OF_BIRTH,
    CATEGORY_EMAIL,
    CATEGORY_IBAN,
    CATEGORY_ID,
    CATEGORY_NAME,
    CATEGORY_PHONE,
    DATE_RE,
    EMAIL_RE,
    IBAN_RE,
    PHONE_RE,
    ColumnClassification,
)
from local_data_masker.maskers.faker_provider import FakerProvider
from local_data_masker.maskers.mapping_store import MappingStore
from local_data_masker.maskers.semantic_replacer import generate_semantic_replacement

PLACEHOLDER_VALUES = {"", "-", "--", "n/a", "na", "none", "null", "nan"}
SEMANTIC_CATEGORIES = {
    "course_title",
    "training_name",
    "topic",
    "company",
    "organization",
    "organisation",
    "customer",
    "supplier",
    "project_name",
    "project",
    "department",
    "product_name",
    "product",
}


@dataclass(frozen=True)
class Replacement:
    sheet: str
    column: str
    row: int
    category: str
    original: str
    masked: str
    confidence: float


def mask_dataframe(
    df: pd.DataFrame,
    classifications: list[ColumnClassification],
    sheet_name: str,
    faker_provider: FakerProvider,
    consistent: bool,
    mapping_store: MappingStore,
    profile: MaskingProfile | None = None,
) -> tuple[pd.DataFrame, list[Replacement]]:
    masked_df = df.copy()
    replacements: list[Replacement] = []
    active_profile = profile or MaskingProfile.empty()

    classified = {c.column: c for c in classifications if c.category is not None}

    # Iterate over all cells, not only classified columns. This allows profile
    # custom replacements to catch sensitive terms inside otherwise harmless
    # columns such as notes or descriptions.
    for column in df.columns:
        column_name = str(column)
        classification = classified.get(column_name)

        for row_index, original in df[column].items():
            original_str = str(original)
            if _is_placeholder(original_str):
                continue

            fake_value: str | None = None
            category: str | None = None
            confidence = 0.0

            custom_value, custom_matches = active_profile.apply_custom_replacements(original_str)
            if custom_matches:
                fake_value = custom_value
                category = "custom_replacement"
                confidence = 1.0

            if fake_value is None and classification is not None:
                category = classification.category
                confidence = classification.confidence
                if not _should_mask_value(category, original_str):
                    continue

                if consistent:
                    fake_value = mapping_store.get(category, original_str)

                if fake_value is None:
                    if category in SEMANTIC_CATEGORIES:
                        fake_value = generate_semantic_replacement(category, original_str, active_profile, faker_provider)
                    else:
                        fake_value = faker_provider.generate(category, original_str)

                    if consistent:
                        mapping_store.set(category, original_str, fake_value)

            if fake_value is None or category is None or fake_value == original_str:
                continue

            masked_df.at[row_index, column] = fake_value
            replacements.append(
                Replacement(
                    sheet=sheet_name,
                    column=column_name,
                    row=int(row_index),
                    category=category,
                    original=original_str,
                    masked=fake_value,
                    confidence=confidence,
                )
            )

    return masked_df, replacements


def _is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDER_VALUES


def _should_mask_value(category: str, value: str) -> bool:
    stripped = value.strip()
    if _is_placeholder(stripped):
        return False

    if category == CATEGORY_EMAIL:
        return bool(EMAIL_RE.match(stripped))
    if category == CATEGORY_IBAN:
        return bool(IBAN_RE.match(stripped))
    if category == CATEGORY_PHONE:
        return bool(PHONE_RE.match(stripped))
    if category in {CATEGORY_DATE, CATEGORY_DATE_OF_BIRTH}:
        return bool(DATE_RE.match(stripped))
    if category == CATEGORY_ID:
        return any(char.isdigit() for char in stripped)
    if category == CATEGORY_NAME:
        return any(char.isalpha() for char in stripped)
    if category in SEMANTIC_CATEGORIES:
        return bool(stripped)

    return bool(stripped)
