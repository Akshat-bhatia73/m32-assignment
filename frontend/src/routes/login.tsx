import { type FormEvent, useState } from "react"
import { Link, Navigate, useNavigate } from "react-router-dom"

import { AuthShell } from "@/components/auth/auth-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { useCurrentUser, useLogin } from "@/hooks/use-auth"
import { ApiError } from "@/lib/api"

export function LoginPage() {
  const { data: user, isLoading } = useCurrentUser()
  const login = useLogin()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)

  if (!isLoading && user) return <Navigate to="/" replace />

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    login.mutate(
      { email, password },
      {
        onSuccess: () => navigate("/"),
        onError: (err) =>
          setError(err instanceof ApiError ? err.message : "Something went wrong"),
      }
    )
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your Ops Copilot"
      footer={
        <>
          New here?{" "}
          <Link to="/signup" className="font-medium text-foreground underline-offset-4 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4 rounded-xl border border-border bg-card p-6">
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Button type="submit" disabled={login.isPending} className="mt-1">
          {login.isPending ? <Spinner className="size-4" /> : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  )
}
