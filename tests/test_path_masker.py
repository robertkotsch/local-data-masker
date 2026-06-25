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
