"""Load custom masking profiles and apply project-specific rules.

Profiles are intentionally simple YAML files. They allow users to add exact or
substring replacements and define semantic column categories such as
``course_title`` or ``project_name`` without changing Python code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from local_data_masker.detectors.regex_detector import ColumnClassification


@dataclass(frozen=True)
class CategoryRule:
    """A semantic masking rule for a group of columns."""

    category: str
    columns: tuple[str, ...]
    replacements: tuple[str, ...]
    confidence: float = 0.9


@dataclass
class MaskingProfile:
    """User-configurable masking profile.

    ``custom_replacements`` are applied to cell text first. This supports cases
    such as ``Money Laundering`` -> ``Healthy Nutrition`` even when the value is
    embedded in a longer string.

    ``column_categories`` map column-name hints to replacement pools. This is the
    first implementation step toward semantic masking.
    """

    custom_replacements: dict[str, str] = field(default_factory=dict)
    column_categories: dict[str, CategoryRule] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "MaskingProfile":
        return cls()

    @classmethod
    def from_file(cls, path: Path) -> "MaskingProfile":
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Masking profile must be a YAML mapping: {path}")

        custom_replacements = _load_custom_replacements(raw.get("custom_replacements", {}))
        column_categories = _load_column_categories(raw.get("column_categories", {}))
        return cls(custom_replacements=custom_replacements, column_categories=column_categories)

    def classify_column(self, column: str) -> ColumnClassification | None:
        """Return a semantic classification for a column, if a profile rule matches."""
        normalized_column = _normalize_column_name(column)

        for rule in self.column_categories.values():
            hints = rule.columns or (rule.category,)
            for hint in hints:
                normalized_hint = _normalize_column_name(hint)
                if _column_matches_hint(normalized_column, normalized_hint):
                    return ColumnClassification(column=column, category=rule.category, confidence=rule.confidence)

        return None

    def apply_custom_replacements(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """Apply exact/substring custom replacements to a cell value.

        Returns the transformed text and the list of replacement pairs that were
        used. Matching is case-insensitive, while the configured replacement text
        is inserted as-is.
        """
        result = text
        matches: list[tuple[str, str]] = []

        for original, replacement in sorted(self.custom_replacements.items(), key=lambda item: len(item[0]), reverse=True):
            if not original:
                continue
            pattern = re.compile(re.escape(original), flags=re.IGNORECASE)
            if pattern.search(result):
                result = pattern.sub(replacement, result)
                matches.append((original, replacement))

        return result, matches

    def replacements_for_category(self, category: str) -> tuple[str, ...]:
        rule = self.column_categories.get(category)
        if rule is None:
            return ()
        return rule.replacements



def _load_custom_replacements(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("custom_replacements must be a mapping")
    return {str(original): str(replacement) for original, replacement in raw.items()}



def _load_column_categories(raw: Any) -> dict[str, CategoryRule]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("column_categories must be a mapping")

    rules: dict[str, CategoryRule] = {}
    for category, config in raw.items():
        category_name = str(category)

        if isinstance(config, list):
            columns = (category_name,)
            replacements = tuple(str(item) for item in config)
            confidence = 0.9
        elif isinstance(config, dict):
            columns = tuple(str(item) for item in config.get("columns", [category_name]))
            replacements = tuple(str(item) for item in config.get("replacements", []))
            confidence = float(config.get("confidence", 0.9))
        else:
            raise ValueError(f"Invalid category rule for {category_name!r}")

        rules[category_name] = CategoryRule(
            category=category_name,
            columns=columns,
            replacements=replacements,
            confidence=confidence,
        )

    return rules



def _normalize_column_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")



def _column_matches_hint(column: str, hint: str) -> bool:
    if not hint:
        return False
    return column == hint or column.endswith(f"_{hint}") or hint in column
