"""Track original-to-fake value mappings for consistent masking."""

from __future__ import annotations

import json
from pathlib import Path


class MappingStore:
    """Maps (category, original_value) to a fake value.

    Used in consistent mode so repeated occurrences of the same original
    value always receive the same fake replacement. The mapping file is
    sensitive (it links real values to their fake counterparts) and should
    be treated like any other secret.
    """

    def __init__(self) -> None:
        self._mapping: dict[str, str] = {}

    @staticmethod
    def _key(category: str, original: str) -> str:
        return f"{category}::{original}"

    def get(self, category: str, original: str) -> str | None:
        return self._mapping.get(self._key(category, original))

    def set(self, category: str, original: str, fake: str) -> None:
        self._mapping[self._key(category, original)] = fake

    def load(self, path: Path) -> None:
        if path.exists():
            self._mapping = json.loads(path.read_text(encoding="utf-8"))

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self._mapping, indent=2, sort_keys=True), encoding="utf-8")
