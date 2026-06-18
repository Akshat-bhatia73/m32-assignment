import { CheckSquare, LogOut } from "lucide-react"
import { NavLink, useNavigate } from "react-router-dom"

import { IconButton } from "@/components/ui/icon-button"
import { ThemeToggle } from "@/components/layout/theme-toggle"
import { useCurrentUser, useLogout } from "@/hooks/use-auth"
import { cn } from "@/lib/utils"

const NAV = [
  { to: "/", label: "Workspace", end: true },
  { to: "/overview", label: "All items", end: false },
]

export function AppHeader() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const navigate = useNavigate()

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-4">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <CheckSquare className="size-4" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold text-foreground">Meeting → Done</p>
            <p className="text-xs text-muted-foreground">Ops Copilot</p>
          </div>
        </div>
        <nav className="hidden items-center gap-1 sm:flex">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-1.5 text-sm transition-colors",
                  isActive
                    ? "bg-secondary font-medium text-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="flex items-center gap-1">
        {user?.name || user?.email ? (
          <span className="mr-1 hidden text-sm text-muted-foreground sm:inline">
            {user.name ?? user.email}
          </span>
        ) : null}
        <ThemeToggle />
        <IconButton
          tooltip="Sign out"
          tooltipSide="bottom"
          variant="ghost"
          disabled={logout.isPending}
          onClick={() => logout.mutate(undefined, { onSuccess: () => navigate("/login") })}
        >
          <LogOut className="size-4" />
        </IconButton>
      </div>
    </header>
  )
}
