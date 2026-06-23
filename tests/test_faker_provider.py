from local_data_masker.detectors.regex_detector import (
    CATEGORY_DATE,
    CATEGORY_EMAIL,
    CATEGORY_ID,
    CATEGORY_NAME,
    CATEGORY_PHONE,
)
from local_data_masker.maskers.faker_provider import FakerProvider


def test_generate_email_preserves_shape():
    provider = FakerProvider(seed=42)
    fake = provider.generate(CATEGORY_EMAIL, "ben.miller@example.com")
    assert "@" in fake


def test_generate_id_preserves_digit_count():
    provider = FakerProvider(seed=42)
    fake = provider.generate(CATEGORY_ID, "481927")
    digits = "".join(c for c in fake if c.isdigit())
    assert len(digits) == 6


def test_generate_date_preserves_format():
    provider = FakerProvider(seed=42)
    fake = provider.generate(CATEGORY_DATE, "1975/02/21")
    assert len(fake.split("/")) == 3
    year, month, day = fake.split("/")
    assert len(year) == 4


def test_generate_name_returns_nonempty_string():
    provider = FakerProvider(seed=42)
    fake = provider.generate(CATEGORY_NAME, "Ben Miller")
    assert isinstance(fake, str) and fake.strip()


def test_generate_phone_returns_nonempty_string():
    provider = FakerProvider(seed=42)
    fake = provider.generate(CATEGORY_PHONE, "+1 555 123 4567")
    assert isinstance(fake, str) and fake.strip()


def test_unknown_category_raises():
    provider = FakerProvider(seed=42)
    try:
        provider.generate("unknown_category", "value")
        assert False, "expected ValueError"
    except ValueError:
        pass
