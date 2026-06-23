import { createFileRoute } from "@tanstack/react-router"

import { PdEcrPlatform } from "@/components/PdEcr/PdEcrPlatform"

export const Route = createFileRoute("/_layout/pd-ecr")({
  component: PdEcrPlatform,
  head: () => ({
    meta: [
      {
        title: "PD-ECR Platform",
      },
    ],
  }),
})
