from pathlib import Path

import pandas as pd

from local_data_masker.pipeline import PreprocessConfig, preprocess


def test_folder_masking_renames_pii_output_paths(tmp_path: Path) -> None:
    input_root = tmp_path / "in"
    person_dir = input_root / "Abaira_Amina_14_12_1990"
    person_dir.mkdir(parents=True)
    pd.DataFrame({"name": ["Amina Abaira"]}).to_csv(person_dir / "record.csv", index=False)

    profile_path = tmp_path / "p.yaml"
    profile_path.write_text(
        'filename_patterns:\n  - "(?P<name_last>[^_]+)_(?P<name_first>[^_]+)_(?P<dob>\\\\d{2}_\\\\d{2}_\\\\d{4})"\n',
        encoding="utf-8",
    )

    output_root = tmp_path / "out"
    results = preprocess(
        PreprocessConfig(
            input_path=input_root,
            output_path=output_root,
            profile_path=profile_path,
            mask_filenames=True,
            seed=1,
        )
    )

    masked_file = Path(results[0].masked_file)
    assert masked_file.exists()
    assert "Abaira_Amina_14_12_1990" not in str(masked_file)
    assert masked_file.name == "record.csv"


def test_keep_filenames_preserves_folder_structure(tmp_path: Path) -> None:
    input_root = tmp_path / "in"
    person_dir = input_root / "Abaira_Amina_14_12_1990"
    person_dir.mkdir(parents=True)
    pd.DataFrame({"name": ["Amina Abaira"]}).to_csv(person_dir / "record.csv", index=False)

    results = preprocess(
        PreprocessConfig(
            input_path=input_root,
            output_path=tmp_path / "out",
            mask_filenames=False,
            seed=1,
        )
    )
    assert "Abaira_Amina_14_12_1990" in str(results[0].masked_file)


def test_preprocess_pipeline_creates_masked_output_and_report(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.csv"
    output_path = tmp_path / "masked.csv"
    report_path = tmp_path / "report.json"

    pd.DataFrame(
        {
            "name": ["Ben Miller"],
            "email": ["ben.miller@example.com"],
            "course_title": ["Money Laundering"],
        }
    ).to_csv(input_path, index=False)

    results = preprocess(
        PreprocessConfig(
            input_path=input_path,
            output_path=output_path,
            report_path=report_path,
            seed=1,
        )
    )

    assert output_path.exists()
    assert report_path.exists()
    assert len(results) == 1
    assert results[0].source_file == str(input_path)
    assert results[0].masked_file == str(output_path)
    assert results[0].replacements_count >= 2


def test_preprocess_pipeline_can_be_used_as_dry_run(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.csv"
    output_path = tmp_path / "masked.csv"
    report_path = tmp_path / "report.json"

    pd.DataFrame({"email": ["ben.miller@example.com"]}).to_csv(input_path, index=False)

    results = preprocess(
        PreprocessConfig(
            input_path=input_path,
            output_path=output_path,
            report_path=report_path,
            dry_run=True,
            seed=1,
        )
    )

    assert not output_path.exists()
    assert report_path.exists()
    assert results[0].masked_file == ""
    assert results[0].replacements_count == 1


def test_preprocess_pipeline_progress_callback(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.csv"
    output_path = tmp_path / "masked.csv"
    seen = []

    pd.DataFrame({"email": ["ben.miller@example.com"]}).to_csv(input_path, index=False)

    preprocess(
        PreprocessConfig(input_path=input_path, output_path=output_path, seed=1),
        progress_callback=seen.append,
    )

    assert len(seen) == 1
    assert seen[0].source_file == str(input_path)
    assert seen[0].masked_file == str(output_path)
