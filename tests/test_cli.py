import json

from typer.testing import CliRunner

from local_data_masker.cli import app

runner = CliRunner()


def _write_sample_csv(path):
    path.write_text(
        "name,email,date_of_birth,employee_id,course_title\n"
        "Ben Miller,ben.miller@example.com,1975/02/21,481927,Money Laundering\n"
    )


def test_mask_csv_file_writes_output_and_report(tmp_path):
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    report_path = tmp_path / "report.json"
    _write_sample_csv(input_csv)

    result = runner.invoke(
        app,
        [
            "mask",
            str(input_csv),
            "--output",
            str(output_csv),
            "--report",
            str(report_path),
            "--seed",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_csv.exists()

    masked_content = output_csv.read_text()
    assert "Ben Miller" not in masked_content
    assert "Money Laundering" in masked_content  # unclassified column stays intact

    report = json.loads(report_path.read_text())
    assert report[0]["source_file"] == str(input_csv)
    categories = {r["category"] for r in report[0]["replacements"]}
    assert categories == {"name", "email", "date_of_birth", "id"}


def test_dry_run_does_not_write_output_file(tmp_path):
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    report_path = tmp_path / "report.json"
    _write_sample_csv(input_csv)

    result = runner.invoke(
        app,
        ["mask", str(input_csv), "--output", str(output_csv), "--dry-run", "--report", str(report_path)],
    )

    assert result.exit_code == 0, result.output
    assert not output_csv.exists()
    assert report_path.exists()


def test_consistent_masking_with_mapping_file_persists_across_runs(tmp_path):
    input_csv = tmp_path / "input.csv"
    output_csv_1 = tmp_path / "output1.csv"
    output_csv_2 = tmp_path / "output2.csv"
    mapping_file = tmp_path / "mapping.json"
    _write_sample_csv(input_csv)

    for output_csv in (output_csv_1, output_csv_2):
        result = runner.invoke(
            app,
            [
                "mask",
                str(input_csv),
                "--output",
                str(output_csv),
                "--consistent",
                "--mapping",
                str(mapping_file),
            ],
        )
        assert result.exit_code == 0, result.output

    assert output_csv_1.read_text() == output_csv_2.read_text()


def test_mask_accepts_keep_filenames_flag(tmp_path):
    input_path = tmp_path / "raw.csv"
    output_path = tmp_path / "out.csv"
    input_path.write_text("name\nBen Miller\n", encoding="utf-8")

    result = runner.invoke(
        app, ["mask", str(input_path), "--output", str(output_path), "--keep-filenames", "--seed", "1"]
    )
    assert result.exit_code == 0
    assert output_path.exists()
