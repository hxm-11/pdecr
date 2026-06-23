### Task 8: Frontend module detail supports assignment, reminders, and regeneration preview

**Files:**
- Modify: `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`

**Interfaces:**
- Consumes:
  - `PdEcrDbModule.permissions`
  - `regeneratePdEcrModule`
  - `applyGeneratedPdEcrModule`
  - `assignPdEcrModule`
  - `sendPdEcrModuleReminder`
- Produces:
  - Assignment panel
  - Reminder button
  - Regenerate preview/apply/discard UI

- [ ] **Step 1: Add API imports**

In `PdEcrModuleDetail.tsx`, extend imports from `@/lib/pdEcrApi`:

```ts
import {
  applyGeneratedPdEcrModule,
  assignPdEcrModule,
  getPdEcrModuleDraft,
  regeneratePdEcrModule,
  savePdEcrModuleDraft,
  sendPdEcrModuleReminder,
  type PdEcrGeneratedModulePreview,
} from "@/lib/pdEcrApi"
```

- [ ] **Step 2: Add component state**

Near existing module state:

```ts
  const [assignmentEmail, setAssignmentEmail] = useState(module.assignee_email || "")
  const [assignmentName, setAssignmentName] = useState(module.assignee_name || "")
  const [assignmentDepartment, setAssignmentDepartment] = useState(module.department || "")
  const [assignmentDueDate, setAssignmentDueDate] = useState(
    module.due_date ? module.due_date.slice(0, 10) : "",
  )
  const [regenerateInstruction, setRegenerateInstruction] = useState("")
  const [generatedPreview, setGeneratedPreview] =
    useState<PdEcrGeneratedModulePreview | null>(null)
  const [actionStatus, setActionStatus] = useState("")
```

- [ ] **Step 3: Add handlers**

Add these handlers in the component:

```ts
  const caseId = module.case_id
  const canAssign = Boolean(module.permissions?.can_assign)
  const canRegenerate = Boolean(module.permissions?.can_regenerate)
  const canSendReminder = Boolean(module.permissions?.can_send_reminder)

  const handleAssignModule = async () => {
    if (!caseId || !module.id) return
    const response = await assignPdEcrModule(caseId, module.id, {
      assignee_email: assignmentEmail || null,
      assignee_name: assignmentName || null,
      department: assignmentDepartment || null,
      due_date: assignmentDueDate || null,
      reminder_policy: { on_assignment: true, overdue: true },
      send_assignment_email: true,
    })
    setActionStatus(
      response.notification
        ? "Assignment saved and reminder email was queued."
        : "Assignment saved.",
    )
  }

  const handleRegenerate = async () => {
    if (!caseId || !module.id) return
    const preview = await regeneratePdEcrModule(
      caseId,
      module.id,
      regenerateInstruction,
    )
    setGeneratedPreview(preview)
    setActionStatus("Generated preview is ready. Review before applying.")
  }

  const handleApplyGenerated = async () => {
    if (!caseId || !module.id || !generatedPreview) return
    await applyGeneratedPdEcrModule(
      caseId,
      module.id,
      generatedPreview,
      module.version,
    )
    setActionStatus("Generated module content applied. Refresh the module to see the latest version.")
    setGeneratedPreview(null)
  }

  const handleSendReminder = async () => {
    if (!caseId || !module.id) return
    await sendPdEcrModuleReminder(caseId, module.id)
    setActionStatus("Reminder email was sent or recorded.")
  }
```

If `module.id` is a database UUID and `module.module_id` is the business module ID, pass `module.module_id` to backend module endpoints. Use:

```ts
  const moduleRouteId = module.module_id || module.id
```

and replace `module.id` in endpoint calls with `moduleRouteId`.

- [ ] **Step 4: Add assignment and regeneration UI**

Add this block above the source references section:

```tsx
<section className="rounded-lg border border-stone-200 bg-white p-4">
  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
    <div>
      <h3 className="text-sm font-semibold text-stone-900">
        Module owner and reminder
      </h3>
      <p className="mt-1 text-sm text-stone-500">
        Assign the responsible person and send email reminders when this module needs action.
      </p>
    </div>
    {canSendReminder ? (
      <Button type="button" variant="outline" onClick={handleSendReminder}>
        Send reminder
      </Button>
    ) : null}
  </div>

  <div className="mt-4 grid gap-3 md:grid-cols-2">
    <Input
      value={assignmentEmail}
      onChange={(event) => setAssignmentEmail(event.target.value)}
      disabled={!canAssign}
      placeholder="Responsible email"
    />
    <Input
      value={assignmentName}
      onChange={(event) => setAssignmentName(event.target.value)}
      disabled={!canAssign}
      placeholder="Responsible name"
    />
    <Input
      value={assignmentDepartment}
      onChange={(event) => setAssignmentDepartment(event.target.value)}
      disabled={!canAssign}
      placeholder="Department"
    />
    <Input
      type="date"
      value={assignmentDueDate}
      onChange={(event) => setAssignmentDueDate(event.target.value)}
      disabled={!canAssign}
    />
  </div>

  {canAssign ? (
    <Button type="button" className="mt-3" onClick={handleAssignModule}>
      Save assignment
    </Button>
  ) : null}
</section>

<section className="rounded-lg border border-stone-200 bg-white p-4">
  <h3 className="text-sm font-semibold text-stone-900">
    Regenerate this module
  </h3>
  <textarea
    value={regenerateInstruction}
    onChange={(event) => setRegenerateInstruction(event.target.value)}
    disabled={!canRegenerate}
    className="mt-3 min-h-24 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
    placeholder="Optional instruction, for example: focus on manufacturing impact."
  />
  {canRegenerate ? (
    <Button type="button" className="mt-3" onClick={handleRegenerate}>
      Regenerate preview
    </Button>
  ) : null}

  {generatedPreview ? (
    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
      <p className="text-sm font-semibold text-amber-900">Preview</p>
      <pre className="mt-2 whitespace-pre-wrap text-sm text-stone-800">
        {generatedPreview.content_md}
      </pre>
      <div className="mt-3 flex gap-2">
        <Button type="button" onClick={handleApplyGenerated}>
          Apply preview
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => setGeneratedPreview(null)}
        >
          Discard
        </Button>
      </div>
    </div>
  ) : null}
</section>

{actionStatus ? (
  <p className="rounded-lg bg-stone-50 px-3 py-2 text-sm text-stone-700">
    {actionStatus}
  </p>
) : null}
```

- [ ] **Step 5: Build frontend**

Run:

```powershell
cd frontend
npm run build
```

Expected: PASS. If the module detail component uses `module.id` differently, change the route parameter to `module.module_id || module.id` and rebuild.

- [ ] **Step 6: Commit**

Run:

```bash
git add frontend/src/components/PdEcr/PdEcrModuleDetail.tsx
git commit -m "feat: add pd-ecr module assignment and regeneration ui"
```

---

