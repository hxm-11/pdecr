import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import { PdEcrCaseList } from "@/components/PdEcr/PdEcrCaseList"

const searchSchema = z.object({
  view: z.enum(["all", "similar"]).catch("all"),
})

export const Route = createFileRoute("/_layout/pd-ecr_/cases")({
  validateSearch: searchSchema,
  component: PdEcrCasesRoute,
  head: () => ({
    meta: [
      {
        title: "ALL PD-ECR List",
      },
    ],
  }),
})

function PdEcrCasesRoute() {
  const { view } = Route.useSearch()
  return <PdEcrCaseList view={view} />
}
