"""Apply detected classifications to a DataFrame, producing masked data and
an audit trail of replacements."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from local_data_masker.detectors.regex_detector import ColumnClassification
from local_data_masker.maskers.faker_provider import FakerProvider
from local_data_masker.maskers.mapping_store import MappingStore


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
) -> tuple[pd.DataFrame, list[Replacement]]:
    masked_df = df.copy()
    replacements: list[Replacement] = []

    classified = {c.column: c for c in classifications if c.category is not None}

    for column, classification in classified.items():
        category = classification.category
        for row_index, original in df[column].items():
            original_str = str(original)
            if not original_str.strip():
                continue

            fake_value = None
            if consistent:
                fake_value = mapping_store.get(category, original_str)

            if fake_value is None:
                fake_value = faker_provider.generate(category, original_str)
                if consistent:
                    mapping_store.set(category, original_str, fake_value)

            masked_df.at[row_index, column] = fake_value
            replacements.append(
                Replacement(
                    sheet=sheet_name,
                    column=column,
                    row=int(row_index),
                    category=category,
                    original=original_str,
                    masked=fake_value,
                    confidence=classification.confidence,
                )
            )

    return masked_df, replacements
