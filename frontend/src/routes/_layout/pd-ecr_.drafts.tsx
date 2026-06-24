import { createFileRoute } from "@tanstack/react-router"

import { PdEcrDraftList } from "@/components/PdEcr/PdEcrDraftList"

export const Route = createFileRoute("/_layout/pd-ecr_/drafts")({
  component: PdEcrDraftList,
  head: () => ({
    meta: [{ title: "PD-ECR Draft Box" }],
  }),
})
