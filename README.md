# Local Data Masker

A pluggable pre-processing layer that turns sensitive real-world data into masked, realistic, and useful datasets before the actual AI, analytics, RAG, or cloud-processing workflow begins.

> **Status:** Phase 3 complete; Phase 4+ planned  
> **Current focus:** structured data masking, semantic replacement profiles, coherent row-level entity masking (names, emails, and aligned person IDs), an importable pre-processing pipeline API, adaptive masking-plan generation, and PDF extraction concepts inspired by the AMVU Dashboard project.

---

## Why this project exists

Sensitive data is often not stored neatly in databases. It may appear in PDFs, exported reports, forms, learning documents, spreadsheets, screenshots, or mixed text sources.

The long-term goal of this project is to make it possible to experiment with huge datasets and cloud-based AI **without exposing raw sensitive data**.

The tool acts as a pre-processing safety layer:

```text
raw sensitive data -> local-data-masker -> masked dataset -> actual processing project
```

The downstream project should only receive masked output. That downstream project might be a cloud LLM workflow, RAG pipeline, vector database ingestion process, analytics job, dashboard generator, or another AI/data-processing tool.

For unknown data structures, the intended future workflow is:

```text
sensitive data
-> local profiling and sampling
-> local LLM infers a masking plan
-> deterministic algorithm masks the full dataset
-> masked export preserves the structure expected by downstream processing
```

Examples:

| Original | Masked |
|---|---|
| `Ben Miller` | `John Winter` |
| `1975/02/21` | `1976/03/20` |
| `Course: Money Laundering` | `Course: Healthy Nutrition` |
| `ben.miller@example.com` | `john.winter@example.test` |
| `Employee ID: 481927` | `Employee ID: 735204` |

The goal is not simply to redact data with black bars. The goal is to create **safe, realistic substitute data** that still works for testing, training, analytics, RAG, cloud AI evaluation, portfolio screenshots, and internal prototypes.

See also:

- [`docs/cloud-ai-workflow.md`](docs/cloud-ai-workflow.md)
- [`docs/integration-as-preprocessor.md`](docs/integration-as-preprocessor.md)
- [`docs/adaptive-masking-plan.md`](docs/adaptive-masking-plan.md)

---

## What works now

Phases 1 to 3 currently support:

- CSV files
- Excel files (`.xlsx`, `.xls`)
- single files or folders of files
- `mask` and `scan` CLI commands
- importable Python pre-processing API via `local_data_masker.pipeline`
- column-based detection for:
  - names
  - email addresses
  - phone numbers
  - IBANs
  - generic dates
  - dates of birth
  - ID-style columns
- coherent row-level person masking:
  - fake names and fake emails are generated as one identity
  - repeated email/name identities are reused within one run
  - with `--consistent`, coherent identities can be reused through the mapping file
- profile-based semantic masking for categories such as:
  - course titles
  - training names
  - project names
  - company/customer/supplier names
  - departments
  - product/application names
- custom substring replacements such as `Money Laundering` -> `Healthy Nutrition`
- consistent masking with a local mapping file
- JSON audit/finding reports
- safer reports that omit original values by default

---

## Getting started

The project is installed into a local virtual environment (`.venv/`), which is
git-ignored, so each developer creates their own. Requires Python 3.10+.

**Create the virtual environment** (once):

```bash
python -m venv .venv
```

**Activate it** (per terminal session):

```bash
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows cmd.exe
.venv\Scripts\activate.bat
```

> If PowerShell blocks activation with an execution-policy error, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Install the project and its dev dependencies** (editable install, so code
changes take effect without reinstalling):

```bash
pip install -e ".[dev]"
```

Once activated, the `local-data-masker` command and `pytest` resolve to the
versions inside `.venv`. Run `deactivate` to exit the environment. If you prefer
not to activate, you can call the tools directly, e.g.
`.venv\Scripts\local-data-masker.exe ...` on Windows or
`.venv/bin/local-data-masker ...` on Linux/macOS.

Mask the included example file:

```bash
local-data-masker mask examples/sample_courses.csv \
  --output masked/sample_courses_masked.csv \
  --report reports/sample_courses_report.json \
  --profile profiles/default.yaml \
  --seed 42
```

Scan without writing a masked output file:

```bash
local-data-masker scan examples/sample_courses.csv \
  --report reports/findings.json \
  --profile profiles/default.yaml
```

Include original values in the report only when you explicitly need them for local review:

```bash
local-data-masker scan examples/sample_courses.csv \
  --report reports/findings_with_originals.json \
  --profile profiles/default.yaml \
  --include-originals
```

Run the tests:

```bash
pytest
```

---

## Use as a pre-processing API

Other projects can call the masker before they start their own processing.

```python
from pathlib import Path

from local_data_masker import PreprocessConfig, preprocess

results = preprocess(
    PreprocessConfig(
        input_path=Path("data/raw"),
        output_path=Path("data/masked"),
        report_path=Path("data/reports/masking-report.json"),
        profile_path=Path("profiles/default.yaml"),
        mapping_path=Path("data/mappings/local.mapping.json"),
        consistent=True,
        omit_originals=True,
        seed=42,
    )
)

masked_files = [result.masked_file for result in results if result.masked_file]
```

The downstream project should consume `masked_files`, not the raw input files.

Detailed guide: [`docs/integration-as-preprocessor.md`](docs/integration-as-preprocessor.md)

---

## Adaptive masking plan workflow

The future adaptive workflow separates inference from execution:

```text
unknown sensitive structure
-> infer structure locally
-> generate explicit masking plan
-> optionally review plan
-> deterministically mask full dataset
-> export masked data in the same structure expected by downstream systems
```

A local LLM should be used to interpret unknown structures and suggest a masking plan. The full dataset should then be handled by deterministic code, not by the LLM.

Detailed concept: [`docs/adaptive-masking-plan.md`](docs/adaptive-masking-plan.md)

---

## PDF extraction lessons from AMVU Dashboard

The related `amvu-dashboard` project already demonstrates a useful pattern for turning many operational PDFs into structured Excel output.

The most relevant lessons for `local-data-masker` are:

### 1. Start with text and table extraction

The AMVU script uses `pdfplumber` to extract both full-page text and tables from `Untersuchungskartei.pdf` files. This is a good first model for a generic PDF extraction layer.

For `local-data-masker`, the first PDF milestone should not try to reconstruct a masked PDF immediately. A safer first step is:

```text
PDF -> extracted text + extracted tables -> findings report / masking plan
```

### 2. Separate extraction from interpretation

The AMVU project separates low-level extraction from domain interpretation:

```text
read PDF
-> extract text and tables
-> parse header fields
-> identify relevant tables
-> classify records
-> export structured workbook
```

For this project, the same pattern should become:

```text
read PDF
-> extract text and tables
-> profile structure
-> infer masking plan
-> apply deterministic masking
-> validate masked output
```

### 3. Handle multi-page tables carefully

Operational PDFs often split tables across pages. The AMVU parser handles continuation tables by tracking whether the parser is currently inside an examination table. This is important because a table may continue on the next page without repeating the header.

For `local-data-masker`, the PDF extractor should therefore preserve:

- page order,
- table order,
- table headers when available,
- continuation-table candidates,
- text blocks that are near tables.

### 4. Produce warnings instead of silently skipping content

The AMVU project distinguishes between missing PDFs, unreadable PDFs, empty records, non-critical records, and technical issues.

For masking, this is essential. A masking tool should not silently ignore parts of a document. It should create warnings such as:

- `missing_file`,
- `unreadable_pdf`,
- `no_text_extracted`,
- `table_extraction_failed`,
- `possible_scanned_pdf`,
- `review_required`,
- `unclassified_sensitive_candidate`.

### 5. Use parallel processing for large batches

The AMVU project processes many PDF folders in parallel and supports a serial mode for debugging. This pattern is useful for large-scale masking as well.

Recommended future design:

```text
--workers auto   # all available CPU cores
--workers 1      # deterministic debugging mode
```

### 6. Keep domain-specific logic out of the generic masker

The AMVU extraction rules are specific to occupational-health examination records. They should not be copied directly into `local-data-masker`.

The reusable idea is the extraction architecture:

```text
folder-based batch input
+ pdfplumber text/table extraction
+ structure profiling
+ warnings
+ parallel processing
+ structured output
```

The masking project should keep the PDF layer generic and let profiles or generated masking plans handle domain-specific interpretation.

---

## Coherent entity masking

The masker now treats related person fields in the same row as one synthetic identity.

Example input:

```text
name,email
Ben Miller,ben.miller@example.com
```

Possible masked output:

```text
name,email
John Winter,john.winter@example.test
```

This avoids incoherent output such as:

```text
John Winter,laura.smith@example.test
```

Identity matching currently uses this priority:

1. email address
2. person name
3. ID-style value as a fallback

That means repeated rows with the same detected email receive the same fake name and fake email within one run. When `--consistent` and `--mapping` are used, the coherent fake name and fake email are stored in the local mapping file and can be reused across runs.

Current scope:

- supported: `name` + `email` coherence
- partially supported: repeated identity reuse by email/name
- not yet supported: full document-level identity graphs or matching people across unstructured PDF text

---

## Cloud AI workflow

The project is designed around a three-zone model:

1. **Raw data zone** — original sensitive files stay local.
2. **Masking and validation zone** — local extraction, detection, masking, and reporting.
3. **Experimentation zone** — masked datasets can be used for cloud AI, analytics, RAG, vector databases, demos, and test systems.

This means the project is **local-first at the safety boundary**, but the masked output is intended to be cloud-ready.

Detailed concept: [`docs/cloud-ai-workflow.md`](docs/cloud-ai-workflow.md)

---

## Custom masking profiles

Profiles are YAML files that define semantic replacements without changing Python code.

Example:

```yaml
custom_replacements:
  Money Laundering: Healthy Nutrition
  Anti-Corruption: Workplace Safety
  Internal Audit: Learning Review

column_categories:
  course_title:
    columns:
      - course
      - course_title
      - training_name
    replacements:
      - Healthy Nutrition
      - Workplace Safety Basics
      - Digital Collaboration
      - Ergonomics at Work
```

The default profile is located here:

```text
profiles/default.yaml
```

### Custom replacements

Custom replacements are applied inside cell text. This means a value such as:

```text
Completed course Money Laundering with follow-up Internal Audit.
```

can become:

```text
Completed course Healthy Nutrition with follow-up Learning Review.
```

### Semantic column categories

Profile column categories allow the tool to mask fields such as `course_title`, `project_name`, `company`, or `department` even when they are not classic PII.

This is important because the project is not limited to personal data. It also masks sensitive business context and topic-specific information.

---

## Masking modes

### One-off masking

Default behavior. Each detected value receives a generated fake value. Coherent person identities are still reused within the current run.

```bash
local-data-masker mask input.csv --output output.csv
```

### Consistent masking

The same original value is always replaced with the same fake value within the same mapping file. Coherent fake person identities are stored as paired name/email mappings.

```bash
local-data-masker mask input.csv \
  --output output.csv \
  --consistent \
  --mapping local.mapping.json
```

> Mapping files contain original values and are sensitive. Do not commit or share them.

---

## Privacy and security principles

This project follows these principles:

- **Pre-processing boundary:** the masker runs before the real data processing starts.
- **Local-first safety boundary:** raw sensitive data is processed locally before anything can be used elsewhere.
- **Cloud-ready masked output:** masked datasets should be useful for cloud AI and analytics experiments.
- **No raw cloud upload:** raw sensitive inputs should not be uploaded to cloud AI services.
- **No telemetry:** the tool should not collect usage data.
- **No sensitive logs:** original values should not be written to normal logs.
- **Safe reports by default:** reports omit original values unless `--include-originals` is used.
- **Dry-run mode:** users can inspect findings before writing masked output.
- **Auditability:** replacements are traceable in a local report.
- **Configurable rules:** users can define custom detection and replacement rules.
- **Fail-safe behavior:** uncertain detections should be flagged for review rather than silently ignored.
- **Sensitive mapping files:** consistent masking mappings must be treated as secrets.

---

## Current architecture

```text
local-data-masker/
├── README.md
├── pyproject.toml
├── docs/
│   ├── adaptive-masking-plan.md
│   ├── cloud-ai-workflow.md
│   └── integration-as-preprocessor.md
├── profiles/
│   └── default.yaml
├── examples/
│   └── sample_courses.csv
├── src/
│   └── local_data_masker/
│       ├── __init__.py
│       ├── cli.py
│       ├── pipeline.py
│       ├── extractors/
│       │   └── table_extractor.py
│       ├── detectors/
│       │   ├── regex_detector.py
│       │   └── custom_rules.py
│       ├── maskers/
│       │   ├── entity_masker.py
│       │   ├── faker_provider.py
│       │   ├── mapping_store.py
│       │   ├── replacer.py
│       │   └── semantic_replacer.py
│       └── exporters/
│           ├── table_exporter.py
│           └── report_exporter.py
└── tests/
```

---

## Roadmap

### Phase 1: Structured data masking ✅

- [x] Read CSV and Excel files
- [x] Detect names, emails, phone numbers, IDs, IBANs, and dates
- [x] Replace values with fake data
- [x] Export masked CSV/XLSX files
- [x] Generate JSON audit reports

### Phase 2: Profile-based semantic masking ✅

- [x] Add YAML-based replacement rules
- [x] Support project-specific masking categories
- [x] Add semantic replacements for course titles, project names, companies, departments, and products
- [x] Make reports safer by default

### Phase 3: Coherent entity masking and pre-processing API ✅

- [x] Keep fake names and generated emails aligned
- [x] Reuse the same fake person identity for repeated email/name records
- [x] Persist coherent fake identities when `--consistent` and `--mapping` are used
- [x] Provide an importable `preprocess()` API for other projects
- [x] Align person-specific IDs with the generated entity

### Phase 4: Adaptive masking-plan generation

- [ ] Add data profiling and representative sampling
- [ ] Add local LLM-assisted masking-plan inference
- [ ] Add editable YAML/JSON masking plans
- [ ] Add `plan`, `apply`, and `preprocess --auto-plan` command flow
- [ ] Add confidence scores and review-required flags

### Phase 5: Generic PDF extraction and profiling

- [ ] Add a `pdf_extractor.py` based on the AMVU extraction lessons
- [ ] Extract text and tables with `pdfplumber`
- [ ] Preserve page order, table order, and continuation-table candidates
- [ ] Generate extraction warnings for unreadable/scanned/problematic PDFs
- [ ] Produce PDF structure profiles for masking-plan inference
- [ ] Add serial and parallel batch-processing modes

### Phase 6: Large dataset workflows

- [ ] Add dataset manifests
- [ ] Add chunked CSV processing
- [ ] Add Parquet support
- [ ] Add resumable batch jobs
- [ ] Add validation summaries for masked datasets

### Phase 7: PDF and document masking

- [ ] Detect sensitive values in extracted PDF text and tables
- [ ] Replace values in text output
- [ ] Evaluate PDF reconstruction options
- [ ] Evaluate PDF overlay/redaction options carefully, ensuring hidden text is not leaked

### Phase 8: Cloud AI export workflows

- [ ] Add masked-only export adapters
- [ ] Prepare datasets for embedding/RAG pipelines
- [ ] Add vector-ingestion export formats
- [ ] Add LLM evaluation dataset formats

### Phase 9: Review workflow and UI

- [ ] Add a review report
- [ ] Mark uncertain detections
- [ ] Add allowlist and blocklist support
- [ ] Add manual approval before export
- [ ] Add a simple local review UI

### Phase 10: OCR and visual documents

- [ ] Add OCR support for scanned PDFs and images
- [ ] Detect personal data in OCR text
- [ ] Explore visual redaction overlays or PDF layer replacement

---

## Non-goals for the first versions

The first versions will not attempt to:

- guarantee legal anonymization,
- process every complex PDF layout perfectly,
- replace professional privacy review,
- upload raw sensitive data to cloud-based AI services,
- hide sensitive data by merely drawing black boxes over text without removing the underlying content.

---

## Terminology

This project focuses on **data masking**.

Data masking means that real values are replaced by artificial values. The output should look realistic, but it should no longer reveal the original person, customer, course, organization, or business case.

This is different from simple anonymization or redaction:

- **Redaction** removes or hides information.
- **Pseudonymization** replaces data but may keep a reversible mapping.
- **Anonymization** aims to make re-identification impossible.
- **Masking** replaces sensitive values with plausible fake values while preserving usefulness.

This project should be treated as a **local masking and pseudonymization tool**, not as a legal guarantee of full anonymization.

---

## License

License to be decided.
