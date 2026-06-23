### Task 7: Frontend creation workflow uses persisted editable AI generation

**Files:**
- Modify: `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`

**Interfaces:**
- Consumes:
  - `generatePdEcrEditableCase(input, similarCases)`
- Produces:
  - Generate button creates backend case and navigates to the editable case detail route.

- [ ] **Step 1: Replace local-only generation mutation**

Modify imports in `PdEcrCreationWorkflow.tsx`:

```ts
import {
  createPdEcrRequest,
  generatePdEcrEditableCase,
  type PdEcrInput,
  type PdEcrSimilarCase,
  retrievePdEcrSimilarCases,
} from "@/lib/pdEcrApi"
```

Update the mutation:

```ts
  const generateMutation = useMutation({
    mutationFn: async () => {
      const missing = missingRequiredFields(data)
      if (missing.length) {
        throw new Error(`Please fill required fields: ${missing.join(", ")}`)
      }
      const input = buildInput(data)
      const cases =
        similarCases.length > 0
          ? similarCases
          : (await retrievePdEcrSimilarCases(input, 5)).results
      setSimilarCases(cases)
      return generatePdEcrEditableCase(input, cases)
    },
    onSuccess: (response) => {
      setStatus("Generated an editable PD-ECR draft. Opening the case now.")
      navigate({
        to: "/pd-ecr/cases",
        search: { view: "all" },
      })
    },
    onError: (error) => {
      const result = buildGeneratedResult({ message: "fallback" })
      saveGeneratedResult(result)
      setStatus(
        error instanceof Error
          ? error.message
          : "Generation service unavailable. Fallback modules were prepared.",
      )
    },
  })
```

If a route exists for a single case detail page, use that route instead of the case list. If no route exists, navigating to the case list is acceptable for this task because the created case appears at the top by updated time.

- [ ] **Step 2: Update button copy**

Change the Generate button label:

```tsx
{generateMutation.isPending ? "Generating editable draft" : "Generate editable draft"}
```

- [ ] **Step 3: Build frontend**

Run:

```powershell
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```bash
git add frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx
git commit -m "feat: create editable pd-ecr draft from ai workflow"
```

---

