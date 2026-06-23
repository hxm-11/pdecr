# PD-ECR Case Ingestion Skill

## Purpose

Convert a parsed PD-ECR source file into one standardized PD-ECR case JSON file.

This skill is used after MinerU has parsed the original PD-ECR file into Markdown, JSON, text, tables, and image assets.

The final output must be a single standard JSON file that can be placed under:

```text
backend/app/data/pd_ecr_cases/
```

## Input

The input may include:

```text
1. Original source file name
2. MinerU parsed Markdown
3. MinerU parsed JSON
4. OCR text
5. Extracted tables
6. Extracted image paths
7. Existing manually cleaned text
```

## Output

The output must be one JSON object following `schema_version = "pdecr_case_v1"`.

Do not output explanations outside the JSON unless explicitly asked.

## Required Top-Level Fields

```json
{
  "schema_version": "pdecr_case_v1",
  "case_id": "",
  "source_file": "",
  "source_type": "",
  "mineru_output_dir": "",
  "metadata": {},
  "modules": {},
  "missing_fields": [],
  "quality_check": {}
}
```

## Required Metadata Fields

The metadata object must include:

```json
{
  "dc_no": "",
  "mcr_no": "",
  "date": "",
  "customer_project": [],
  "product_no": [],
  "part_no": [],
  "change_type": "",
  "initiator": "",
  "sample_status": ""
}
```

Rules:

1. `case_id` must be taken from existing metadata first.
2. If no explicit case_id exists, derive it from the file name.
3. `source_file` must always preserve the original file name.
4. `customer_project`, `product_no`, and `part_no` must always be arrays.
5. Missing required fields must be added to `missing_fields`.
6. Do not silently omit fields.

## Required Modules

The modules object must contain exactly these six modules:

```json
{
  "basic_information": {},
  "change_description": {},
  "reason_for_change": {},
  "impact_analysis": {},
  "implementation_plan": {},
  "approval_signoff_reference": {}
}
```

Each module must follow this structure:

```json
{
  "content": "",
  "evidence": [],
  "needs_human_input": false,
  "warnings": []
}
```

## Evidence Format

Each evidence item must follow this structure:

```json
{
  "source_file": "",
  "source_page": "",
  "source_section": "",
  "snippet": "",
  "confidence": "high | medium | low"
}
```

Rules:

1. Evidence must point to the source file or MinerU output.
2. If page number is unknown, set `source_page` to an empty string.
3. If the extraction is uncertain, use `confidence: "low"` and add a warning.
4. Do not invent evidence.

## Module Mapping Rules

Map original PD-ECR content into the six V1 modules as follows:

### basic_information

Include basic case identity and product/project information:

```text
DC No
MCR No
Date
Customer project
Product number
Part number
Initiator
Sample status
```

### change_description

Include:

```text
current design
proposed change
changed part/component
before/after difference
change request description
```

### reason_for_change

Include:

```text
reason for change
problem background
customer requirement
quality issue
cost reduction reason
manufacturing reason
technical improvement reason
```

### impact_analysis

Include:

```text
product impact
process impact
customer impact
quality impact
validation impact
drawing/BOM/software impact
risk analysis
```

### implementation_plan

Include:

```text
implementation step
trial plan
validation plan
cut-in plan
sample plan
responsible department
expected timing
```

### approval_signoff_reference

Include only extracted approval or sign-off related source information.

Do not claim that any person has approved the change unless the source explicitly says so.

This module should usually set:

```json
"needs_human_input": true
```

and include a warning:

```text
Approval/sign-off information must be verified manually.
```

## Missing Field Rules

The following fields are required:

```text
case_id
source_file
metadata.dc_no
metadata.customer_project
modules.change_description.content
modules.reason_for_change.content
```

If any required field is missing, add its path to `missing_fields`.

Example:

```json
"missing_fields": [
  "metadata.dc_no",
  "modules.reason_for_change.content"
]
```

## Quality Check Rules

The quality_check object must include:

```json
{
  "metadata_complete": false,
  "module_complete": false,
  "human_review_required": true,
  "notes": []
}
```

Rules:

1. `metadata_complete` is true only when all required metadata fields are present.
2. `module_complete` is true only when all six modules have useful content or a clear human-input warning.
3. `human_review_required` should be true by default for V1.
4. Add notes for weak OCR, missing tables, missing approval page, unclear product numbers, or uncertain mapping.

## Prohibited Behavior

Do not:

```text
1. Invent DC No, MCR No, product number, part number, approval status, or dates.
2. Rename schema fields.
3. Add new top-level fields without instruction.
4. Drop source_file.
5. Drop image/table references if they contain useful engineering information.
6. Convert uncertain information into confirmed facts.
7. Produce final approval conclusions.
8. Modify the original source file.
```

## Final Output Rule

Return only valid JSON.

The JSON must be parseable by Python `json.loads()`.

No Markdown fences.
No comments.
No extra explanation.
