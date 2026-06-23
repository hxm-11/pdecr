import { createFileRoute } from "@tanstack/react-router"

import { PdEcrCreationWorkflow } from "@/components/PdEcr/PdEcrCreationWorkflow"

export const Route = createFileRoute("/_layout/pd-ecr_/new")({
  component: PdEcrCreationWorkflow,
  head: () => ({
    meta: [
      {
        title: "PD-ECR New Creation",
      },
    ],
  }),
})
