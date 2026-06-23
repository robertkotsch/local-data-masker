from pathlib import Path

import pandas as pd

from local_data_masker.pipeline import PreprocessConfig, preprocess


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
