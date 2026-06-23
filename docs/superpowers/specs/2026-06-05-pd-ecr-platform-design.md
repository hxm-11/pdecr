# PD-ECR Platform Design

## Goal

Build the PD-ECR web workflow shown in the two reference images inside the existing FastAPI + React application.

The page has two work areas:

- Historical data search: search the PD-ECR knowledge base or historical data and display results in four modules.
- New creation: create a new change request, then generate AI content for each PD-ECR page/module.

## Routes

- `/pd-ecr`: main platform page.
- `/pd-ecr/content`: generated content block page.
- `/pd-ecr/content/$moduleId`: detail view for a selected module.

## Main Platform Page

The top section mirrors the first reference image:

- Title: `PD-ECR Platform`.
- User greeting area.
- `AI Search` arrow label.
- Search text input for historical PD-ECR keywords.
- `Run` button.
- Historical result panel with:
  - Similar CASE summary.
  - `PD-ECR one page` module grid.
  - `Refer to` matched PD-ECR identifiers.

The four historical modules are:

- `change-description`: 变更描述.
- `impact-analysis`: 影响分析.
- `validation-plan`: 验证计划.
- `execution-checklist`: 执行清单.

Each module is clickable and opens the corresponding report detail view.

The lower section mirrors the first reference image:

- `New creation` arrow label.
- Inline form fields:
  - 变更来源.
  - 变更背景原因.
  - 变更描述.
  - Target Close date.
- `AI 一键生成每页内容` action.

Clicking `AI 一键生成每页内容` submits the new-change form to the backend AI generation endpoint and navigates to `/pd-ecr/content`.

## Generated Content Page

The generated content page mirrors the second reference image:

- Title: `PD-ECR AI`.
- Subtitle: `PD-ECR content block`.
- Four large module blocks:
  - 变更描述.
  - 影响分析.
  - 验证计划.
  - 执行清单.

Each block is clickable and opens `/pd-ecr/content/$moduleId`, showing the generated report content for that module.

## Backend Integration

Use existing backend routes:

- `POST /api/v1/pd-ecr/test-rag` for historical search preview when `Run` is clicked.
- `POST /api/v1/pd-ecr/generate-report` for AI content generation from the new-change form.

The frontend maps user inputs to the existing `PdEcrInput` fields:

- 变更来源 -> `initiator` or `remarks` depending on available context.
- 变更背景原因 -> `reason`.
- 变更描述 -> `change_proposal`.
- Target Close date -> `remarks` until a dedicated backend field exists.
- Search query -> `reason` / `change_proposal` for RAG search.

If backend generation returns `modules`, those modules drive the UI. If the backend is unavailable or the response lacks module data, the UI shows a readable fallback state instead of a blank page.

## UI Principles

- Match the reference layout closely enough for recognition, but implement it as a responsive web page rather than a PowerPoint canvas.
- Use the existing React, TanStack Router, Tailwind, and shadcn-style components.
- Use Bosch-style visual cues: teal gradient background, dark blue action arrows, white table panels, bottom color strip, and Bosch logo asset if available.
- On smaller screens, stack sections vertically and keep all text readable.

## Acceptance Criteria

- `/pd-ecr` is reachable from the authenticated app sidebar.
- `Run` searches historical PD-ECR data and fills the top module grid.
- Each top module opens a corresponding detail view.
- The new-change row accepts user input.
- `AI 一键生成每页内容` calls the AI generation endpoint and navigates to `/pd-ecr/content`.
- `/pd-ecr/content` shows the four generated modules.
- Each generated module opens its corresponding generated report detail.
- The app builds successfully with `npm run build`.
