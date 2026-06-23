# Research: PD-ECR V1 MVP

## Decision: Normalize historical cases through a V1 adapter before UI/API use

**Rationale**: Historical data currently exists across JSON metadata, OCR output,
Markdown knowledge files, clean text, and a manually curated case JSON file. A
single adapter lets V1 preserve existing files while exposing one stable contract
to retrieval, generation, frontend display, and export.

**Alternatives considered**:

- Rewrite all historical files into one new database: rejected for V1 because it
  adds migration work and production-like data operations.
- Keep current ad hoc shapes in each endpoint: rejected because source
  traceability and metadata completeness would remain inconsistent.

## Decision: Use snake_case API fields with business-label aliases in UI

**Rationale**: Existing backend and frontend code already use fields such as
`dc_no`, `mcr_no`, `product_no`, and `component_no`. Keeping snake_case in API
payloads avoids churn while allowing UI labels such as DC No, MCR No, 产品号, and
零件号.

**Alternatives considered**:

- Use display labels directly as JSON keys: rejected because spaces, casing, and
  bilingual labels make typed code harder to maintain.

## Decision: Keep current RAG engine and add metadata/keyword/semantic ranking adapter

**Rationale**: `backend/app/rag/retriever.py` already supports FAISS semantic
search and keyword fallback. V1 needs better result shape and metadata boosts,
not a new search engine.

**Alternatives considered**:

- Build a new vector store: rejected for V1 scope and data migration cost.
- Keyword-only search: rejected because similar engineering changes may share
  meaning without exact wording.

## Decision: Default Top K to 5

**Rationale**: The specification defines 5 as the default. It is enough for demo
comparison without overwhelming the user, and existing retrieval can request more
internally for reranking.

**Alternatives considered**:

- Always return 20: rejected because the UI success criteria and MVP demo focus
  on readable, ranked references.

## Decision: Require structured JSON from AI generation and validate before display

**Rationale**: Existing generation renders template modules from LLM fields. The
V1 contract needs six named modules with source references and human-input flags,
so generated JSON must be parsed and validated before frontend display/export.

**Alternatives considered**:

- Let the LLM return Markdown only: rejected because module-level source
  traceability would be unreliable.
- Trust any JSON-like model output: rejected because malformed modules could hide
  missing source references.

## Decision: Preserve existing generated report HTML and add V1 export envelope

**Rationale**: Existing report generation already writes HTML files. V1 can add
source references, submitted form data, similar cases, six modules, and draft
status around that output instead of introducing a new document engine.

**Alternatives considered**:

- Implement PDF/XLSX export immediately: rejected as unnecessary for the MVP
  success criteria.

## Decision: Use existing frontend PD-ECR routes and local state, then tighten types

**Rationale**: The frontend already has case list, creation workflow, content
blocks, module detail, and export helpers. Updating these screens to the V1 six
module contract is lower risk than replacing the flow.

**Alternatives considered**:

- Create a separate new V1 frontend app area: rejected because it duplicates
  existing pages and increases demo inconsistency.

## Decision: Store generated draft state statelessly first, with cache fallback

**Rationale**: V1 is demo/trial oriented. A `draft_id` derived from input hash or
generation result can support `GET /drafts/{draft_id}/modules` without a full
production persistence model. Existing SQLite module drafts can remain for local
editable module data.

**Alternatives considered**:

- Add production database tables now: rejected because V1 does not promise system
  of record behavior.
