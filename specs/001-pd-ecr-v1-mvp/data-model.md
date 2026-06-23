# Data Model: PD-ECR V1 MVP

## HistoricalCase

Represents one historical PD-ECR case loaded from Markdown, JSON, OCR output, or
curated case data.

**Fields**:

- `case_id` string, required after normalization
- `metadata` HistoricalMetadata, required
- `modules` object keyed by V1 module ID, optional per module
- `source_file` string, required
- `source_trace` SourceTrace, optional
- `raw_text` string, optional for retrieval and module extraction
- `missing_fields` string array, required when metadata is incomplete

**Relationships**:

- Has one HistoricalMetadata.
- Has zero or more HistoricalModule records.
- May appear in many SimilarCaseResult records.

**Validation rules**:

- `case_id` and `source_file` must be non-empty.
- Missing canonical metadata fields must be listed in `missing_fields`.
- Module content may be empty, but empty modules must be displayed explicitly.

## HistoricalMetadata

Canonical metadata carried through list, detail, retrieval, generation, and
export.

**Fields**:

- `case_id` string
- `dc_no` string
- `mcr_no` string
- `change_type` string
- `product_no` string
- `part_no` string
- `customer_project` string or string array normalized for display
- `source_file` string
- `date` string, optional
- `initiator` string, optional
- `sample_status` string or string array, optional

**Validation rules**:

- Canonical fields must always exist in API responses.
- Empty values are allowed only with explicit missing-field reporting.
- `part_no` may be derived from existing `component_no` during V1 adaptation.

## HistoricalModule

Represents a section extracted from a historical case.

**Fields**:

- `module_id` enum:
  - `basic_information`
  - `change_description`
  - `reason_for_change`
  - `impact_analysis`
  - `implementation_plan`
  - `approval_signoff_information`
- `title` string
- `summary` string
- `content` string
- `source_file` string
- `source_pages` number array, optional
- `confidence` enum: `high`, `medium`, `low`, optional

**Validation rules**:

- `module_id`, `title`, and `source_file` are required.
- If content is unavailable, `summary` should state that the source has no
  extracted content for this module.

## NewPdEcrRequest

User-submitted input for retrieval and generation.

**Fields**:

- `dc_no` string, required
- `mcr_no` string, required
- `customer_project` string, required
- `product_no` string, required
- `part_no` string, required
- `change_type` string, required
- `change_description` string, required
- `change_reason` string, required
- `date` string, optional
- `initiator` string, optional
- `current_design` string, optional
- `change_proposal` string, optional
- `remarks` string, optional
- `top_k` number, optional default 5

**Validation rules**:

- Required fields must be present before retrieval or generation.
- `top_k` defaults to 5 and should be bounded for V1 demo use.
- Existing backend field aliases map `part_no` to `component_no` and
  `change_reason` to `reason`.

## SimilarCaseResult

One ranked retrieval result.

**Fields**:

- `rank` number
- `case_id` string
- `dc_no` string
- `change_type` string
- `matched_fields` string array
- `similarity_score` number
- `similarity_reason` string
- `source_file` string
- `module_summary` string
- `source_cases` string array
- `source_files` string array
- `retrieval_mode` enum: `faiss`, `keyword_fallback`, `hybrid_keyword`, `hybrid`
- `retrieval_context` RetrievalContext

**Validation rules**:

- `case_id`, `source_file`, `similarity_score`, and `module_summary` are
  required.
- `source_files` must contain `source_file`.
- Results are sorted by rank ascending and score descending.

## RetrievalContext

Evidence package passed to AI generation.

**Fields**:

- `matched_fields` string array
- `keyword_hits` string array
- `semantic_score` number, optional
- `metadata_score` number, optional
- `evidence_snippets` EvidenceSnippet array
- `module_summary` string

**Validation rules**:

- Evidence snippets must carry `source_file`.
- Snippets should be short enough for prompt use and UI display.

## EvidenceSnippet

Small source excerpt or extracted summary used as grounding evidence.

**Fields**:

- `source_file` string
- `case_id` string
- `module_id` string, optional
- `text` string
- `page` number, optional
- `confidence` enum: `high`, `medium`, `low`, optional

## GeneratedDraft

AI-assisted PD-ECR output.

**Fields**:

- `draft_id` string
- `draft_status` enum: `V1_MVP_DRAFT`
- `input_snapshot` NewPdEcrRequest
- `similar_cases` SimilarCaseResult array
- `modules` GeneratedModule array
- `report_url` string, optional
- `generated_at` string

**Relationships**:

- Belongs to one NewPdEcrRequest snapshot.
- References zero or more SimilarCaseResult records.
- Has exactly six GeneratedModule records.

**Validation rules**:

- Must contain exactly the six V1 modules.
- Must never be marked as production-approved.

## GeneratedModule

One generated section in the six-module V1 draft.

**Fields**:

- `module_id` enum:
  - `basic_information`
  - `change_description`
  - `reason_for_change`
  - `impact_analysis`
  - `implementation_plan`
  - `approval_signoff_information`
- `title` string
- `summary` string
- `content` string or object
- `source_cases` string array
- `source_files` string array
- `needs_human_input` boolean
- `warnings` string array

**Validation rules**:

- Modules based on historical evidence must include at least one source case or
  source file.
- Modules without enough evidence must set `needs_human_input` to true and state
  the missing evidence in `warnings`.

## BasicReportExport

Export-ready package for the demo report.

**Fields**:

- `export_id` string
- `draft_id` string
- `format` enum: `html`, `csv`
- `draft_status` string
- `input_snapshot` NewPdEcrRequest
- `similar_cases` SimilarCaseResult array
- `modules` GeneratedModule array
- `source_files` string array
- `download_url` string, optional
- `created_at` string

**Validation rules**:

- Export includes draft/demo status.
- Export includes source references and similar cases.
