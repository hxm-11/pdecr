import { createFileRoute } from "@tanstack/react-router"

import { PdEcrModuleDetail } from "@/components/PdEcr/PdEcrModuleDetail"

export const Route = createFileRoute("/_layout/pd-ecr_/content_/$moduleId")({
  component: ModuleDetailRoute,
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

  return <PdEcrModuleDetail moduleId={moduleId} />
}
