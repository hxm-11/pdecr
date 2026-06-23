import type {
  PdEcrDbModule,
  PdEcrGeneratedCaseResponse,
  PdEcrGeneratedModulePreview,
  PdEcrModuleAssignmentPayload,
  PdEcrPermissionFlags,
} from "../frontend/src/lib/pdEcrApi"
import {
  applyGeneratedPdEcrModule,
  assignPdEcrModule,
  generatePdEcrEditableCase,
  regeneratePdEcrModule,
  sendPdEcrModuleReminder,
} from "../frontend/src/lib/pdEcrApi"

const permissions: PdEcrPermissionFlags = {
  can_edit: true,
  can_assign: true,
  can_regenerate: true,
  can_send_reminder: true,
  can_review: false,
  can_close: false,
}

const module: PdEcrDbModule = {
  id: "module-row-1",
  case_id: "case-1",
  module_id: "impact_analysis",
  version: 2,
  assignee_id: "user-1",
  assignee_email: "owner@example.com",
  assignee_name: "Module Owner",
  department: "Engineering",
  due_date: "2026-06-30",
  reminder_policy: { cadence: "weekly" },
  last_reminded_at: null,
  permissions,
}

const generatedCase: PdEcrGeneratedCaseResponse = {
  case: {
    id: "case-1",
    case_no: "PD-ECR-1",
    status: "draft",
  },
  modules: [module],
  draft_id: "draft-1",
  draft_status: "V1_MVP_DRAFT",
  warnings: [],
  redirect_to: "/pd-ecr/cases/case-1",
}

const generatedModule: PdEcrGeneratedModulePreview = {
  case_id: generatedCase.case.id,
  module_id: module.module_id,
  title: module.title,
  content_md: "Generated content",
  content_json: { section: "impact" },
  source_cases: ["case-0"],
  source_files: ["case-0.md"],
  needs_human_input: false,
}

const assignment: PdEcrModuleAssignmentPayload = {
  assignee_email: "owner@example.com",
  due_date: "2026-06-30",
  reminder_policy: { cadence: "weekly" },
  send_assignment_email: true,
}

async function exerciseApiSurface() {
  await generatePdEcrEditableCase({ dc_no: "DC-1" }, [])
  await regeneratePdEcrModule(
    generatedModule.case_id,
    generatedModule.module_id,
    "shorter",
  )
  await applyGeneratedPdEcrModule(
    generatedModule.case_id,
    generatedModule.module_id,
    generatedModule,
    module.version,
  )
  await assignPdEcrModule(module.case_id, module.module_id, assignment)
  await sendPdEcrModuleReminder(module.case_id, module.module_id)
}

void exerciseApiSurface
