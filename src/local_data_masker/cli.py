"""Command-line interface for local-data-masker."""

from __future__ import annotations

from pathlib import Path

import typer

from local_data_masker.pipeline import (
    PreprocessConfig,
    PreprocessError,
    PreprocessResult,
    preprocess,
)

app = typer.Typer(help="Local-first data masking tool.")


def _echo_progress(result: PreprocessResult, dry_run: bool) -> None:
    suffix = " (dry run)" if dry_run else " masked"
    typer.echo(f"{result.source_file}: {result.replacements_count} value(s) detected{suffix}")


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
    if consistent and mapping_file is not None:
        typer.echo(
            "Warning: mapping files contain sensitive original values. Do not commit or share them.",
            err=True,
        )

    config = PreprocessConfig(
        input_path=input_path,
        output_path=output,
        report_path=report,
        profile_path=profile,
        mapping_path=mapping_file,
        consistent=consistent,
        dry_run=dry_run,
        omit_originals=omit_originals,
        seed=seed,
    )

    try:
        preprocess(config, progress_callback=lambda result: _echo_progress(result, dry_run))
    except PreprocessError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if report is not None:
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
    config = PreprocessConfig(
        input_path=input_path,
        output_path=input_path,
        report_path=report,
        profile_path=profile,
        dry_run=True,
        omit_originals=omit_originals,
    )

    try:
        preprocess(config, progress_callback=lambda result: _echo_progress(result, dry_run=True))
    except PreprocessError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Audit report written to {report}")


if __name__ == "__main__":
    app()
