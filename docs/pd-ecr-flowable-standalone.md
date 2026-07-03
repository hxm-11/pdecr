# PD-ECR Flowable Standalone Deployment

This guide is for running Flowable without Docker. The PD-ECR backend only needs
the Flowable REST service URL, so Flowable can run on a developer laptop, a VM,
or a company server.

## Target Architecture

```text
Browser -> PD-ECR frontend -> FastAPI backend -> Flowable REST
                                      |
                                      -> PD-ECR database
```

Flowable owns the active manager approval task. PD-ECR still owns case content,
module data, permissions, activity history, and UI rendering.

## Server Requirements

- Java runtime compatible with the Flowable version you deploy
- A reachable HTTP port, for example `8080`
- A Flowable database for production use, preferably PostgreSQL or MySQL
- A service account for the PD-ECR backend, for example `rest-admin`

For local proof-of-concept use, Flowable's bundled database is acceptable. For
company deployment, use a persistent database and keep Flowable's database
separate from the PD-ECR application database.

## Flowable REST URL

The backend expects a REST root URL ending with:

```text
/flowable-rest/service
```

Examples:

```text
http://localhost:8080/flowable-rest/service
http://flowable.company.local:8080/flowable-rest/service
https://flowable.company.local/flowable-rest/service
```

## PD-ECR Backend Configuration

Copy the values from `.env.flowable-standalone.example` into `.env` and adjust
the host, username, and password:

```env
FLOWABLE_ENABLED=true
FLOWABLE_BASE_URL=http://flowable.company.local:8080/flowable-rest/service
FLOWABLE_USERNAME=rest-admin
FLOWABLE_PASSWORD=change-me
FLOWABLE_PROCESS_DEFINITION_KEY=pd_ecr_manager_approval
FLOWABLE_TIMEOUT_SECONDS=10
```

Restart the FastAPI backend after changing these values.

## Deploy The PD-ECR BPMN

Deploy the bundled manager approval process:

```powershell
.\scripts\deploy-flowable-bpmn.ps1 `
  -BaseUrl "http://flowable.company.local:8080/flowable-rest/service" `
  -Username "rest-admin" `
  -Password "change-me"
```

The BPMN file is:

```text
backend/app/integrations/flowable/processes/pd_ecr_manager_approval.bpmn20.xml
```

The process definition key must stay aligned with:

```env
FLOWABLE_PROCESS_DEFINITION_KEY=pd_ecr_manager_approval
```

## Check The Integration

Check that the backend can reach Flowable and that the process definition is
deployed:

```powershell
.\scripts\check-flowable.ps1 `
  -BaseUrl "http://flowable.company.local:8080/flowable-rest/service" `
  -Username "rest-admin" `
  -Password "change-me"
```

Then create or submit a PD-ECR case for manager approval. The local database
should receive these values:

```text
pd_ecr_case.flowable_process_instance_id
pd_ecr_case.flowable_status
pd_ecr_approval_task.flowable_task_id
```

If those values are empty, the backend is still using local approval only or the
Flowable process failed to start.

## Production Notes

- Do not expose Flowable REST directly to end users unless your company has
  authentication, TLS, and firewall rules in place.
- Let only the FastAPI backend call Flowable REST.
- Replace the default `rest-admin/test` credentials before company deployment.
- Use HTTPS or an internal trusted network route for company servers.
- Back up the Flowable database together with the PD-ECR application database.
- Keep Flowable service logs because they are useful for process troubleshooting.

## What Is Covered Today

Current PD-ECR integration covers the first approval gate:

```text
submit PD-ECR case -> manager approval task -> approved or rejected end
```

Department confirmation, execution assignment, execution tasks, and leader
review still run in the PD-ECR application workflow tables.
