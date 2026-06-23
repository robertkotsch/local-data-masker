"""Generate plausible fake values for detected categories."""

from __future__ import annotations

import random
import re
from datetime import date, datetime, timedelta

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


def _generate_name(faker: Faker, original: str) -> str:
    return faker.name()


def _generate_email(faker: Faker, original: str) -> str:
    return faker.email(domain="example.test")


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


def _generate_date(faker: Faker, original: str) -> str:
    parsed = _parse_date(original)
    if parsed is None:
        return faker.date()
    original_date, fmt = parsed
    offset_days = random.randint(-365, 365)
    fake_date = original_date + timedelta(days=offset_days)
    return fake_date.strftime(fmt)


_GENERATORS = {
    CATEGORY_NAME: _generate_name,
    CATEGORY_EMAIL: _generate_email,
    CATEGORY_PHONE: _generate_phone,
    CATEGORY_DATE: _generate_date,
    CATEGORY_DATE_OF_BIRTH: _generate_date,
    CATEGORY_IBAN: _generate_iban,
    CATEGORY_ID: _generate_id,
}
