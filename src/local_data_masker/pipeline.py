"""Importable preprocessing pipeline for local-data-masker.

This module is the integration boundary for other projects. The CLI should stay
thin and delegate to this module, while downstream applications can import and
run the masking step before sending masked data into analytics, RAG, cloud AI,
or other processing workflows.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

import pandas as pd

from local_data_masker.detectors.custom_rules import MaskingProfile
from local_data_masker.detectors.regex_detector import ColumnClassification, classify_dataframe
from local_data_masker.exporters.report_exporter import build_report, write_report
from local_data_masker.exporters.table_exporter import export_csv, export_excel
from local_data_masker.extractors.table_extractor import is_supported, load_table
from local_data_masker.maskers.entity_masker import EntityMasker
from local_data_masker.maskers.faker_provider import FakePerson, FakerProvider
from local_data_masker.maskers.mapping_store import MappingStore
from local_data_masker.maskers.path_masker import mask_relative_path
from local_data_masker.maskers.replacer import mask_dataframe

ProgressCallback = Callable[["PreprocessResult"], None]


@dataclass(frozen=True)
class PreprocessResult:
    """Result for one processed source file."""

    source_file: str
    masked_file: str
    replacements_count: int
    report: dict


@dataclass(frozen=True)
class PreprocessConfig:
    """Configuration for the reusable masking pre-processing step."""

    input_path: Path
    output_path: Path
    report_path: Path | None = None
    profile_path: Path | None = None
    mapping_path: Path | None = None
    consistent: bool = False
    dry_run: bool = False
    omit_originals: bool = True
    mask_filenames: bool = True
    seed: int | None = None


class PreprocessError(RuntimeError):
    """Raised when the pre-processing pipeline cannot complete."""


class UnsupportedInputError(PreprocessError):
    """Raised when no supported input files are found."""


class ProfileNotFoundError(PreprocessError):
    """Raised when a requested profile file does not exist."""


class MappingFileWarning(UserWarning):
    """Warning category for sensitive mapping-file handling."""


def preprocess(
    config: PreprocessConfig,
    progress_callback: ProgressCallback | None = None,
) -> list[PreprocessResult]:
    """Run the masking pre-processing step.

    This is the public API intended for other projects.

    Example:

    ```python
    from pathlib import Path
    from local_data_masker.pipeline import PreprocessConfig, preprocess

    results = preprocess(
        PreprocessConfig(
            input_path=Path("data/raw"),
            output_path=Path("data/masked"),
            profile_path=Path("profiles/default.yaml"),
            report_path=Path("data/reports/masking-report.json"),
            consistent=True,
            mapping_path=Path("data/mappings/local.mapping.json"),
        )
    )
    ```
    """
    files = _iter_input_files(config.input_path)
    if not files:
        raise UnsupportedInputError(f"No supported CSV/Excel files found: {config.input_path}")

    masking_profile = load_profile(config.profile_path)
    _prepare_output_location(config)

    mapping_store = MappingStore()
    if config.consistent and config.mapping_path is not None:
        mapping_store.load(config.mapping_path)

    faker_provider = FakerProvider(seed=config.seed)
    results: list[PreprocessResult] = []
    used_paths: set[str] = set()
    path_counter = itertools.count(1)

    for file_path in files:
        result = _process_file(
            file_path=file_path,
            config=config,
            profile=masking_profile,
            faker_provider=faker_provider,
            mapping_store=mapping_store,
            used_paths=used_paths,
            path_counter=path_counter,
        )
        results.append(result)
        if progress_callback is not None:
            progress_callback(result)

    if config.consistent and config.mapping_path is not None:
        config.mapping_path.parent.mkdir(parents=True, exist_ok=True)
        mapping_store.save(config.mapping_path)

    if config.report_path is not None:
        write_report([result.report for result in results], config.report_path)

    return results


def load_profile(profile_path: Path | None) -> MaskingProfile:
    """Load a masking profile, or return an empty profile when none is supplied."""
    if profile_path is None:
        return MaskingProfile.empty()
    if not profile_path.exists():
        raise ProfileNotFoundError(f"Masking profile not found: {profile_path}")
    return MaskingProfile.from_file(profile_path)


def classify_with_profile(df: pd.DataFrame, profile: MaskingProfile) -> list[ColumnClassification]:
    """Combine built-in column classification with profile-based classifications."""
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


def _iter_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(p for p in input_path.rglob("*") if p.is_file() and is_supported(p))


def _prepare_output_location(config: PreprocessConfig) -> None:
    if config.dry_run:
        return
    if config.input_path.is_file():
        config.output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        config.output_path.mkdir(parents=True, exist_ok=True)


def _process_file(
    file_path: Path,
    config: PreprocessConfig,
    profile: MaskingProfile,
    faker_provider: FakerProvider,
    mapping_store: MappingStore,
    used_paths: set[str],
    path_counter: Iterator[int],
) -> PreprocessResult:
    sheets = load_table(file_path)
    masked_sheets = {}
    all_replacements = []
    entity_masker = EntityMasker(faker_provider, mapping_store, config.consistent)

    for sheet_name, df in sheets.items():
        classifications = classify_with_profile(df, profile)
        masked_df, replacements = mask_dataframe(
            df,
            classifications,
            sheet_name,
            faker_provider,
            config.consistent,
            mapping_store,
            profile=profile,
            entity_masker=entity_masker,
        )
        masked_sheets[sheet_name] = masked_df
        all_replacements.extend(replacements)

    primary_identity = entity_masker.primary_person()
    out_path = _resolve_output_path(
        config, file_path, profile, primary_identity, faker_provider,
        mapping_store, entity_masker, used_paths, path_counter,
    )

    if not config.dry_run:
        if file_path.suffix.lower() == ".csv":
            export_csv(next(iter(masked_sheets.values())), out_path)
        else:
            export_excel(masked_sheets, out_path)

    masked_for_report = str(out_path) if not config.dry_run else ""
    folder_masked = config.mask_filenames and not config.input_path.is_file()
    report = build_report(
        source_file=str(out_path) if folder_masked else str(file_path),
        masked_file=masked_for_report,
        replacements=all_replacements,
        omit_originals=config.omit_originals,
        original_source_file=str(file_path) if folder_masked else None,
    )

    return PreprocessResult(
        source_file=str(file_path),
        masked_file=masked_for_report,
        replacements_count=len(all_replacements),
        report=report,
    )


def _resolve_output_path(
    config: PreprocessConfig,
    file_path: Path,
    profile: MaskingProfile,
    primary_identity: FakePerson | None,
    faker_provider: FakerProvider,
    mapping_store: MappingStore,
    entity_masker: EntityMasker,
    used_paths: set[str],
    path_counter: Iterator[int],
) -> Path:
    if config.input_path.is_file():
        return config.output_path

    relative = file_path.relative_to(config.input_path)
    if config.mask_filenames:
        masked_relative = mask_relative_path(
            relative, primary_identity, profile, entity_masker, faker_provider,
            mapping_store, config.consistent, used_paths, path_counter,
        )
        if config.consistent:
            mapping_store.set("path", str(relative), str(masked_relative))
        relative = masked_relative

    out_path = config.output_path / relative
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return out_path
