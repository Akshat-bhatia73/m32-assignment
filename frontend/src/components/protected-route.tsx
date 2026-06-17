import { Navigate, Outlet } from "react-router-dom"

import { useCurrentUser } from "@/hooks/use-auth"
import { Spinner } from "@/components/ui/spinner"

export function ProtectedRoute() {
  const { data: user, isLoading } = useCurrentUser()

  if (isLoading) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Spinner className="size-6 text-muted-foreground" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}
