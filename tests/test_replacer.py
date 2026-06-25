import pandas as pd

from local_data_masker.detectors.regex_detector import classify_dataframe
from local_data_masker.maskers.faker_provider import FakerProvider
from local_data_masker.maskers.mapping_store import MappingStore
from local_data_masker.maskers.replacer import mask_dataframe


def test_consistent_masking_reuses_same_fake_value():
    df = pd.DataFrame({"name": ["Ben Miller", "Ben Miller", "Other Person"]})
    classifications = classify_dataframe(df)
    store = MappingStore()
    masked_df, replacements = mask_dataframe(
        df, classifications, "Sheet1", FakerProvider(seed=1), consistent=True, mapping_store=store
    )
    assert masked_df["name"][0] == masked_df["name"][1]
    assert masked_df["name"][0] != masked_df["name"][2]


def test_one_off_masking_gives_distinct_people_distinct_fakes():
    df = pd.DataFrame({"name": [f"First{i} Last{i}" for i in range(20)]})
    classifications = classify_dataframe(df)
    store = MappingStore()
    masked_df, _ = mask_dataframe(
        df, classifications, "Sheet1", FakerProvider(seed=1), consistent=False, mapping_store=store
    )
    # Distinct people must not collapse into a single fake identity.
    assert len(set(masked_df["name"])) > 1


def test_one_off_masking_coheres_repeated_identities_within_a_run():
    df = pd.DataFrame({"name": ["Ben Miller"] * 20})
    classifications = classify_dataframe(df)
    store = MappingStore()
    masked_df, _ = mask_dataframe(
        df, classifications, "Sheet1", FakerProvider(seed=1), consistent=False, mapping_store=store
    )
    # The same person repeated in one run reuses one coherent fake identity.
    assert len(set(masked_df["name"])) == 1


def test_unclassified_columns_are_left_untouched():
    df = pd.DataFrame({"course_title": ["Money Laundering"]})
    classifications = classify_dataframe(df)
    store = MappingStore()
    masked_df, replacements = mask_dataframe(
        df, classifications, "Sheet1", FakerProvider(seed=1), consistent=False, mapping_store=store
    )
    assert masked_df["course_title"][0] == "Money Laundering"
    assert replacements == []


def test_address_columns_are_masked():
    df = pd.DataFrame({"address": ["Scheffelstr.14, 09120 Chemnitz"]})
    classifications = classify_dataframe(df)
    store = MappingStore()
    masked_df, replacements = mask_dataframe(
        df, classifications, "Sheet1", FakerProvider(seed=1), consistent=False, mapping_store=store
    )
    assert masked_df["address"][0] != "Scheffelstr.14, 09120 Chemnitz"
    assert masked_df["address"][0].strip()
    assert replacements[0].category == "address"


def test_examiner_is_not_masked_with_the_patient_identity():
    df = pd.DataFrame({"name": ["Amina Abaira"], "examiner": ["Babette Rother"]})
    classifications = classify_dataframe(df)
    store = MappingStore()
    masked_df, _ = mask_dataframe(
        df, classifications, "Sheet1", FakerProvider(seed=1), consistent=False, mapping_store=store
    )
    assert masked_df["name"][0] != "Amina Abaira"
    assert masked_df["examiner"][0] != "Babette Rother"
    # A third-party person (the examiner) must not collapse into the patient's fake identity.
    assert masked_df["name"][0] != masked_df["examiner"][0]


def test_replacements_record_original_and_masked_values():
    df = pd.DataFrame({"email": ["ben.miller@example.com"]})
    classifications = classify_dataframe(df)
    store = MappingStore()
    _, replacements = mask_dataframe(
        df, classifications, "Sheet1", FakerProvider(seed=1), consistent=False, mapping_store=store
    )
    assert len(replacements) == 1
    assert replacements[0].original == "ben.miller@example.com"
    assert replacements[0].category == "email"
