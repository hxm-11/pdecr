import { createFileRoute } from "@tanstack/react-router"

import { PdEcrDocumentReview } from "@/components/PdEcr/PdEcrDocumentReview"

export const Route = createFileRoute("/_layout/pd-ecr_/documents/$docId")({
  component: PdEcrDocumentReview,
  head: () => ({
    meta: [{ title: "PD-ECR Document Review" }],
  }),
})
