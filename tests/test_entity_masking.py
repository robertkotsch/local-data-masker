import pandas as pd

from local_data_masker.detectors.regex_detector import classify_dataframe
from local_data_masker.maskers.faker_provider import FakerProvider
from local_data_masker.maskers.mapping_store import MappingStore
from local_data_masker.maskers.replacer import mask_dataframe


def _expected_email_from_name(full_name: str) -> str:
    first_name, last_name = full_name.split()[0], full_name.split()[-1]
    return f"{first_name.lower()}.{last_name.lower()}@example.test"


def test_name_and_email_are_masked_as_one_coherent_entity() -> None:
    df = pd.DataFrame(
        {
            "name": ["Ben Miller"],
            "email": ["ben.miller@example.com"],
        }
    )

    masked_df, replacements = mask_dataframe(
        df,
        classify_dataframe(df),
        "Sheet1",
        FakerProvider(seed=7),
        consistent=False,
        mapping_store=MappingStore(),
    )

    fake_name = masked_df.loc[0, "name"]
    fake_email = masked_df.loc[0, "email"]

    assert fake_name != "Ben Miller"
    assert fake_email != "ben.miller@example.com"
    assert fake_email == _expected_email_from_name(fake_name)
    assert {replacement.category for replacement in replacements} == {"name", "email"}


def test_repeated_email_reuses_the_same_fake_entity_within_one_run() -> None:
    df = pd.DataFrame(
        {
            "name": ["Ben Miller", "B. Miller"],
            "email": ["ben.miller@example.com", "ben.miller@example.com"],
        }
    )

    masked_df, _ = mask_dataframe(
        df,
        classify_dataframe(df),
        "Sheet1",
        FakerProvider(seed=11),
        consistent=False,
        mapping_store=MappingStore(),
    )

    assert masked_df.loc[0, "name"] == masked_df.loc[1, "name"]
    assert masked_df.loc[0, "email"] == masked_df.loc[1, "email"]


def test_consistent_entity_mapping_reuses_fake_identity_across_calls() -> None:
    df = pd.DataFrame(
        {
            "name": ["Ben Miller"],
            "email": ["ben.miller@example.com"],
        }
    )
    mapping_store = MappingStore()

    first_masked_df, _ = mask_dataframe(
        df,
        classify_dataframe(df),
        "Sheet1",
        FakerProvider(seed=21),
        consistent=True,
        mapping_store=mapping_store,
    )
    second_masked_df, _ = mask_dataframe(
        df,
        classify_dataframe(df),
        "Sheet1",
        FakerProvider(seed=99),
        consistent=True,
        mapping_store=mapping_store,
    )

    assert first_masked_df.loc[0, "name"] == second_masked_df.loc[0, "name"]
    assert first_masked_df.loc[0, "email"] == second_masked_df.loc[0, "email"]
