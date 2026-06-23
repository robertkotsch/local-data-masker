# Integration as a Pre-processing Component

`local-data-masker` is designed to run **before** the actual data-processing, AI, analytics, or RAG workflow.

It should be treated as a reusable pre-processing step that can be plugged into another project.

---

## Concept

```text
raw data -> local-data-masker -> masked data -> your actual processing pipeline
```

The downstream project should only receive masked output.

Examples of downstream projects:

- cloud LLM experiments
- RAG pipelines
- vector database ingestion
- analytics pipelines
- dashboard generation
- ML/AI prototyping
- test data generation
- e-learning demo workflows

---

## Two ways to use it

### 1. CLI pre-processing step

Use the command line when the masker is a separate pre-processing job.

```bash
local-data-masker mask data/raw \
  --output data/masked \
  --report data/reports/masking-report.json \
  --profile profiles/default.yaml \
  --consistent \
  --mapping data/mappings/local.mapping.json
```

Then your actual project works only with:

```text
data/masked
```

### 2. Python API integration

Use the Python API when another project should call the masker directly.

```python
from pathlib import Path

from local_data_masker.pipeline import PreprocessConfig, preprocess

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

for result in results:
    print(result.source_file, result.masked_file, result.replacements_count)
```

---

## Recommended project layout

```text
my-ai-project/
├── data/
│   ├── raw/           # never upload, never send to cloud AI
│   ├── masked/        # safe candidate input for downstream processing
│   ├── reports/       # review before sharing
│   └── mappings/      # sensitive, never commit or upload
├── profiles/
│   └── default.yaml
├── src/
│   └── my_ai_project/
│       ├── preprocess.py
│       ├── rag_pipeline.py
│       └── analytics.py
└── .gitignore
```

---

## Example downstream pipeline

```python
from pathlib import Path

from local_data_masker.pipeline import PreprocessConfig, preprocess
from my_ai_project.rag_pipeline import ingest_masked_documents

masking_results = preprocess(
    PreprocessConfig(
        input_path=Path("data/raw"),
        output_path=Path("data/masked"),
        report_path=Path("data/reports/masking-report.json"),
        profile_path=Path("profiles/default.yaml"),
        consistent=True,
        mapping_path=Path("data/mappings/local.mapping.json"),
    )
)

masked_files = [result.masked_file for result in masking_results if result.masked_file]
ingest_masked_documents(masked_files)
```

---

## Integration contract

The pre-processing step should guarantee as much as possible that:

- raw data is read only inside the local masking boundary,
- downstream projects receive masked files only,
- original values are not included in reports unless explicitly requested,
- mapping files are treated as secrets,
- reports are available for review and validation,
- the downstream pipeline can stop if masking fails.

---

## Failure behavior

When the pre-processing step fails, the downstream pipeline should not continue.

Recommended pattern:

```python
try:
    results = preprocess(config)
except Exception as exc:
    raise RuntimeError("Masking failed. Downstream processing was stopped.") from exc
```

---

## Important boundary

This project is not the actual AI or analytics processor.

It is the **protective pre-processing layer** before the real processing begins.

That keeps responsibilities clear:

```text
local-data-masker = prepare safe data
other project      = process safe data
```
