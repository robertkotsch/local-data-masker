# Filename / Path Masking — Design

**Date:** 2026-06-25
**Status:** Approved, pending implementation plan

## Problem

When masking a folder of files, the tool mirrors the input directory structure
into the output folder (`pipeline._resolve_output_path`). Folder and file names
frequently encode PII — e.g. `Abaira_Amina_14_12_1990/Untersuchungskartei.pdf`
encodes a name and date of birth. Today:

- the masked output is written to a path that still contains the original PII name, and
- the JSON report records the raw `source_file` / `masked_file` paths,

so a fully masked dataset still leaks identities through its filesystem layout and
its audit report, even with `--omit-originals`.

## Goal

The masked filename must belong to the **same identity** as the masked content:
the person named by `Abaira_Amina_14_12_1990` and the "Amina Abaira" inside the
file both map to the same fake identity (e.g. "Danielle Johnson"). Coherence is
achieved by routing filename fields through the **same** `EntityMasker` +
`MappingStore` + `FakerProvider` that mask the content.

## Decisions (from brainstorming)

1. **Masked names share the content identity** (not opaque tokens, not blind
   filename transformation).
2. **Identity resolution order: content-first → filename-parse fallback → opaque
   token.**
3. **On by default**, with `--keep-filenames` to opt out.

## Scope

- **Folder-mode only.** When the input is a single file, the user supplies an
  explicit `--output` path, which is respected verbatim. Masking applies only to
  the *relative path components* the tool derives when mirroring a folder.
- Applies to every path component (directories and the file stem); the file
  **suffix** is preserved (`.csv`, `.pdf`, …).

## Architecture

### New component: `maskers/path_masker.py`

Single responsibility: map a source file's **relative path** to a **masked
relative path**, coherent with content masking.

```
mask_relative_path(
    relative_path: Path,
    primary_identity: FakePerson | None,   # from content masking, may be None
    profile: MaskingProfile,
    entity_masker: EntityMasker,
    faker_provider: FakerProvider,
    mapping_store: MappingStore,
    consistent: bool,
    used_paths: set[str],                  # for collision disambiguation
    fallback_counter: Iterator[int],       # for opaque tokens, run-stable
) -> Path
```

**Masking is pattern-driven per component.** Each relative-path component is
tested against the profile's `filename_patterns`; the first match wins. A
component that matches **no** pattern is treated as a non-PII structural name and
left unchanged (e.g. the constant `Untersuchungskartei.pdf` leaf). Only a matched
component is rewritten, by filling its captured groups:

1. **name groups** (`name`, `name_first`, `name_last`) — filled **content-first**:
   if the file's `primary_identity` is set, use `person.first_name` /
   `person.last_name` / full name from it; otherwise (no content identity) mask
   the *captured* filename name through the shared `EntityMasker` (filename
   fallback). Content-first matters because the content identity may be keyed by
   email while the filename only carries a name — those are different entity keys,
   so trusting the content's `FakePerson` is what keeps the path coherent with the
   file's contents.
2. **date / id groups** (`dob`, `date`, `id`) — masked through the shared
   `MappingStore` / faker. The date token's separators are normalized to `.`
   before masking, so it equals the content's masked DOB under `--consistent`
   **when the in-file and filename dates share the same field ordering**
   (day/month/year). A filename DOB is always a *valid* masked date; exact
   cross-coherence with the in-file DOB is best-effort, not guaranteed (see the
   plan's "Known limitation").
3. **Opaque (last resort)** — if a matched component yields no usable masked value
   (e.g. an empty capture, or a name group with neither content identity nor a
   maskable captured value), the whole component becomes `record_{n:04d}` from
   `fallback_counter`.

Reconstruction substitutes the masked values into the matched group spans,
preserving the literal separators and any uncaptured text. The file suffix is
never altered.

**Collision handling:** if the produced relative path is already in `used_paths`,
append `_2`, `_3`, … to the final component's stem until unique.

### Profile addition: `filename_patterns`

```yaml
filename_patterns:
  - "(?P<name_last>[^_/]+)_(?P<name_first>[^_/]+)_(?P<dob>\\d{2}_\\d{2}_\\d{4})"
```

- A list of regexes with **semantic** named groups. Recognized group names:
  `name_first`, `name_last`, `name` (full), `dob`, `date`, `id`.
- Patterns are matched against each relative-path component. First match wins.
- `MaskingProfile` parses this into a list of compiled patterns; absent →
  empty list (filename parsing simply never matches, content/opaque still work).
- The shipped `profiles/health_records.yaml` gains the AMVU pattern above.

### Content primary-identity exposure

`mask_dataframe` currently returns `(masked_df, replacements)`. The `EntityMasker`
already caches every `EntityContext` it creates, in insertion order. We expose the
**first** created entity as the file's primary identity:

- Add `EntityMasker.primary_person() -> FakePerson | None` returning the first
  cached context's `person` (or `None` if no identity was found).
- `pipeline._process_file` reads it after masking all sheets and passes it to
  `mask_relative_path`. (Across multiple sheets the masker instance is shared, so
  "first identity in the file" is well-defined.)

Today the `EntityMasker` is created *inside* `mask_dataframe`, so the pipeline
cannot reach it. The next section hoists its construction into the pipeline so it
can be shared across a file's sheets and the path masker.

### Pipeline wiring

Today `mask_dataframe` constructs its own `EntityMasker` per call. To share one
masker (and its caches) across a file's sheets **and** the path masker, the
`EntityMasker` is hoisted: constructed in `pipeline._process_file` and passed
into `mask_dataframe` as an optional argument (defaulting to a fresh one to keep
existing callers/tests working).

Per-file flow (folder mode, `mask_filenames=True`):

```
load_table
  -> entity_masker = EntityMasker(faker, mapping_store, consistent)
  -> for each sheet: mask_dataframe(..., entity_masker=entity_masker)
  -> primary = entity_masker.primary_person()
  -> masked_rel = mask_relative_path(rel_path, primary, profile, entity_masker, ...)
  -> export to output_root / masked_rel
  -> record original_rel -> masked_rel in mapping_store ("path" category) if consistent
```

When `mask_filenames=False` or single-file input, `_resolve_output_path` behaves
exactly as today.

### Report & mapping changes

- `build_report` already takes `omit_originals`. Extend it so that when
  `omit_originals` is true, `source_file` is the **masked** relative path (or
  basename) and the original path is omitted; with `--include-originals`, include
  an extra `original_source_file` field.
- The original→masked relative-path map is stored in the `MappingStore` under a
  `path` category when `--consistent`, enabling authorized traceability via the
  (sensitive) mapping file.

### CLI / config

- `PreprocessConfig.mask_filenames: bool = True`.
- `cli.py mask`: `--mask-filenames/--keep-filenames` Typer flag, default true,
  wired into the config. (`scan` is dry-run and writes no files; the flag is
  irrelevant there and is not added.)

## Error handling

- A malformed regex in `filename_patterns` raises a `ProfileNotFoundError`-style
  profile error at load time (clear message, not a crash mid-run).
- A path component that matches no pattern and has no content identity falls back
  to the opaque token — never left unmasked, never silently dropped.

## Testing (TDD)

`tests/test_path_masker.py`
- content identity renders fake first/last into the matched pattern;
- filename-parse fallback masks captured fields coherently (same fake as a shared
  entity) when there is no content identity;
- opaque fallback yields `record_0001` for a person-less, non-matching name;
- collision between two distinct fake-name files appends `_2`.

`tests/test_profiles.py`
- `filename_patterns` parse into usable compiled patterns; malformed pattern errors.

`tests/test_pipeline.py`
- folder input with `mask_filenames=True` writes outputs under masked relative
  paths and the report omits the original path by default;
- `--keep-filenames` / single-file input preserves current path behavior.

## Out of scope (YAGNI)

- Renaming based on multiple identities in one file (only the primary is used).
- Masking absolute path prefixes outside the mirrored relative portion.
- PDF reading (separate Phase 5 work); this design only masks *paths*.
