import { CheckSquare, LayoutGrid, LogOut, MoreHorizontal, Plus, Trash2 } from "lucide-react"
import { NavLink, useNavigate } from "react-router-dom"

import { ThemeToggle } from "@/components/layout/theme-toggle"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { IconButton } from "@/components/ui/icon-button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useCurrentUser, useLogout } from "@/hooks/use-auth"
import { cn } from "@/lib/utils"
import type { Session } from "@/lib/types"

function relativeDay(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  const now = new Date()
  const startOfDay = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const days = Math.round((startOfDay(now) - startOfDay(d)) / 86_400_000)
  if (days <= 0) return "Today"
  if (days === 1) return "Yesterday"
  if (days < 7) return `${days} days ago`
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export function SessionSidebar({
  sessions,
  currentId,
  onSelect,
  onNew,
  onDelete,
  className,
}: {
  sessions: Session[]
  currentId: string | undefined
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  className?: string
}) {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const navigate = useNavigate()
  const label = user?.name || user?.email || ""

  return (
    <div className={cn("flex h-full flex-col bg-sidebar text-sidebar-foreground", className)}>
      {/* Brand — replaces the old global top bar. */}
      <div className="flex h-[3.75rem] shrink-0 items-center gap-2 border-b border-sidebar-border px-4">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <CheckSquare className="size-4" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-foreground">Meeting → Done</p>
          <p className="text-xs text-muted-foreground">Ops Copilot</p>
        </div>
      </div>

      <div className="shrink-0 p-3">
        <Button className="w-full justify-center gap-2" onClick={onNew}>
          <Plus className="size-4" />
          New meeting
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2">
        <p className="px-2 pb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Meetings
        </p>
        {sessions.length === 0 ? (
          <p className="px-2 py-2 text-sm text-muted-foreground">No meetings yet.</p>
        ) : (
          <ul className="flex flex-col gap-0.5 pb-2">
            {sessions.map((s) => {
              const active = s.id === currentId
              return (
                <li key={s.id}>
                  <div
                    className={cn(
                      "group flex items-center rounded-lg pr-1 transition-colors",
                      active ? "bg-sidebar-accent" : "hover:bg-sidebar-accent/60"
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => onSelect(s.id)}
                      className="flex min-w-0 flex-1 flex-col items-start gap-0.5 px-2.5 py-2 text-left"
                    >
                      <span
                        className={cn(
                          "w-full truncate text-sm",
                          active ? "font-medium text-foreground" : "text-foreground/80"
                        )}
                      >
                        {s.title || "Untitled"}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {relativeDay(s.created_at)}
                      </span>
                    </button>
                    <DropdownMenu>
                      <Tooltip>
                        <TooltipTrigger
                          render={
                            <DropdownMenuTrigger
                              render={
                                <Button
                                  variant="ghost"
                                  size="icon-sm"
                                  aria-label="Meeting options"
                                  className="shrink-0 rounded-full text-muted-foreground opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100"
                                >
                                  <MoreHorizontal className="size-4" />
                                </Button>
                              }
                            />
                          }
                        />
                        <TooltipContent>Meeting options</TooltipContent>
                      </Tooltip>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem variant="destructive" onClick={() => onDelete(s.id)}>
                          <Trash2 className="size-4" />
                          Delete meeting
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="shrink-0 space-y-1 border-t border-sidebar-border p-2">
        <NavLink
          to="/overview"
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors",
              isActive
                ? "bg-sidebar-accent font-medium text-foreground"
                : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
            )
          }
        >
          <LayoutGrid className="size-4" />
          All action items
        </NavLink>

        <div className="flex items-center gap-2 rounded-lg px-2.5 py-1.5">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium uppercase text-muted-foreground">
            {label.charAt(0) || "?"}
          </div>
          <span className="min-w-0 flex-1 truncate text-sm text-foreground">{label}</span>
          <ThemeToggle />
          <IconButton
            tooltip="Sign out"
            variant="ghost"
            size="icon-sm"
            disabled={logout.isPending}
            onClick={() => logout.mutate(undefined, { onSuccess: () => navigate("/login") })}
          >
            <LogOut className="size-4" />
          </IconButton>
        </div>
      </div>
    </div>
  )
}
