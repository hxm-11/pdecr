import { createFileRoute } from "@tanstack/react-router"

import { PdEcrCaseDashboard } from "@/components/PdEcr/PdEcrCaseDashboard"

export const Route = createFileRoute("/_layout/pd-ecr_/dashboard")({
  component: PdEcrCaseDashboard,
  head: () => ({
    meta: [{ title: "PD-ECR Case Dashboard" }],
  }),
})
