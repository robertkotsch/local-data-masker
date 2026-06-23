"""Public package API for local-data-masker."""

from local_data_masker.pipeline import PreprocessConfig, PreprocessResult, preprocess

__version__ = "0.1.0"

__all__ = [
    "PreprocessConfig",
    "PreprocessResult",
    "preprocess",
]
