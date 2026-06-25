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
