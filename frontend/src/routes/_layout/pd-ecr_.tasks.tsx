import { createFileRoute } from "@tanstack/react-router"

import { PdEcrMyTasks } from "@/components/PdEcr/PdEcrMyTasks"

export const Route = createFileRoute("/_layout/pd-ecr_/tasks")({
  component: PdEcrMyTasks,
  head: () => ({
    meta: [{ title: "PD-ECR Workbench" }],
  }),
})
