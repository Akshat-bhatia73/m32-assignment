import { type FormEvent, useState } from "react"
import { Link, Navigate, useNavigate } from "react-router-dom"

import { AuthShell } from "@/components/auth/auth-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { useCurrentUser, useSignup } from "@/hooks/use-auth"
import { ApiError } from "@/lib/api"

export function SignupPage() {
  const { data: user, isLoading } = useCurrentUser()
  const signup = useSignup()
  const navigate = useNavigate()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)

  if (!isLoading && user) return <Navigate to="/" replace />

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    signup.mutate(
      { name: name || undefined, email, password },
      {
        onSuccess: () => navigate("/"),
        onError: (err) =>
          setError(err instanceof ApiError ? err.message : "Something went wrong"),
      }
    )
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Turn meetings into done, in minutes"
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4 rounded-xl border border-border bg-card p-6">
        <div className="flex flex-col gap-2">
          <Label htmlFor="name">Name</Label>
          <Input
            id="name"
            autoComplete="name"
            placeholder="Optional"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
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
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">At least 8 characters.</p>
        </div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Button type="submit" disabled={signup.isPending} className="mt-1">
          {signup.isPending ? <Spinner className="size-4" /> : "Create account"}
        </Button>
      </form>
    </AuthShell>
  )
}
