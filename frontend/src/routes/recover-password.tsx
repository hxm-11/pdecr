import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/recover-password")({
  beforeLoad: async () => {
    throw redirect({ to: "/" })
  },
  component: () => null,
})
