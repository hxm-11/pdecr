import { createFileRoute } from "@tanstack/react-router"
import { Building2, KeyRound, LogIn, ShieldCheck, UserRound } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { AuthLayout } from "@/components/Common/AuthLayout"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/login")({
  component: LoginPage,
})

const seededPassword = "PdecrPeople123!"
const defaultAutoLoginEmail = "design.engineer@example.com"
const shouldAutoLogin =
  import.meta.env.DEV && import.meta.env.VITE_AUTO_LOGIN === "true"

const peopleAccounts = [
  {
    email: "pdecr.manager@example.com",
    name: "PD-ECR Manager",
    department: "PM",
    role: "Full access",
  },
  {
    email: "design.leader@example.com",
    name: "Design Leader",
    department: "Design",
    role: "Department leader",
  },
  {
    email: "design.engineer@example.com",
    name: "Design Engineer",
    department: "Design",
    role: "Department member",
  },
  {
    email: "quality.leader@example.com",
    name: "Quality Leader",
    department: "Quality",
    role: "Department leader",
  },
  {
    email: "quality.engineer@example.com",
    name: "Quality Engineer",
    department: "Quality",
    role: "Department member",
  },
  {
    email: "pdecr.reviewer@example.com",
    name: "Reviewer",
    department: "Quality",
    role: "Reviewer",
  },
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
  const autoLoginAttemptedRef = useRef(false)
  const [email, setEmail] = useState(
    import.meta.env.VITE_AUTO_LOGIN_EMAIL || defaultAutoLoginEmail,
  )
  const [password, setPassword] = useState(
    import.meta.env.VITE_AUTO_LOGIN_PASSWORD || seededPassword,
  )

  useEffect(() => {
    if (!shouldAutoLogin || autoLoginAttemptedRef.current || isLoggedIn()) return

    autoLoginAttemptedRef.current = true
    loginMutation.mutate({
      username: email.trim(),
      password,
      grant_type: "password",
      scope: "",
      client_id: null,
      client_secret: null,
    })
  }, [email, loginMutation, password])

  const selectAccount = (account: (typeof peopleAccounts)[number]) => {
    setEmail(account.email)
    setPassword(seededPassword)
  }

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
      <form className="space-y-6" onSubmit={submit}>
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-md bg-blue-50 text-blue-700 ring-1 ring-blue-100">
              <KeyRound className="size-5" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">
                BOSCH PD-ECR
              </p>
              <h1 className="text-2xl font-semibold text-slate-950">
                Sign in
              </h1>
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-600">
            Select a seeded people account or enter another user to continue.
          </p>
        </div>

        <div className="space-y-2.5">
          <Label htmlFor="email" className="text-slate-700">
            Email
          </Label>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            className="h-11 bg-white"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>

        <div className="space-y-2.5">
          <Label htmlFor="password" className="text-slate-700">
            Password
          </Label>
          <PasswordInput
            id="password"
            autoComplete="current-password"
            className="h-11 bg-white"
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
          className="h-11 w-full bg-blue-700 text-white hover:bg-blue-800"
          disabled={loginMutation.isPending || !email.trim() || !password}
        >
          <LogIn className="size-4" />
          {loginMutation.isPending ? "Signing in..." : "Sign in"}
        </Button>

        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <ShieldCheck className="size-4 text-blue-700" />
              Seeded people accounts
            </div>
            <span className="rounded bg-white px-2 py-1 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">
              {peopleAccounts.length} users
            </span>
          </div>
          <div className="mt-3 grid gap-2">
            {peopleAccounts.map((account) => (
              <button
                key={account.email}
                type="button"
                className="group flex w-full items-center gap-3 rounded-md border border-slate-200 bg-white px-3 py-2 text-left transition hover:border-blue-200 hover:bg-blue-50"
                onClick={() => selectAccount(account)}
              >
                <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-600 group-hover:bg-white group-hover:text-blue-700">
                  <UserRound className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-slate-900">
                    {account.name}
                  </span>
                  <span className="mt-0.5 flex min-w-0 items-center gap-1.5 text-xs text-slate-500">
                    <Building2 className="size-3.5 shrink-0" />
                    <span className="truncate">
                      {account.department} · {account.role}
                    </span>
                  </span>
                </span>
              </button>
            ))}
          </div>
          <p className="mt-3 rounded border border-dashed border-slate-300 bg-white px-3 py-2 text-xs text-slate-600">
            Shared seed password: <span className="font-mono">{seededPassword}</span>
          </p>
        </div>
      </form>
    </AuthLayout>
  )
}
