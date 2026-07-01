import { createFileRoute } from "@tanstack/react-router"

import { PdEcrModuleDetail } from "@/components/PdEcr/PdEcrModuleDetail"

export const Route = createFileRoute("/_layout/pd-ecr_/content_/$moduleId")({
  component: ModuleDetailRoute,
  validateSearch: (search: Record<string, unknown>) => ({
    field: typeof search.field === "string" ? search.field : undefined,
    anchor: typeof search.anchor === "string" ? search.anchor : undefined,
    taskId: typeof search.taskId === "string" ? search.taskId : undefined,
  }),
  head: () => ({
    meta: [
      {
        title: "PD-ECR Module Detail",
      },
    ],
  }),
})

function ModuleDetailRoute() {
  const { moduleId } = Route.useParams()
  const { field, anchor, taskId } = Route.useSearch()

  return (
    <PdEcrModuleDetail
      moduleId={moduleId}
      targetField={field}
      targetAnchor={anchor}
      taskId={taskId}
    />
  )
}
