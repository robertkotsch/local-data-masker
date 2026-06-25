"""Create coherent fake person entities for row-level masking.

The goal is to keep related fields aligned. For example, a row containing
``Ben Miller`` and ``ben.miller@example.com`` should become something like
``John Winter`` and ``john.winter@example.test`` rather than two unrelated fake
values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from local_data_masker.detectors.regex_detector import (
    CATEGORY_EMAIL,
    CATEGORY_ID,
    CATEGORY_NAME,
    ColumnClassification,
    is_third_party_person_column,
)
from local_data_masker.maskers.faker_provider import FakePerson, FakerProvider
from local_data_masker.maskers.mapping_store import MappingStore

ENTITY_NAME_CATEGORY = "entity.name"
ENTITY_EMAIL_CATEGORY = "entity.email"
ENTITY_ID_CATEGORY = "entity.id"


@dataclass(frozen=True)
class EntityContext:
    """Fake values for one detected real-world person/entity."""

    key: str
    person: FakePerson

    def replacement_for(self, category: str) -> str | None:
        if category == CATEGORY_NAME:
            return self.person.full_name
        if category == CATEGORY_EMAIL:
            return self.person.email
        return None


class EntityMasker:
    """Generate and cache coherent fake person entities.

    The cache is used even when persistent consistent masking is disabled, so a
    repeated person in one run still receives the same fake identity. When
    ``consistent`` is enabled, the generated name and email are also stored in the
    supplied mapping store so they can be reused across runs.
    """

    def __init__(self, faker_provider: FakerProvider, mapping_store: MappingStore, consistent: bool) -> None:
        self._faker_provider = faker_provider
        self._mapping_store = mapping_store
        self._consistent = consistent
        self._cache: dict[str, EntityContext] = {}
        self._id_cache: dict[str, str] = {}

    def context_for_row(
        self,
        row: pd.Series,
        classifications: dict[str, ColumnClassification],
    ) -> EntityContext | None:
        """Return a coherent fake entity for a row, if the row has identity data."""
        key = _identity_key(row, classifications)
        if key is None:
            return None

        cached = self._cache.get(key)
        if cached is not None:
            return cached

        person = self._load_or_create_person(key)
        context = EntityContext(key=key, person=person)
        self._cache[key] = context
        return context

    def id_for(self, context: EntityContext, original_id: str) -> str:
        """Return a coherent fake ID for an entity, generated once per identity.

        A person's ID belongs to that person, so a repeated identity reuses one
        fake ID within the run (and across runs when consistent masking is on),
        mirroring how the entity's name and email already cohere. The fake ID is
        derived from ``original_id`` so its format (prefix, digit count) is kept.
        """
        cached = self._id_cache.get(context.key)
        if cached is not None:
            return cached

        if self._consistent:
            stored = self._mapping_store.get(ENTITY_ID_CATEGORY, context.key)
            if stored:
                self._id_cache[context.key] = stored
                return stored

        fake_id = self._faker_provider.generate(CATEGORY_ID, original_id)
        self._id_cache[context.key] = fake_id
        if self._consistent:
            self._mapping_store.set(ENTITY_ID_CATEGORY, context.key, fake_id)
        return fake_id

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

    def _load_or_create_person(self, key: str) -> FakePerson:
        if self._consistent:
            full_name = self._mapping_store.get(ENTITY_NAME_CATEGORY, key)
            email = self._mapping_store.get(ENTITY_EMAIL_CATEGORY, key)
            if full_name and email:
                return FakePerson.from_full_name_and_email(full_name, email)

        person = self._faker_provider.generate_person()

        if self._consistent:
            self._mapping_store.set(ENTITY_NAME_CATEGORY, key, person.full_name)
            self._mapping_store.set(ENTITY_EMAIL_CATEGORY, key, person.email)

        return person


def _identity_key(row: pd.Series, classifications: dict[str, ColumnClassification]) -> str | None:
    """Choose the most stable available identity key for a tabular row.

    Priority:
    1. email address
    2. person name
    3. ID-style value

    Email is preferred because names may be ambiguous. IDs are used only as a
    fallback because many tables contain process IDs or course IDs that are not
    person identities.
    """
    for category in (CATEGORY_EMAIL, CATEGORY_NAME, CATEGORY_ID):
        for column, classification in classifications.items():
            if classification.category != category or column not in row:
                continue
            if is_third_party_person_column(column):
                continue
            value = _normalize_value(row[column])
            if value:
                return f"{category}:{value}"
    return None


def _normalize_value(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"", "-", "--", "n/a", "na", "none", "null", "nan"}:
        return ""
    return " ".join(text.split())
