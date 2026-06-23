import { createFileRoute } from "@tanstack/react-router"

import { PdEcrContentBlocks } from "@/components/PdEcr/PdEcrContentBlocks"

export const Route = createFileRoute("/_layout/pd-ecr_/content")({
  component: PdEcrContentBlocks,
  head: () => ({
    meta: [
      {
        title: "PD-ECR Content Block",
      },
    ],
  }),
})
