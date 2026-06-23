"""Generate plausible fake values for detected categories."""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence

from faker import Faker

from local_data_masker.detectors.regex_detector import (
    CATEGORY_DATE,
    CATEGORY_DATE_OF_BIRTH,
    CATEGORY_EMAIL,
    CATEGORY_IBAN,
    CATEGORY_ID,
    CATEGORY_NAME,
    CATEGORY_PHONE,
)

DATE_FORMATS = (
    ("%Y/%m/%d", re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")),
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")),
    ("%d/%m/%Y", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
    ("%d-%m-%Y", re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$")),
)

COURSE_TITLES = (
    "Healthy Nutrition",
    "Workplace Safety Basics",
    "Digital Collaboration",
    "Ergonomics at Work",
    "Effective Communication",
    "Data Protection Basics",
)

PROJECT_NAMES = (
    "Project Silverline",
    "Project Northstar",
    "Project Blue Harbor",
    "Project Clearview",
)

DEPARTMENTS = (
    "Learning & Development",
    "People Operations",
    "Digital Services",
    "Customer Enablement",
)

PRODUCT_NAMES = (
    "Demo Portal",
    "Learning Hub",
    "Service Companion",
    "Knowledge Center",
)


@dataclass(frozen=True)
class FakePerson:
    """Coherent fake person values used across related columns."""

    first_name: str
    last_name: str
    full_name: str
    email: str

    @classmethod
    def from_full_name_and_email(cls, full_name: str, email: str) -> "FakePerson":
        parts = full_name.split()
        first_name = parts[0] if parts else "John"
        last_name = parts[-1] if len(parts) > 1 else "Doe"
        return cls(first_name=first_name, last_name=last_name, full_name=full_name, email=email)


class FakerProvider:
    """Wraps Faker to produce category-appropriate fake values."""

    def __init__(self, seed: int | None = None) -> None:
        self._faker = Faker()
        if seed is not None:
            Faker.seed(seed)
            random.seed(seed)

    def generate(self, category: str, original: str) -> str:
        generator = _GENERATORS.get(category)
        if generator is None:
            raise ValueError(f"No fake value generator for category: {category}")
        return generator(self._faker, original)

    def generate_person(self) -> FakePerson:
        """Generate one coherent fake person identity."""
        first_name = self._faker.first_name()
        last_name = self._faker.last_name()
        full_name = f"{first_name} {last_name}"
        email = _email_from_name(first_name, last_name)
        return FakePerson(first_name=first_name, last_name=last_name, full_name=full_name, email=email)

    def choice(self, candidates: Sequence[str]) -> str:
        """Return a reproducible random choice when a seed is configured."""
        if not candidates:
            raise ValueError("Cannot choose from an empty candidate list")
        return random.choice(list(candidates))


def _generate_name(faker: Faker, original: str) -> str:
    first_name = faker.first_name()
    last_name = faker.last_name()
    return f"{first_name} {last_name}"


def _generate_email(faker: Faker, original: str) -> str:
    first = faker.first_name()
    last = faker.last_name()
    return _email_from_name(first, last)


def _email_from_name(first_name: str, last_name: str) -> str:
    first = _slugify(first_name) or "john"
    last = _slugify(last_name) or "doe"
    return f"{first}.{last}@example.test"


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.lower()
    ascii_value = re.sub(r"[^a-z0-9]+", ".", ascii_value)
    return ascii_value.strip(".")


def _generate_phone(faker: Faker, original: str) -> str:
    return faker.phone_number()


def _generate_iban(faker: Faker, original: str) -> str:
    return faker.iban()


def _generate_id(faker: Faker, original: str) -> str:
    digits = re.sub(r"\D", "", original)
    if not digits:
        return str(faker.random_number(digits=6, fix_len=True))
    fake_digits = "".join(str(random.randint(0, 9)) for _ in digits)
    return original.replace(digits, fake_digits, 1) if digits in original else fake_digits


def _parse_date(value: str) -> tuple[date, str] | None:
    for fmt, pattern in DATE_FORMATS:
        if pattern.match(value.strip()):
            try:
                parsed = datetime.strptime(value.strip(), fmt).date()
                return parsed, fmt
            except ValueError:
                continue
    return None


def _safe_date(year: int, month: int, day: int) -> date:
    # Keep the generated day in a safe range so every month is valid.
    return date(year, max(1, min(month, 12)), max(1, min(day, 28)))


def _generate_date(faker: Faker, original: str) -> str:
    parsed = _parse_date(original)
    if parsed is None:
        return faker.date()
    original_date, fmt = parsed
    offset_days = random.randint(-365, 365)
    fake_date = original_date + timedelta(days=offset_days)
    return fake_date.strftime(fmt)


def _generate_date_of_birth(faker: Faker, original: str) -> str:
    parsed = _parse_date(original)
    if parsed is None:
        return faker.date_of_birth(minimum_age=18, maximum_age=75).strftime("%Y-%m-%d")

    original_date, fmt = parsed
    year_shift = random.choice([-3, -2, -1, 1, 2, 3])
    month_shift = random.choice([-2, -1, 1, 2])
    day_shift = random.choice([-3, -2, -1, 1, 2, 3])

    fake_year = original_date.year + year_shift
    fake_month = original_date.month + month_shift
    if fake_month < 1:
        fake_year -= 1
        fake_month += 12
    elif fake_month > 12:
        fake_year += 1
        fake_month -= 12

    fake_day = original_date.day + day_shift
    fake_date = _safe_date(fake_year, fake_month, fake_day)
    return fake_date.strftime(fmt)


def _generate_course_title(faker: Faker, original: str) -> str:
    return random.choice(COURSE_TITLES)


def _generate_company(faker: Faker, original: str) -> str:
    return faker.company()


def _generate_project_name(faker: Faker, original: str) -> str:
    return random.choice(PROJECT_NAMES)


def _generate_department(faker: Faker, original: str) -> str:
    return random.choice(DEPARTMENTS)


def _generate_product_name(faker: Faker, original: str) -> str:
    return random.choice(PRODUCT_NAMES)


_GENERATORS = {
    CATEGORY_NAME: _generate_name,
    CATEGORY_EMAIL: _generate_email,
    CATEGORY_PHONE: _generate_phone,
    CATEGORY_DATE: _generate_date,
    CATEGORY_DATE_OF_BIRTH: _generate_date_of_birth,
    CATEGORY_IBAN: _generate_iban,
    CATEGORY_ID: _generate_id,
    "course_title": _generate_course_title,
    "training_name": _generate_course_title,
    "topic": _generate_course_title,
    "company": _generate_company,
    "organization": _generate_company,
    "organisation": _generate_company,
    "customer": _generate_company,
    "supplier": _generate_company,
    "project_name": _generate_project_name,
    "project": _generate_project_name,
    "department": _generate_department,
    "product_name": _generate_product_name,
    "product": _generate_product_name,
}
