# PD-ECR Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PD-ECR platform and generated content pages in the existing React frontend, connected to existing FastAPI PD-ECR RAG and generation routes.

**Architecture:** Add a focused PD-ECR API wrapper, a small shared data/state module, and focused React components for the platform shell, module grid, creation form, content block page, and module detail page. TanStack file routes expose `/pd-ecr`, `/pd-ecr/content`, and `/pd-ecr/content/$moduleId`.

**Tech Stack:** React 19, TanStack Router, TanStack Query, Tailwind CSS, axios, FastAPI backend routes under `/api/v1/pd-ecr`.

---

## File Structure

- Create `frontend/src/lib/pdEcrApi.ts`: typed axios wrapper for `/api/v1/pd-ecr/test-rag` and `/api/v1/pd-ecr/generate-report`.
- Create `frontend/src/components/PdEcr/pdEcrState.ts`: module definitions, fallback data, and localStorage helpers for generated content.
- Create `frontend/src/components/PdEcr/PdEcrPlatform.tsx`: first-page UI, historical search, new creation form, and navigation after AI generation.
- Create `frontend/src/components/PdEcr/PdEcrContentBlocks.tsx`: second-page four-block UI.
- Create `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`: detail page for one module.
- Create `frontend/src/routes/_layout/pd-ecr.tsx`: `/pd-ecr` route.
- Create `frontend/src/routes/_layout/pd-ecr.content.tsx`: `/pd-ecr/content` route.
- Create `frontend/src/routes/_layout/pd-ecr.content.$moduleId.tsx`: `/pd-ecr/content/$moduleId` route.
- Modify `frontend/src/components/Sidebar/AppSidebar.tsx`: add PD-ECR sidebar link.
- Create `frontend/tests/pd-ecr.spec.ts`: Playwright coverage for page visibility, mocked historical search, mocked generation, navigation, and detail display.

## Task 1: Add Failing Route And Workflow Test

**Files:**
- Create: `frontend/tests/pd-ecr.spec.ts`

- [ ] **Step 1: Write the failing test**

Write Playwright tests that mock auth and PD-ECR backend responses, then assert the route and workflow.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend; npx playwright test tests/pd-ecr.spec.ts --project=chromium`
Expected: FAIL because `/pd-ecr` route and UI do not exist yet.

## Task 2: Add API And State Helpers

**Files:**
- Create: `frontend/src/lib/pdEcrApi.ts`
- Create: `frontend/src/components/PdEcr/pdEcrState.ts`

- [ ] **Step 1: Implement typed API functions**

Create request/response types, `searchPdEcrHistory`, and `generatePdEcrReport`.

- [ ] **Step 2: Implement module helpers**

Create four module definitions, fallback history/generated data, response normalization, and generated result localStorage persistence.

- [ ] **Step 3: Run typecheck**

Run: `cd frontend; npm run build`
Expected: TypeScript should still fail until route components exist, but helper files should not introduce standalone type errors.

## Task 3: Build PD-ECR Routes And Components

**Files:**
- Create: `frontend/src/components/PdEcr/PdEcrPlatform.tsx`
- Create: `frontend/src/components/PdEcr/PdEcrContentBlocks.tsx`
- Create: `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`
- Create: `frontend/src/routes/_layout/pd-ecr.tsx`
- Create: `frontend/src/routes/_layout/pd-ecr.content.tsx`
- Create: `frontend/src/routes/_layout/pd-ecr.content.$moduleId.tsx`
- Modify: `frontend/src/components/Sidebar/AppSidebar.tsx`

- [ ] **Step 1: Implement `/pd-ecr` platform page**

Build the top historical-search area, four clickable historical modules, refer-to list, lower new-creation row, and AI generation button.

- [ ] **Step 2: Implement `/pd-ecr/content` page**

Build the four generated content blocks and navigation to module detail.

- [ ] **Step 3: Implement `/pd-ecr/content/$moduleId` page**

Read persisted generated modules and show the selected module's report content.

- [ ] **Step 4: Add sidebar link**

Add a `PD-ECR` item with a lucide icon to the authenticated sidebar.

## Task 4: Verify And Polish

**Files:**
- Verify all files created or modified above.

- [ ] **Step 1: Run Playwright PD-ECR test**

Run: `cd frontend; npx playwright test tests/pd-ecr.spec.ts --project=chromium`
Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend; npm run build`
Expected: PASS.

- [ ] **Step 3: Start dev server and visually verify**

Run: `cd frontend; npm run dev`
Open `/pd-ecr` and verify the first page matches the reference layout closely, the AI generation button navigates to the second page, and each module opens its detail view.
