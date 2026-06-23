# Adaptive Masking Plan Workflow

`local-data-masker` should not assume that the input data structure is known in advance.

In real projects, the incoming data may come from different systems, customers, exports, PDFs, spreadsheets, reports, or mixed sources. Column names, sheet names, field meanings, languages, and formats may vary from project to project.

The adaptive workflow therefore separates **plan inference** from **full-dataset masking**.

---

## Core pipeline

```text
sensitive data
-> profiling and sampling
-> local LLM infers a masking plan
-> deterministic algorithm masks the full dataset
-> masked export preserves the original downstream structure
-> normal downstream processing continues
```

The local LLM helps the tool understand unknown structures. The deterministic masking engine performs the actual full-scale masking.

---

## Why the LLM should infer, not execute

A local LLM is useful for answering questions such as:

```text
What does this unknown column probably mean?
```

It is not the right component for applying replacements to millions of rows.

The deterministic engine is better suited for:

- applying the same plan reliably,
- processing large datasets,
- preserving row counts and column structures,
- producing audit reports,
- streaming or chunking large files,
- validating the masked output.

This keeps the system adaptive but still controlled, reproducible, and auditable.

---

## Recommended flow

```text
1. Read metadata
   - file names
   - sheet names
   - column names
   - data types
   - row counts

2. Profile the data
   - value patterns
   - null rates
   - uniqueness/cardinality
   - date-like values
   - email-like values
   - ID-like values
   - suspicious free-text cells

3. Build representative samples
   - first rows
   - random rows
   - suspicious rows
   - high-cardinality examples
   - free-text examples

4. Ask a local LLM for interpretation
   - infer categories
   - suggest masking strategies
   - assign confidence scores
   - flag fields that require review

5. Generate an explicit masking plan
   - YAML or JSON
   - editable
   - auditable
   - reusable

6. Apply deterministic masking
   - full dataset
   - same output structure
   - same file shape where possible
   - coherent fake entities

7. Validate masked output
   - scan output again
   - generate residual-risk warnings
   - block downstream processing if risk is too high
```

---

## Sampling strategy

Do not rely only on the first 2,000 rows.

A better default sample should combine:

```text
first rows + random rows + suspicious rows + column statistics
```

Example:

- first 500 rows,
- random 1,000 rows,
- rows containing `@`, long free text, dates, IDs, IBAN-like values, phone-like values,
- per-column statistics and examples.

The LLM should receive a **profile summary**, not the entire raw dataset.

---

## Example masking plan

```yaml
version: 1
source:
  file: customer_training_export.xlsx
  sheet: Participants

columns:
  Teilnehmer:
    action: mask
    category: name
    strategy: coherent_person
    confidence: 0.92
    review_required: false

  E-Mail Adresse:
    action: mask
    category: email
    strategy: coherent_person
    confidence: 0.99
    review_required: false

  Geburtsdatum:
    action: mask
    category: date_of_birth
    strategy: date_shift_birthdate
    confidence: 0.88
    review_required: false

  Schulung:
    action: mask
    category: course_title
    strategy: semantic_replacement
    confidence: 0.81
    review_required: false

  Kommentar:
    action: scan_cells
    category: mixed_text
    strategy: inline_scan_and_replace
    confidence: 0.67
    review_required: true
```

The LLM may suggest this plan, but the deterministic executor applies it.

---

## Same-structure output principle

The masked export should behave like the original input from the downstream process perspective.

Where possible, it should preserve:

- file type,
- sheet names,
- column names,
- row count,
- basic data types,
- relationships between fields,
- semantic usefulness.

The downstream project should not need to know whether masking happened.

```text
same input contract
same output contract
but sensitive values are replaced
```

---

## Example integration with another project

```python
from pathlib import Path

from local_data_masker import PreprocessConfig, preprocess
from my_project.pipeline import process_data

masking_results = preprocess(
    PreprocessConfig(
        input_path=Path("data/raw"),
        output_path=Path("data/masked"),
        report_path=Path("data/reports/masking-report.json"),
        profile_path=Path("plans/generated-plan.yaml"),
        consistent=True,
        mapping_path=Path("data/mappings/local.mapping.json"),
    )
)

masked_files = [result.masked_file for result in masking_results if result.masked_file]
process_data(masked_files)
```

In a later version, `profile_path` should be replaced or complemented by a dedicated `plan_path`.

---

## Future command structure

A future adaptive version could expose three commands:

```bash
local-data-masker plan data/raw \
  --output plans/generated-plan.yaml \
  --llm ollama:qwen3:4b \
  --sample-size 2000
```

```bash
local-data-masker apply data/raw \
  --plan plans/generated-plan.yaml \
  --output data/masked \
  --report data/reports/masking-report.json
```

```bash
local-data-masker preprocess data/raw \
  --output data/masked \
  --auto-plan \
  --llm ollama:qwen3:4b \
  --report data/reports/masking-report.json
```

---

## Design principle

Do not hard-code source structures.

Hard-code reusable categories and strategies instead.

Bad:

```python
if column == "name":
    mask_name()
```

Better:

```python
if inferred_category == "name":
    apply_strategy("coherent_person")
```

This allows the tool to adapt to unknown datasets while keeping the masking execution deterministic.

---

## Summary

The adaptive masking workflow should be:

```text
unknown sensitive structure
-> infer structure locally
-> generate explicit masking plan
-> optionally review plan
-> deterministically mask full dataset
-> export masked data in the same structure expected by downstream systems
```

This is the core concept that allows `local-data-masker` to act as a plug-in pre-processing step for other AI, analytics, RAG, or cloud-processing projects.
