"""Command-line interface for local-data-masker."""

from __future__ import annotations

from pathlib import Path

import typer

from local_data_masker.detectors.custom_rules import MaskingProfile
from local_data_masker.detectors.regex_detector import ColumnClassification, classify_dataframe
from local_data_masker.exporters.report_exporter import build_report, write_report
from local_data_masker.exporters.table_exporter import export_csv, export_excel
from local_data_masker.extractors.table_extractor import is_supported, load_table
from local_data_masker.maskers.faker_provider import FakerProvider
from local_data_masker.maskers.mapping_store import MappingStore
from local_data_masker.maskers.replacer import mask_dataframe

app = typer.Typer(help="Local-first data masking tool.")


def _iter_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(p for p in input_path.rglob("*") if p.is_file() and is_supported(p))


def _load_profile(profile_path: Path | None) -> MaskingProfile:
    if profile_path is None:
        return MaskingProfile.empty()
    if not profile_path.exists():
        typer.echo(f"Masking profile not found: {profile_path}", err=True)
        raise typer.Exit(code=1)
    return MaskingProfile.from_file(profile_path)


def _classify_with_profile(df, profile: MaskingProfile) -> list[ColumnClassification]:
    base_classifications = {classification.column: classification for classification in classify_dataframe(df)}

    for column in df.columns:
        column_name = str(column)
        profile_classification = profile.classify_column(column_name)
        if profile_classification is None:
            continue

        existing = base_classifications.get(column_name)
        if existing is None or existing.category is None or profile_classification.confidence >= existing.confidence:
            base_classifications[column_name] = profile_classification

    return list(base_classifications.values())


@app.command()
def mask(
    input_path: Path = typer.Argument(..., exists=True, help="A file or folder of CSV/Excel files."),
    output: Path = typer.Option(..., "--output", "-o", help="Output file (single input) or folder (multiple inputs)."),
    consistent: bool = typer.Option(False, "--consistent", help="Reuse the same fake value for repeated originals."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Detect and report findings without writing masked files."),
    report: Path | None = typer.Option(None, "--report", help="Path to write the JSON audit report."),
    mapping_file: Path | None = typer.Option(None, "--mapping", help="Persist/reuse the consistent-masking mapping at this path."),
    profile: Path | None = typer.Option(None, "--profile", help="YAML masking profile with custom replacements and semantic categories."),
    omit_originals: bool = typer.Option(
        True,
        "--omit-originals/--include-originals",
        help="Exclude/include original values in reports. Defaults to omitting originals for safety.",
    ),
    seed: int | None = typer.Option(None, "--seed", help="Random seed for reproducible fake values."),
) -> None:
    """Mask sensitive values in CSV/Excel files."""
    files = _iter_input_files(input_path)
    if not files:
        typer.echo("No supported CSV/Excel files found.", err=True)
        raise typer.Exit(code=1)

    masking_profile = _load_profile(profile)

    if not dry_run:
        if input_path.is_file():
            output.parent.mkdir(parents=True, exist_ok=True)
        else:
            output.mkdir(parents=True, exist_ok=True)

    mapping_store = MappingStore()
    if consistent and mapping_file is not None:
        typer.echo(
            "Warning: mapping files contain sensitive original values. Do not commit or share them.",
            err=True,
        )
        mapping_store.load(mapping_file)

    faker_provider = FakerProvider(seed=seed)
    reports: list[dict] = []

    for file_path in files:
        sheets = load_table(file_path)
        masked_sheets = {}
        all_replacements = []

        for sheet_name, df in sheets.items():
            classifications = _classify_with_profile(df, masking_profile)
            masked_df, replacements = mask_dataframe(
                df,
                classifications,
                sheet_name,
                faker_provider,
                consistent,
                mapping_store,
                profile=masking_profile,
            )
            masked_sheets[sheet_name] = masked_df
            all_replacements.extend(replacements)

        if input_path.is_file():
            out_path = output
        else:
            out_path = output / file_path.relative_to(input_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)

        if not dry_run:
            if file_path.suffix.lower() == ".csv":
                export_csv(next(iter(masked_sheets.values())), out_path)
            else:
                export_excel(masked_sheets, out_path)

        reports.append(
            build_report(
                source_file=str(file_path),
                masked_file=str(out_path) if not dry_run else "",
                replacements=all_replacements,
                omit_originals=omit_originals,
            )
        )

        typer.echo(f"{file_path}: {len(all_replacements)} value(s) detected" + (" (dry run)" if dry_run else " masked"))

    if consistent and mapping_file is not None:
        mapping_file.parent.mkdir(parents=True, exist_ok=True)
        mapping_store.save(mapping_file)

    if report is not None:
        write_report(reports, report)
        typer.echo(f"Audit report written to {report}")


@app.command()
def scan(
    input_path: Path = typer.Argument(..., exists=True, help="A file or folder of CSV/Excel files."),
    report: Path = typer.Option(..., "--report", help="Path to write the JSON findings report."),
    profile: Path | None = typer.Option(None, "--profile", help="YAML masking profile with custom replacements and semantic categories."),
    omit_originals: bool = typer.Option(
        True,
        "--omit-originals/--include-originals",
        help="Exclude/include original values in reports. Defaults to omitting originals for safety.",
    ),
) -> None:
    """Detect sensitive values without modifying any files."""
    mask(
        input_path=input_path,
        output=input_path,
        consistent=False,
        dry_run=True,
        report=report,
        mapping_file=None,
        profile=profile,
        omit_originals=omit_originals,
        seed=None,
    )


if __name__ == "__main__":
    app()
