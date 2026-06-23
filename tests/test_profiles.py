from pathlib import Path

import pandas as pd

from local_data_masker.detectors.custom_rules import MaskingProfile
from local_data_masker.detectors.regex_detector import classify_dataframe
from local_data_masker.exporters.report_exporter import build_report
from local_data_masker.maskers.faker_provider import FakerProvider
from local_data_masker.maskers.mapping_store import MappingStore
from local_data_masker.maskers.replacer import mask_dataframe


def test_custom_replacement_applies_inside_unclassified_column() -> None:
    profile = MaskingProfile(custom_replacements={"Money Laundering": "Healthy Nutrition"})
    df = pd.DataFrame({"notes": ["Course: Money Laundering", "No sensitive topic"]})

    classifications = classify_dataframe(df)
    masked_df, replacements = mask_dataframe(
        df,
        classifications,
        "Sheet1",
        FakerProvider(seed=1),
        consistent=False,
        mapping_store=MappingStore(),
        profile=profile,
    )

    assert masked_df.loc[0, "notes"] == "Course: Healthy Nutrition"
    assert masked_df.loc[1, "notes"] == "No sensitive topic"
    assert len(replacements) == 1
    assert replacements[0].category == "custom_replacement"


def test_profile_classifies_and_masks_course_title_column(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        """
column_categories:
  course_title:
    columns:
      - course_title
    replacements:
      - Healthy Nutrition
""".strip(),
        encoding="utf-8",
    )
    profile = MaskingProfile.from_file(profile_path)
    classification = profile.classify_column("course_title")

    assert classification is not None
    assert classification.category == "course_title"

    df = pd.DataFrame({"course_title": ["Money Laundering"]})
    masked_df, replacements = mask_dataframe(
        df,
        [classification],
        "Sheet1",
        FakerProvider(seed=1),
        consistent=False,
        mapping_store=MappingStore(),
        profile=profile,
    )

    assert masked_df.loc[0, "course_title"] == "Healthy Nutrition"
    assert replacements[0].category == "course_title"


def test_report_omits_original_values_by_default() -> None:
    profile = MaskingProfile(custom_replacements={"Money Laundering": "Healthy Nutrition"})
    df = pd.DataFrame({"notes": ["Money Laundering"]})
    _, replacements = mask_dataframe(
        df,
        classify_dataframe(df),
        "Sheet1",
        FakerProvider(seed=1),
        consistent=False,
        mapping_store=MappingStore(),
        profile=profile,
    )

    report = build_report("input.csv", "masked.csv", replacements, omit_originals=True)

    assert "original" not in report["replacements"][0]
    assert report["replacements"][0]["masked"] == "Healthy Nutrition"
