# Filename / Path Masking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mask PII-bearing components of output file paths so a masked dataset does not leak identities through its folder/file names or its report, keeping the masked filename coherent with the identity masked inside the file.

**Architecture:** A new `maskers/path_masker.py` maps a source file's relative path to a masked relative path. It is pattern-driven (profile `filename_patterns`), fills name groups content-first (the file's primary fake identity) with a filename-parse fallback, and falls back to an opaque `record_NNNN` token. The pipeline hoists the per-file `EntityMasker` so the path masker shares its identity caches, and the report omits the original source path by default.

**Tech Stack:** Python 3.10+, pandas, Faker, Typer, PyYAML, pytest. Windows dev shell is PowerShell; tests run via the project venv.

## Global Constraints

- Python >= 3.10; use `from __future__ import annotations` and `X | None` syntax (matches existing modules).
- Value objects are `@dataclass(frozen=True)` where they are immutable.
- No original/raw values in normal logs; reports omit originals unless `--include-originals`.
- Run tests with the project venv: `.venv\Scripts\python.exe -m pytest` (PowerShell) — set `$env:PYTHONUTF8=1` for Unicode test data.
- TDD: write the failing test, watch it fail, minimal code, watch it pass, commit. One behavior per test.
- Category constants live in `detectors/regex_detector.py`: `CATEGORY_NAME="name"`, `CATEGORY_DATE_OF_BIRTH="date_of_birth"`, `CATEGORY_ID="id"`.

## Known limitation (documented, intentional)

Name coherence between filename and content is guaranteed (via the shared primary identity / entity cache). Date-of-birth coherence holds only when the in-file date string and the filename date string share the same day/month/year ordering (both are normalized to a `.`-separated key before masking). A masked filename DOB is always a *valid* masked date; it may differ from the in-file masked DOB when the two formats disagree. This is out of scope to fully unify.

---

### Task 1: Profile `filename_patterns`

**Files:**
- Modify: `src/local_data_masker/detectors/custom_rules.py` (add field to `MaskingProfile`, parse in `from_file`, add `_load_filename_patterns`)
- Test: `tests/test_profiles.py`

**Interfaces:**
- Produces: `MaskingProfile.filename_patterns: tuple[re.Pattern, ...]` (compiled, in declaration order). `MaskingProfile.empty()` returns one with `filename_patterns=()`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_profiles.py`:

```python
import re
import pytest


def test_filename_patterns_compile_with_named_groups(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        """
filename_patterns:
  - "(?P<name_last>[^_]+)_(?P<name_first>[^_]+)_(?P<dob>\\\\d{2}_\\\\d{2}_\\\\d{4})"
""".strip(),
        encoding="utf-8",
    )
    profile = MaskingProfile.from_file(profile_path)

    assert len(profile.filename_patterns) == 1
    match = profile.filename_patterns[0].search("Abaira_Amina_14_12_1990")
    assert match is not None
    assert match.group("name_last") == "Abaira"
    assert match.group("name_first") == "Amina"
    assert match.group("dob") == "14_12_1990"


def test_malformed_filename_pattern_raises(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        'filename_patterns:\n  - "(?P<bad>["\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        MaskingProfile.from_file(profile_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_profiles.py::test_filename_patterns_compile_with_named_groups -v`
Expected: FAIL — `MaskingProfile` has no attribute `filename_patterns`.

- [ ] **Step 3: Write minimal implementation**

In `custom_rules.py`, add the field to the dataclass (after `column_categories`):

```python
    column_categories: dict[str, CategoryRule] = field(default_factory=dict)
    filename_patterns: tuple[re.Pattern, ...] = ()
```

In `from_file`, after building `column_categories`:

```python
        custom_replacements = _load_custom_replacements(raw.get("custom_replacements", {}))
        column_categories = _load_column_categories(raw.get("column_categories", {}))
        filename_patterns = _load_filename_patterns(raw.get("filename_patterns", []))
        return cls(
            custom_replacements=custom_replacements,
            column_categories=column_categories,
            filename_patterns=filename_patterns,
        )
```

Add module-level helper (near the other `_load_*` functions):

```python
def _load_filename_patterns(raw: Any) -> tuple[re.Pattern, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError("filename_patterns must be a list of regex strings")
    patterns: list[re.Pattern] = []
    for item in raw:
        try:
            patterns.append(re.compile(str(item)))
        except re.error as exc:
            raise ValueError(f"Invalid filename pattern {item!r}: {exc}") from exc
    return tuple(patterns)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_profiles.py -v`
Expected: PASS (both new tests and the existing ones).

- [ ] **Step 5: Commit**

```bash
git add src/local_data_masker/detectors/custom_rules.py tests/test_profiles.py
git commit -m "feat: parse filename_patterns from masking profiles"
```

---

### Task 2: `EntityMasker.primary_person()` and `person_for_value()`

**Files:**
- Modify: `src/local_data_masker/maskers/entity_masker.py` (add two methods to `EntityMasker`)
- Test: `tests/test_entity_masking.py`

**Interfaces:**
- Consumes: existing `EntityMasker._cache: dict[str, EntityContext]`, `_load_or_create_person`, `_normalize_value`, `EntityContext`, `FakePerson`, `CATEGORY_NAME`.
- Produces:
  - `EntityMasker.primary_person() -> FakePerson | None` — the first identity cached this run (insertion order), else `None`.
  - `EntityMasker.person_for_value(category: str, value: str) -> FakePerson | None` — coherent fake person for a raw identity string (cached/reused by key `f"{category}:{normalized}"`); `None` for an empty value.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_entity_masking.py`:

```python
from local_data_masker.detectors.regex_detector import CATEGORY_NAME
from local_data_masker.maskers.entity_masker import EntityMasker


def test_primary_person_returns_first_cached_identity() -> None:
    masker = EntityMasker(FakerProvider(seed=5), MappingStore(), consistent=False)
    assert masker.primary_person() is None

    first = masker.person_for_value(CATEGORY_NAME, "Amina Abaira")
    masker.person_for_value(CATEGORY_NAME, "Sarra Abassi")

    assert first is not None
    assert masker.primary_person() == first


def test_person_for_value_is_coherent_for_repeated_value() -> None:
    masker = EntityMasker(FakerProvider(seed=5), MappingStore(), consistent=False)
    a = masker.person_for_value(CATEGORY_NAME, "Amina Abaira")
    b = masker.person_for_value(CATEGORY_NAME, "amina   abaira")
    assert a == b
    assert masker.person_for_value(CATEGORY_NAME, "") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_entity_masking.py::test_primary_person_returns_first_cached_identity -v`
Expected: FAIL — `EntityMasker` has no attribute `primary_person`.

- [ ] **Step 3: Write minimal implementation**

In `entity_masker.py`, add `CATEGORY_NAME` to the existing import from `regex_detector` if not already imported (it is). Add these methods to `EntityMasker` (e.g. after `context_for_row`):

```python
    def primary_person(self) -> FakePerson | None:
        """Return the first fake identity created this run, or None."""
        for context in self._cache.values():
            return context.person
        return None

    def person_for_value(self, category: str, value: str) -> FakePerson | None:
        """Return a coherent fake person for a raw identity string.

        Reuses the run cache keyed by ``f"{category}:{normalized}"`` so the same
        value (e.g. a name found only in a filename) maps to one fake identity,
        and to the same identity the content used when the keys match.
        """
        normalized = _normalize_value(value)
        if not normalized:
            return None
        key = f"{category}:{normalized}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached.person
        person = self._load_or_create_person(key)
        self._cache[key] = EntityContext(key=key, person=person)
        return person
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_entity_masking.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/local_data_masker/maskers/entity_masker.py tests/test_entity_masking.py
git commit -m "feat: expose primary and value-keyed fake identities on EntityMasker"
```

---

### Task 3: `mask_dataframe` accepts a shared `EntityMasker`

**Files:**
- Modify: `src/local_data_masker/maskers/replacer.py` (`mask_dataframe` signature + body)
- Test: `tests/test_replacer.py`

**Interfaces:**
- Consumes: `EntityMasker(faker_provider, mapping_store, consistent)`.
- Produces: `mask_dataframe(df, classifications, sheet_name, faker_provider, consistent, mapping_store, profile=None, entity_masker=None)` — when `entity_masker` is passed, it is used (and its caches persist for the caller); when `None`, one is created internally as before.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_replacer.py`:

```python
from local_data_masker.maskers.entity_masker import EntityMasker


def test_shared_entity_masker_exposes_primary_person_after_masking():
    df = pd.DataFrame({"name": ["Ben Miller"], "email": ["ben.miller@example.com"]})
    classifications = classify_dataframe(df)
    masker = EntityMasker(FakerProvider(seed=1), MappingStore(), consistent=False)

    masked_df, _ = mask_dataframe(
        df, classifications, "Sheet1", FakerProvider(seed=1),
        consistent=False, mapping_store=MappingStore(), entity_masker=masker,
    )

    primary = masker.primary_person()
    assert primary is not None
    assert masked_df.loc[0, "name"] == primary.full_name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_replacer.py::test_shared_entity_masker_exposes_primary_person_after_masking -v`
Expected: FAIL — `mask_dataframe() got an unexpected keyword argument 'entity_masker'`.

- [ ] **Step 3: Write minimal implementation**

In `replacer.py`, add the import:

```python
from local_data_masker.maskers.entity_masker import EntityMasker
```

(It is already imported — keep one import.) Change the signature:

```python
def mask_dataframe(
    df: pd.DataFrame,
    classifications: list[ColumnClassification],
    sheet_name: str,
    faker_provider: FakerProvider,
    consistent: bool,
    mapping_store: MappingStore,
    profile: MaskingProfile | None = None,
    entity_masker: EntityMasker | None = None,
) -> tuple[pd.DataFrame, list[Replacement]]:
```

Replace the internal construction line:

```python
    entity_masker = EntityMasker(faker_provider, mapping_store, consistent)
```

with:

```python
    if entity_masker is None:
        entity_masker = EntityMasker(faker_provider, mapping_store, consistent)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_replacer.py tests/test_entity_masking.py -v`
Expected: PASS (new test and all existing masking tests).

- [ ] **Step 5: Commit**

```bash
git add src/local_data_masker/maskers/replacer.py tests/test_replacer.py
git commit -m "feat: let mask_dataframe accept a shared EntityMasker"
```

---

### Task 4: `path_masker.py` — relative path → masked relative path

**Files:**
- Create: `src/local_data_masker/maskers/path_masker.py`
- Test: `tests/test_path_masker.py`

**Interfaces:**
- Consumes: `MaskingProfile.filename_patterns`, `EntityMasker.person_for_value`, `FakePerson(first_name,last_name,full_name,email)`, `FakerProvider.generate(category, original)`, `MappingStore.get/set`, `CATEGORY_NAME/CATEGORY_DATE_OF_BIRTH/CATEGORY_ID`.
- Produces:
  ```python
  mask_relative_path(
      relative_path: Path,
      primary_identity: FakePerson | None,
      profile: MaskingProfile,
      entity_masker: EntityMasker,
      faker_provider: FakerProvider,
      mapping_store: MappingStore,
      consistent: bool,
      used_paths: set[str],
      fallback_counter: Iterator[int],
  ) -> Path
  ```
  Returns a relative `Path`; preserves the final suffix; non-matching components unchanged; uniqueness enforced via `used_paths`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_path_masker.py`:

```python
import itertools
import re
from pathlib import Path

from local_data_masker.detectors.custom_rules import MaskingProfile
from local_data_masker.maskers.entity_masker import EntityMasker
from local_data_masker.maskers.faker_provider import FakePerson, FakerProvider
from local_data_masker.maskers.mapping_store import MappingStore
from local_data_masker.maskers.path_masker import mask_relative_path

PATTERN = re.compile(r"(?P<name_last>[^_]+)_(?P<name_first>[^_]+)_(?P<dob>\d{2}_\d{2}_\d{4})")


def _profile(*patterns):
    return MaskingProfile(filename_patterns=tuple(patterns))


def test_content_identity_names_the_path():
    person = FakePerson("Danielle", "Johnson", "Danielle Johnson", "danielle.johnson@example.test")
    masked = mask_relative_path(
        Path("Abaira_Amina_14_12_1990/Untersuchungskartei.pdf"),
        person, _profile(PATTERN), EntityMasker(FakerProvider(seed=1), MappingStore(), False),
        FakerProvider(seed=1), MappingStore(), False, set(), itertools.count(1),
    )
    parts = masked.parts
    assert parts[0].startswith("Johnson_Danielle_")
    assert parts[0] != "Abaira_Amina_14_12_1990"
    assert parts[1] == "Untersuchungskartei.pdf"
    assert masked.suffix == ".pdf"


def test_filename_fallback_masks_when_no_content_identity():
    em = EntityMasker(FakerProvider(seed=2), MappingStore(), False)
    masked = mask_relative_path(
        Path("Abaira_Amina_14_12_1990"), None, _profile(PATTERN), em,
        FakerProvider(seed=2), MappingStore(), False, set(), itertools.count(1),
    )
    assert str(masked) != "Abaira_Amina_14_12_1990"
    # The fallback name resolves through the shared entity cache and is reusable.
    assert em.person_for_value("name", "Amina Abaira") is not None


def test_unparseable_match_becomes_opaque_token():
    masked = mask_relative_path(
        Path("SecretProjectXYZ"), None, _profile(re.compile(r"(?P<secret>.+)")),
        EntityMasker(FakerProvider(seed=1), MappingStore(), False),
        FakerProvider(seed=1), MappingStore(), False, set(), itertools.count(1),
    )
    assert str(masked) == "record_0001"


def test_non_matching_component_is_left_unchanged():
    masked = mask_relative_path(
        Path("plain_folder/data.csv"), None, _profile(PATTERN),
        EntityMasker(FakerProvider(seed=1), MappingStore(), False),
        FakerProvider(seed=1), MappingStore(), False, set(), itertools.count(1),
    )
    assert str(masked).replace("\\", "/") == "plain_folder/data.csv"


def test_collision_appends_suffix():
    used: set[str] = set()
    person = FakePerson("Danielle", "Johnson", "Danielle Johnson", "d@e.test")
    profile = _profile(re.compile(r"(?P<name_last>[^_]+)_(?P<name_first>[^_]+)"))
    em = EntityMasker(FakerProvider(seed=1), MappingStore(), False)
    a = mask_relative_path(Path("Aa_Bb"), person, profile, em, FakerProvider(seed=1), MappingStore(), False, used, itertools.count(1))
    b = mask_relative_path(Path("Cc_Dd"), person, profile, em, FakerProvider(seed=1), MappingStore(), False, used, itertools.count(1))
    assert a != b
    assert b.name.endswith("_2")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_path_masker.py -v`
Expected: FAIL — `No module named 'local_data_masker.maskers.path_masker'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/local_data_masker/maskers/path_masker.py`:

```python
"""Mask PII-bearing components of a file's relative path, coherently with content.

A path component is rewritten only when it matches one of the profile's
``filename_patterns``. Name groups are filled content-first (the file's primary
fake identity) with a filename-parse fallback; date/id groups are masked through
the shared faker/mapping; a matched component with no usable identity becomes an
opaque ``record_NNNN`` token. Non-matching components are left unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from local_data_masker.detectors.custom_rules import MaskingProfile
from local_data_masker.detectors.regex_detector import (
    CATEGORY_DATE_OF_BIRTH,
    CATEGORY_ID,
    CATEGORY_NAME,
)
from local_data_masker.maskers.entity_masker import EntityMasker
from local_data_masker.maskers.faker_provider import FakePerson, FakerProvider
from local_data_masker.maskers.mapping_store import MappingStore

NAME_GROUPS = ("name", "name_first", "name_last")
DATE_GROUPS = ("dob", "date")
ID_GROUPS = ("id",)
RECOGNIZED_GROUPS = NAME_GROUPS + DATE_GROUPS + ID_GROUPS


def mask_relative_path(
    relative_path: Path,
    primary_identity: FakePerson | None,
    profile: MaskingProfile,
    entity_masker: EntityMasker,
    faker_provider: FakerProvider,
    mapping_store: MappingStore,
    consistent: bool,
    used_paths: set[str],
    fallback_counter: Iterator[int],
) -> Path:
    parts = relative_path.parts
    masked_parts = []
    for index, part in enumerate(parts):
        is_last = index == len(parts) - 1
        masked_parts.append(
            _mask_component(
                part, is_last, primary_identity, profile, entity_masker,
                faker_provider, mapping_store, consistent, fallback_counter,
            )
        )
    return _dedupe(Path(*masked_parts), used_paths)


def _mask_component(
    component: str,
    is_last: bool,
    primary_identity: FakePerson | None,
    profile: MaskingProfile,
    entity_masker: EntityMasker,
    faker_provider: FakerProvider,
    mapping_store: MappingStore,
    consistent: bool,
    fallback_counter: Iterator[int],
) -> str:
    leaf = Path(component)
    suffix = leaf.suffix if is_last else ""
    stem = leaf.stem if is_last else component

    for pattern in profile.filename_patterns:
        match = pattern.search(stem)
        if match is None:
            continue
        values = _masked_group_values(
            match, primary_identity, entity_masker, faker_provider, mapping_store, consistent,
        )
        if not values:
            return f"record_{next(fallback_counter):04d}{suffix}"
        return _render(stem, match, values) + suffix

    return component


def _masked_group_values(
    match: re.Match,
    primary_identity: FakePerson | None,
    entity_masker: EntityMasker,
    faker_provider: FakerProvider,
    mapping_store: MappingStore,
    consistent: bool,
) -> dict[str, str]:
    groups = {name for name in match.groupdict() if match.group(name) is not None}
    present = [g for g in RECOGNIZED_GROUPS if g in groups]
    if not present:
        return {}

    values: dict[str, str] = {}
    name_groups = [g for g in present if g in NAME_GROUPS]
    if name_groups:
        person = _resolve_person(match, name_groups, primary_identity, entity_masker)
        if person is None:
            return {}
        for g in name_groups:
            if g == "name_first":
                values[g] = person.first_name
            elif g == "name_last":
                values[g] = person.last_name
            else:  # "name"
                values[g] = person.full_name

    for g in present:
        if g in DATE_GROUPS:
            values[g] = _mask_date_token(match.group(g), faker_provider, mapping_store, consistent)
        elif g in ID_GROUPS:
            values[g] = _mask_value(CATEGORY_ID, match.group(g), faker_provider, mapping_store, consistent)

    return values


def _resolve_person(match, name_groups, primary_identity, entity_masker):
    if primary_identity is not None:
        return primary_identity
    captured = " ".join(match.group(g) for g in name_groups if match.group(g)).strip()
    return entity_masker.person_for_value(CATEGORY_NAME, captured)


def _mask_value(category, original, faker_provider, mapping_store, consistent):
    if consistent:
        existing = mapping_store.get(category, original)
        if existing:
            return existing
    fake = faker_provider.generate(category, original)
    if consistent:
        mapping_store.set(category, original, fake)
    return fake


def _mask_date_token(token, faker_provider, mapping_store, consistent):
    sep = next((c for c in token if not c.isdigit()), ".")
    normalized = token.replace(sep, ".")
    fake = _mask_value(CATEGORY_DATE_OF_BIRTH, normalized, faker_provider, mapping_store, consistent)
    return fake.replace(".", sep)


def _render(component: str, match: re.Match, values: dict[str, str]) -> str:
    spans = sorted((match.span(g)[0], match.span(g)[1], v) for g, v in values.items())
    out = []
    cursor = 0
    for start, end, value in spans:
        out.append(component[cursor:start])
        out.append(value)
        cursor = end
    out.append(component[cursor:])
    return "".join(out)


def _dedupe(path: Path, used_paths: set[str]) -> Path:
    candidate = path
    counter = 2
    while str(candidate) in used_paths:
        candidate = candidate.with_name(f"{path.stem}_{counter}{path.suffix}")
        counter += 1
    used_paths.add(str(candidate))
    return candidate
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_path_masker.py -v`
Expected: PASS (all five tests).

- [ ] **Step 5: Commit**

```bash
git add src/local_data_masker/maskers/path_masker.py tests/test_path_masker.py
git commit -m "feat: add path_masker for coherent filename/path masking"
```

---

### Task 5: `PreprocessConfig.mask_filenames` + CLI flag

**Files:**
- Modify: `src/local_data_masker/pipeline.py` (`PreprocessConfig` dataclass)
- Modify: `src/local_data_masker/cli.py` (`mask` command)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `PreprocessConfig.mask_filenames: bool = True`; CLI `mask` flag `--mask-filenames/--keep-filenames` (default true) wired to `mask_filenames`.

- [ ] **Step 1: Write the failing test**

Inspect `tests/test_cli.py` for the existing CliRunner pattern, then add a test that `--keep-filenames` is accepted and a single-file mask still works (the flag must exist):

```python
def test_mask_accepts_keep_filenames_flag(tmp_path):
    from typer.testing import CliRunner
    from local_data_masker.cli import app

    input_path = tmp_path / "raw.csv"
    output_path = tmp_path / "out.csv"
    input_path.write_text("name\nBen Miller\n", encoding="utf-8")

    result = CliRunner().invoke(
        app, ["mask", str(input_path), "--output", str(output_path), "--keep-filenames", "--seed", "1"]
    )
    assert result.exit_code == 0
    assert output_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_cli.py::test_mask_accepts_keep_filenames_flag -v`
Expected: FAIL — Typer reports "No such option: --keep-filenames" (non-zero exit).

- [ ] **Step 3: Write minimal implementation**

In `pipeline.py`, add to `PreprocessConfig` (after `omit_originals`):

```python
    omit_originals: bool = True
    mask_filenames: bool = True
    seed: int | None = None
```

In `cli.py` `mask`, add a parameter (after `omit_originals`):

```python
    mask_filenames: bool = typer.Option(
        True,
        "--mask-filenames/--keep-filenames",
        help="Mask PII in output file/folder names (folder input only). On by default.",
    ),
```

And pass it into the config:

```python
        omit_originals=omit_originals,
        mask_filenames=mask_filenames,
        seed=seed,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/local_data_masker/pipeline.py src/local_data_masker/cli.py tests/test_cli.py
git commit -m "feat: add --mask-filenames/--keep-filenames flag (default on)"
```

---

### Task 6: Pipeline wiring — share EntityMasker, mask output paths, record path mapping

**Files:**
- Modify: `src/local_data_masker/pipeline.py` (`preprocess`, `_process_file`, `_resolve_output_path`)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `mask_relative_path(...)` (Task 4), `EntityMasker` (Task 2), `mask_dataframe(..., entity_masker=...)` (Task 3), `PreprocessConfig.mask_filenames` (Task 5).
- Produces: folder-mode output files written under masked relative paths; original→masked relative path stored in `MappingStore` under category `"path"` when `consistent`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
def test_folder_masking_renames_pii_output_paths(tmp_path: Path) -> None:
    input_root = tmp_path / "in"
    person_dir = input_root / "Abaira_Amina_14_12_1990"
    person_dir.mkdir(parents=True)
    pd.DataFrame({"name": ["Amina Abaira"]}).to_csv(person_dir / "record.csv", index=False)

    profile_path = tmp_path / "p.yaml"
    profile_path.write_text(
        'filename_patterns:\n  - "(?P<name_last>[^_]+)_(?P<name_first>[^_]+)_(?P<dob>\\\\d{2}_\\\\d{2}_\\\\d{4})"\n',
        encoding="utf-8",
    )

    output_root = tmp_path / "out"
    results = preprocess(
        PreprocessConfig(
            input_path=input_root,
            output_path=output_root,
            profile_path=profile_path,
            mask_filenames=True,
            seed=1,
        )
    )

    masked_file = Path(results[0].masked_file)
    assert masked_file.exists()
    assert "Abaira_Amina_14_12_1990" not in str(masked_file)
    assert masked_file.name == "record.csv"


def test_keep_filenames_preserves_folder_structure(tmp_path: Path) -> None:
    input_root = tmp_path / "in"
    person_dir = input_root / "Abaira_Amina_14_12_1990"
    person_dir.mkdir(parents=True)
    pd.DataFrame({"name": ["Amina Abaira"]}).to_csv(person_dir / "record.csv", index=False)

    results = preprocess(
        PreprocessConfig(
            input_path=input_root,
            output_path=tmp_path / "out",
            mask_filenames=False,
            seed=1,
        )
    )
    assert "Abaira_Amina_14_12_1990" in str(results[0].masked_file)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_pipeline.py::test_folder_masking_renames_pii_output_paths -v`
Expected: FAIL — masked path still contains `Abaira_Amina_14_12_1990`.

- [ ] **Step 3: Write minimal implementation**

In `pipeline.py`, add imports:

```python
import itertools

from local_data_masker.maskers.entity_masker import EntityMasker
from local_data_masker.maskers.faker_provider import FakePerson
from local_data_masker.maskers.path_masker import mask_relative_path
```

In `preprocess`, create per-run path state before the file loop and pass it to `_process_file`:

```python
    faker_provider = FakerProvider(seed=config.seed)
    results: list[PreprocessResult] = []
    used_paths: set[str] = set()
    path_counter = itertools.count(1)

    for file_path in files:
        result = _process_file(
            file_path=file_path,
            config=config,
            profile=masking_profile,
            faker_provider=faker_provider,
            mapping_store=mapping_store,
            used_paths=used_paths,
            path_counter=path_counter,
        )
```

Change `_process_file` to build a shared `EntityMasker`, capture the primary identity, and pass the path state through. Replace its body's masking loop and output resolution:

```python
def _process_file(
    file_path: Path,
    config: PreprocessConfig,
    profile: MaskingProfile,
    faker_provider: FakerProvider,
    mapping_store: MappingStore,
    used_paths: set[str],
    path_counter,
) -> PreprocessResult:
    sheets = load_table(file_path)
    masked_sheets = {}
    all_replacements = []
    entity_masker = EntityMasker(faker_provider, mapping_store, config.consistent)

    for sheet_name, df in sheets.items():
        classifications = classify_with_profile(df, profile)
        masked_df, replacements = mask_dataframe(
            df,
            classifications,
            sheet_name,
            faker_provider,
            config.consistent,
            mapping_store,
            profile=profile,
            entity_masker=entity_masker,
        )
        masked_sheets[sheet_name] = masked_df
        all_replacements.extend(replacements)

    primary_identity = entity_masker.primary_person()
    out_path = _resolve_output_path(
        config, file_path, profile, primary_identity, faker_provider,
        mapping_store, entity_masker, used_paths, path_counter,
    )

    if not config.dry_run:
        if file_path.suffix.lower() == ".csv":
            export_csv(next(iter(masked_sheets.values())), out_path)
        else:
            export_excel(masked_sheets, out_path)

    masked_for_report = str(out_path) if not config.dry_run else ""
    report = build_report(
        source_file=str(file_path),
        masked_file=masked_for_report,
        replacements=all_replacements,
        omit_originals=config.omit_originals,
    )

    return PreprocessResult(
        source_file=str(file_path),
        masked_file=masked_for_report,
        replacements_count=len(all_replacements),
        report=report,
    )
```

Replace `_resolve_output_path` with a version that masks the relative path in folder mode:

```python
def _resolve_output_path(
    config: PreprocessConfig,
    file_path: Path,
    profile: MaskingProfile,
    primary_identity: FakePerson | None,
    faker_provider: FakerProvider,
    mapping_store: MappingStore,
    entity_masker: EntityMasker,
    used_paths: set[str],
    path_counter,
) -> Path:
    if config.input_path.is_file():
        return config.output_path

    relative = file_path.relative_to(config.input_path)
    if config.mask_filenames:
        masked_relative = mask_relative_path(
            relative, primary_identity, profile, entity_masker, faker_provider,
            mapping_store, config.consistent, used_paths, path_counter,
        )
        if config.consistent:
            mapping_store.set("path", str(relative), str(masked_relative))
        relative = masked_relative

    out_path = config.output_path / relative
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return out_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_pipeline.py -v`
Expected: PASS (new folder tests and existing single-file pipeline tests).

- [ ] **Step 5: Run the full suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add src/local_data_masker/pipeline.py tests/test_pipeline.py
git commit -m "feat: mask PII output paths in folder mode via path_masker"
```

---

### Task 7: Report omits original source path + health profile pattern + docs

**Files:**
- Modify: `src/local_data_masker/exporters/report_exporter.py` (`build_report`)
- Modify: `src/local_data_masker/pipeline.py` (`_process_file` report call)
- Modify: `profiles/health_records.yaml` (add `filename_patterns`)
- Modify: `README.md` (document the flag), `CLAUDE.md` (note path masking)
- Test: `tests/test_profiles.py` (or `tests/test_pipeline.py`) for report behavior

**Interfaces:**
- Consumes: `build_report` (current signature `source_file, masked_file, replacements, omit_originals`).
- Produces: `build_report(source_file, masked_file, replacements, omit_originals, original_source_file=None)` — adds `original_source_file` to the report only when `omit_originals` is False and the value is provided.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_profiles.py` (it already imports `build_report`):

```python
def test_report_includes_original_source_only_when_requested() -> None:
    omitted = build_report("masked/rec.csv", "masked/rec.csv", [], omit_originals=True,
                           original_source_file="Abaira_Amina_14_12_1990/rec.csv")
    assert "original_source_file" not in omitted

    shown = build_report("masked/rec.csv", "masked/rec.csv", [], omit_originals=False,
                         original_source_file="Abaira_Amina_14_12_1990/rec.csv")
    assert shown["original_source_file"] == "Abaira_Amina_14_12_1990/rec.csv"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_profiles.py::test_report_includes_original_source_only_when_requested -v`
Expected: FAIL — `build_report() got an unexpected keyword argument 'original_source_file'`.

- [ ] **Step 3: Write minimal implementation**

In `report_exporter.py`, update `build_report`:

```python
def build_report(
    source_file: str,
    masked_file: str,
    replacements: list[Replacement],
    omit_originals: bool,
    original_source_file: str | None = None,
) -> dict:
    report = {
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
    if not omit_originals and original_source_file is not None:
        report["original_source_file"] = original_source_file
    return report
```

In `pipeline.py` `_process_file`, when folder masking applies, report the masked source and carry the original for `--include-originals`. Replace the report block:

```python
    masked_for_report = str(out_path) if not config.dry_run else ""
    folder_masked = config.mask_filenames and not config.input_path.is_file()
    report = build_report(
        source_file=masked_for_report if folder_masked and masked_for_report else str(file_path),
        masked_file=masked_for_report,
        replacements=all_replacements,
        omit_originals=config.omit_originals,
        original_source_file=str(file_path) if folder_masked else None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_profiles.py tests/test_pipeline.py -v`
Expected: PASS.

- [ ] **Step 5: Add the health profile pattern and docs**

Append to `profiles/health_records.yaml`:

```yaml

# Folder names in occupational-health exports encode Last_First_DD_MM_YYYY.
# Masking renames them coherently with the masked patient identity.
filename_patterns:
  - "(?P<name_last>[^_/]+)_(?P<name_first>[^_/]+)_(?P<dob>\\d{2}_\\d{2}_\\d{4})"
```

In `README.md`, under masking modes / privacy principles, add a short note:

```markdown
### Filename masking

When masking a folder, PII in file and folder names (e.g. `Abaira_Amina_14_12_1990`)
is masked coherently with the identity inside each file. On by default; use
`--keep-filenames` to preserve original names. Configure name structure with
`filename_patterns` in the profile.
```

In `CLAUDE.md`, add one line to the coherent-entities or architecture section:

```markdown
- `maskers/path_masker.py` masks PII in output paths (folder mode), driven by the profile's `filename_patterns`; names are filled content-first from the file's primary fake identity. Toggle with `PreprocessConfig.mask_filenames` / `--keep-filenames`.
```

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (all tests).

- [ ] **Step 7: Commit**

```bash
git add src/local_data_masker/exporters/report_exporter.py src/local_data_masker/pipeline.py profiles/health_records.yaml README.md CLAUDE.md tests/test_profiles.py
git commit -m "feat: omit original source path in reports; ship health filename pattern; docs"
```

---

## Verification (after all tasks)

- [ ] `.venv\Scripts\python.exe -m pytest -q` — all green.
- [ ] Manual smoke on real data (scratchpad, not the repo): run `mask` over a few `Export/` folders with `profiles/health_records.yaml`, `--consistent`, `--seed 42`, and confirm output folder names no longer contain patient names/DOBs and match the masked content identity.
