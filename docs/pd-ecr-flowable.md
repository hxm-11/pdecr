# PD-ECR Flowable Integration

This document describes the minimal Flowable contract used by the PD-ECR manager approval flow.

For non-Docker company-server deployment, see `docs/pd-ecr-flowable-standalone.md`.

The current integration covers the first approval gate:

```text
submit PD-ECR case -> manager approval task -> approved or rejected end
```

The BPMN file lives at:

```text
backend/app/integrations/flowable/processes/pd_ecr_manager_approval.bpmn20.xml
```

## Runtime Configuration

Set these variables in the backend environment when you want Flowable to own approval orchestration:

```env
FLOWABLE_ENABLED=true
FLOWABLE_BASE_URL=http://localhost:8081/flowable-rest/service
FLOWABLE_USERNAME=rest-admin
FLOWABLE_PASSWORD=test
FLOWABLE_PROCESS_DEFINITION_KEY=pd_ecr_manager_approval
FLOWABLE_TIMEOUT_SECONDS=10
```

For the local Docker Compose setup, `compose.override.yml` exposes Flowable on host port `8081` because `8080` is already used by Adminer. Inside Docker, the backend uses `http://flowable:8080/flowable-rest/service`.

When `FLOWABLE_ENABLED=false`, the backend keeps the existing local approval behavior. This is useful for local development and tests that do not run a Flowable server.

## Deploy The BPMN

Deploy the BPMN to Flowable before submitting approval cases:

```powershell
.\scripts\deploy-flowable-bpmn.ps1
```

Or deploy it manually:

```powershell
curl.exe -u rest-admin:test `
  -F "deploymentKey=pd_ecr_manager_approval" `
  -F "file=@backend/app/integrations/flowable/processes/pd_ecr_manager_approval.bpmn20.xml" `
  http://localhost:8081/flowable-rest/service/repository/deployments
```

If your Flowable URL is different, keep `FLOWABLE_BASE_URL` pointed at the REST service root, usually ending in `/flowable-rest/service`.

## Process Variables

The backend sends these variables when it starts the process:

| Variable | Direction | Meaning |
|---|---|---|
| `caseId` | Backend -> Flowable | Local `PdEcrCase.id`; also used as the Flowable business key. |
| `caseNo` | Backend -> Flowable | Human-readable PD-ECR case number. |
| `title` | Backend -> Flowable | Case title shown to approvers. |
| `initiator` | Backend -> Flowable | Initiator display name or email. |
| `customerProject` | Backend -> Flowable | Customer/project field from the PD-ECR request. |
| `productNo` | Backend -> Flowable | Product number from the PD-ECR request. |
| `partNo` | Backend -> Flowable | Part/component number from the PD-ECR request. |
| `approverId` | Backend -> Flowable | Local user id when the approver maps to a local user. |
| `approverEmail` | Backend -> Flowable | Flowable assignee for `managerApprovalTask`. |
| `approverName` | Backend -> Flowable | Approver display name. |
| `formDataJson` | Backend -> Flowable | Original submitted form data as JSON text. |
| `approved` | Backend -> Flowable | Boolean written when completing the manager task. |
| `approvedBy` | Backend -> Flowable | Display name of the user who completed the task. |
| `approvedByEmail` | Backend -> Flowable | Email of the user who completed the task. |
| `rejectionReason` | Backend -> Flowable | Rejection reason when `approved=false`. |

## Backend Endpoints

The existing PD-ECR endpoints drive the Flowable process when the switch is enabled:

```text
POST /api/v1/pd-ecr/cases/submit-for-approval
POST /api/v1/pd-ecr/cases/{case_id}/manager-approve
POST /api/v1/pd-ecr/cases/{case_id}/manager-reject
GET  /api/v1/pd-ecr/workflow/my-tasks
```

The backend stores Flowable runtime identifiers on the local case and approval task:

```text
PdEcrCase.flowable_process_instance_id
PdEcrCase.flowable_process_definition_key
PdEcrCase.flowable_business_key
PdEcrCase.flowable_status
PdEcrApprovalTask.flowable_task_id
PdEcrApprovalTask.flowable_task_definition_key
```

This keeps PD-ECR business content in the application database while Flowable owns the active approval task.
