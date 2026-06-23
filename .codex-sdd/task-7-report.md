### Task 7 Report: Frontend creation workflow uses persisted editable AI generation

**Files changed**
- `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`

**Implementation notes**
- Replaced the creation workflow generation call from `generatePdEcrDraft` to `generatePdEcrEditableCase`.
- On successful persisted generation, the workflow no longer saves the generated draft to localStorage as the source of truth.
- Success status now includes the created case number/DC number/id when available, then navigates to `/pd-ecr/cases?view=all`.
- Existing fallback behavior remains: generation errors still prepare and save fallback modules locally.
- Updated the Generate button copy to `Generate editable draft` / `Generating editable draft`.

**Verification**
- Red check before edit:
  - Command: static assertion for `generatePdEcrEditableCase`, `Generate editable draft`, and `Generating editable draft` in `PdEcrCreationWorkflow.tsx`
  - Result: failed as expected because the old local draft flow was still present.
- Green check after edit:
  - Command: same static assertion
  - Result: `creation workflow static assertions passed`
- Build:
  - Command: `npm run build` from `frontend`
  - Result: PASS, exit code 0.
  - Output summary:
    - `tsc -p tsconfig.build.json && vite build`
    - `✓ 2479 modules transformed.`
    - `✓ built in 3.67s`
  - Warnings observed:
    - npm unknown global config `always-auth`
    - Node `[DEP0205] DeprecationWarning: module.register() is deprecated`
    - Vite chunk-size warning for chunks larger than 500 kB
