import { createFileRoute } from "@tanstack/react-router";

import { PdEcrHistoryCase } from "@/components/PdEcr/PdEcrHistoryCase";

export const Route = createFileRoute("/_layout/pd-ecr_/history-case")({
  component: PdEcrHistoryCase,
  head: () => ({
    meta: [{ title: "PD-ECR History Case" }],
  }),
});
