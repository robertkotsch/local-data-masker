"""Generate semantic replacements from custom masking profiles."""

from __future__ import annotations

from local_data_masker.detectors.custom_rules import MaskingProfile
from local_data_masker.maskers.faker_provider import FakerProvider


def generate_semantic_replacement(
    category: str,
    original: str,
    profile: MaskingProfile,
    faker_provider: FakerProvider,
) -> str:
    """Generate a replacement for a semantic category.

    Profile-defined replacement pools take precedence. If a profile does not
    provide candidates for the category, the FakerProvider fallback generators
    are used.
    """
    candidates = profile.replacements_for_category(category)
    if candidates:
        return faker_provider.choice(candidates)
    return faker_provider.generate(category, original)
