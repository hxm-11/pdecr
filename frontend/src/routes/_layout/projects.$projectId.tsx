import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/projects/$projectId")({
  beforeLoad: () => {
    throw redirect({ to: "/pd-ecr/dashboard" })
  },
})
