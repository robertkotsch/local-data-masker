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


def test_one_off_masking_does_not_force_consistency():
    df = pd.DataFrame({"name": ["Ben Miller"] * 20})
    classifications = classify_dataframe(df)
    store = MappingStore()
    masked_df, _ = mask_dataframe(
        df, classifications, "Sheet1", FakerProvider(seed=1), consistent=False, mapping_store=store
    )
    assert len(set(masked_df["name"])) > 1


def test_unclassified_columns_are_left_untouched():
    df = pd.DataFrame({"course_title": ["Money Laundering"]})
    classifications = classify_dataframe(df)
    store = MappingStore()
    masked_df, replacements = mask_dataframe(
        df, classifications, "Sheet1", FakerProvider(seed=1), consistent=False, mapping_store=store
    )
    assert masked_df["course_title"][0] == "Money Laundering"
    assert replacements == []


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
