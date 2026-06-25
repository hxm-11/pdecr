import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/reset-password")({
  beforeLoad: async () => {
    throw redirect({ to: "/" })
  },
  component: () => null,
})
