import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/signup")({
  beforeLoad: async () => {
    throw redirect({ to: "/" })
  },
  component: () => null,
})
