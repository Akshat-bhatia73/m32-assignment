import { CheckSquare, LogOut } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/layout/theme-toggle"
import { useCurrentUser, useLogout } from "@/hooks/use-auth"

export function AppHeader() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const navigate = useNavigate()

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-4">
      <div className="flex items-center gap-2">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <CheckSquare className="size-4" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-foreground">Meeting → Done</p>
          <p className="text-xs text-muted-foreground">Ops Copilot</p>
        </div>
      </div>

      <div className="flex items-center gap-1">
        {user?.name || user?.email ? (
          <span className="mr-1 hidden text-sm text-muted-foreground sm:inline">
            {user.name ?? user.email}
          </span>
        ) : null}
        <ThemeToggle />
        <Button
          variant="ghost"
          size="icon"
          aria-label="Sign out"
          disabled={logout.isPending}
          onClick={() => logout.mutate(undefined, { onSuccess: () => navigate("/login") })}
        >
          <LogOut className="size-4" />
        </Button>
      </div>
    </header>
  )
}
