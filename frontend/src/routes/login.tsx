import { createFileRoute } from "@tanstack/react-router"
import { KeyRound, LogIn } from "lucide-react"
import { useState } from "react"

import { AuthLayout } from "@/components/Common/AuthLayout"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/login")({
  component: LoginPage,
})

const validationUsers = [
  "manager-validation@example.com",
  "assignee-validation@example.com",
  "leader-validation@example.com",
]

function loginErrorMessage(error: unknown) {
  if (!error || typeof error !== "object") return "Login failed"
  const record = error as {
    message?: string
    response?: { data?: unknown; status?: number }
  }
  const detail =
    record.response?.data && typeof record.response.data === "object"
      ? (record.response.data as { detail?: unknown }).detail
      : undefined
  if (typeof detail === "string") return detail
  return record.message || "Login failed"
}

function LoginPage() {
  const { loginMutation } = useAuth()
  const [email, setEmail] = useState("assignee-validation@example.com")
  const [password, setPassword] = useState("PdecrValidation123!")

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    loginMutation.mutate({
      username: email.trim(),
      password,
      grant_type: "password",
      scope: "",
      client_id: null,
      client_secret: null,
    })
  }

  return (
    <AuthLayout>
      <form className="space-y-5" onSubmit={submit}>
        <div className="space-y-2">
          <div className="flex size-10 items-center justify-center rounded-md bg-amber-100 text-amber-700">
            <KeyRound className="size-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Sign in</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Use one validation account to test the PD-ECR workflow.
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <PasswordInput
            id="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>

        {loginMutation.error ? (
          <Alert variant="destructive">
            <AlertTitle>Login failed</AlertTitle>
            <AlertDescription>
              {loginErrorMessage(loginMutation.error)}
            </AlertDescription>
          </Alert>
        ) : null}

        <Button
          type="submit"
          className="w-full"
          disabled={loginMutation.isPending || !email.trim() || !password}
        >
          <LogIn className="size-4" />
          {loginMutation.isPending ? "Signing in..." : "Sign in"}
        </Button>

        <div className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">Validation users</p>
          <div className="mt-2 space-y-1">
            {validationUsers.map((user) => (
              <button
                key={user}
                type="button"
                className="block w-full rounded px-2 py-1 text-left hover:bg-background"
                onClick={() => setEmail(user)}
              >
                {user}
              </button>
            ))}
          </div>
          <p className="mt-2">Password: PdecrValidation123!</p>
        </div>
      </form>
    </AuthLayout>
  )
}
