# Local Data Masker

A local safety gateway for turning sensitive real-world data into masked, realistic, and useful datasets for large-scale analytics, cloud AI experiments, RAG pipelines, demos, and test systems.

> **Status:** Phase 3 started  
> **Current focus:** structured data masking, semantic replacement profiles, coherent row-level entity masking, and cloud-ready masked dataset workflows.

---

## Why this project exists

Sensitive data is often not stored neatly in databases. It may appear in PDFs, exported reports, forms, learning documents, spreadsheets, screenshots, or mixed text sources.

The long-term goal of this project is to make it possible to experiment with huge datasets and cloud-based AI **without exposing raw sensitive data**.

The local tool acts as a safety gateway:

```text
raw sensitive data -> local masking + validation -> masked dataset -> cloud AI / analytics / RAG experiments
```

Raw data should stay local. Masked and validated data can then be used for experiments with LLMs, embeddings, vector databases, analytics workflows, dashboards, and prototype applications.

Examples:

| Original | Masked |
|---|---|
| `Ben Miller` | `John Winter` |
| `1975/02/21` | `1976/03/20` |
| `Course: Money Laundering` | `Course: Healthy Nutrition` |
| `ben.miller@example.com` | `john.winter@example.test` |
| `Employee ID: 481927` | `Employee ID: 735204` |

The goal is not simply to redact data with black bars. The goal is to create **safe, realistic substitute data** that still works for testing, training, analytics, RAG, cloud AI evaluation, portfolio screenshots, and internal prototypes.

See also: [`docs/cloud-ai-workflow.md`](docs/cloud-ai-workflow.md)

---

## What works now

Phase 1 to early Phase 3 currently supports:

- CSV files
- Excel files (`.xlsx`, `.xls`)
- single files or folders of files
- `mask` and `scan` CLI commands
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

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

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
│   └── cloud-ai-workflow.md
├── profiles/
│   └── default.yaml
├── examples/
│   └── sample_courses.csv
├── src/
│   └── local_data_masker/
│       ├── cli.py
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

### Phase 1: Structured data masking

- Read CSV and Excel files
- Detect names, emails, phone numbers, IDs, IBANs, and dates
- Replace values with fake data
- Export masked CSV/XLSX files
- Generate JSON audit reports

### Phase 2: Profile-based semantic masking

- Add YAML-based replacement rules
- Support project-specific masking categories
- Add semantic replacements for course titles, project names, companies, departments, and products
- Make reports safer by default

### Phase 3: Coherent entity masking

- Keep fake names and generated emails aligned
- Reuse the same fake person identity for repeated email/name records
- Persist coherent fake identities when `--consistent` and `--mapping` are used
- Next: align person-specific IDs more explicitly with the generated entity

### Phase 4: Large dataset workflows

- Add dataset manifests
- Add chunked CSV processing
- Add Parquet support
- Add resumable batch jobs
- Add validation summaries for masked datasets

### Phase 5: PDF and document extraction

- Extract text from normal PDFs
- Detect sensitive values in extracted text
- Replace values in text output
- Evaluate PDF reconstruction options

### Phase 6: Cloud AI export workflows

- Add masked-only export adapters
- Prepare datasets for embedding/RAG pipelines
- Add vector-ingestion export formats
- Add LLM evaluation dataset formats

### Phase 7: Review workflow and UI

- Add a review report
- Mark uncertain detections
- Add allowlist and blocklist support
- Add manual approval before export
- Add a simple local review UI

### Phase 8: OCR and visual documents

- Add OCR support for scanned PDFs and images
- Detect personal data in OCR text
- Explore visual redaction overlays or PDF layer replacement

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
