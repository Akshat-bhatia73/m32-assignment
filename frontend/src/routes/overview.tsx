import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, ArrowRight, CalendarDays, ClipboardList, User } from "lucide-react"
import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"

import { StatusBadge } from "@/components/board/status-badge"
import { ThemeToggle } from "@/components/layout/theme-toggle"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { api } from "@/lib/api"
import type { ActionItemWithSession, ActionStatus } from "@/lib/types"
import { cn } from "@/lib/utils"

type Filter = "all" | ActionStatus
const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "scheduled", label: "Scheduled" },
  { key: "sent", label: "Sent" },
  { key: "done", label: "Done" },
]

function formatDue(due: string | null): string | null {
  if (!due) return null
  const d = new Date(`${due}T00:00:00`)
  if (Number.isNaN(d.getTime())) return due
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export function OverviewPage() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Filter>("all")

  const actionsQuery = useQuery({
    queryKey: ["all-actions"],
    queryFn: () => api.getAllActions(),
  })
  const items = actionsQuery.data

  const counts = useMemo(() => {
    const base: Record<Filter, number> = { all: 0, open: 0, scheduled: 0, sent: 0, done: 0 }
    for (const it of items ?? []) {
      base.all += 1
      base[it.status] += 1
    }
    return base
  }, [items])

  // Group the filtered items by their session, preserving recency order.
  const groups = useMemo(() => {
    const filtered = (items ?? []).filter((it) => filter === "all" || it.status === filter)
    const map = new Map<string, { title: string; items: ActionItemWithSession[] }>()
    for (const it of filtered) {
      const g = map.get(it.session_id) ?? { title: it.session_title, items: [] }
      g.items.push(it)
      map.set(it.session_id, g)
    }
    return [...map.entries()].map(([session_id, g]) => ({ session_id, ...g }))
  }, [items, filter])

  return (
    <div className="flex h-svh flex-col bg-background">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <Button
                variant="ghost"
                size="sm"
                className="-ml-2 mb-1 gap-1.5 text-muted-foreground"
                onClick={() => navigate("/")}
              >
                <ArrowLeft className="size-4" />
                Back to workspace
              </Button>
              <h1 className="text-lg font-semibold text-foreground">All action items</h1>
              <p className="text-sm text-muted-foreground">
                Every task across your meetings, in one place.
              </p>
            </div>
            <ThemeToggle />
          </div>

          <div className="mb-5 flex flex-wrap gap-1.5">
            {FILTERS.map((f) => (
              <Button
                key={f.key}
                variant={filter === f.key ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setFilter(f.key)}
                className={cn(filter === f.key && "font-medium")}
              >
                {f.label}
                <span className="ml-1.5 text-xs text-muted-foreground">{counts[f.key]}</span>
              </Button>
            ))}
          </div>

          {actionsQuery.isLoading ? (
            <div className="flex justify-center py-20">
              <Spinner className="size-6 text-muted-foreground" />
            </div>
          ) : groups.length === 0 ? (
            <EmptyState hasAny={(items ?? []).length > 0} />
          ) : (
            <div className="flex flex-col gap-6">
              {groups.map((group) => (
                <section key={group.session_id}>
                  <div className="mb-2 flex items-center justify-between">
                    <h2 className="truncate text-sm font-medium text-foreground">
                      {group.title}
                      <span className="ml-2 text-xs font-normal text-muted-foreground">
                        {group.items.length} item{group.items.length !== 1 ? "s" : ""}
                      </span>
                    </h2>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="shrink-0 gap-1 text-muted-foreground"
                      onClick={() => navigate(`/?session=${group.session_id}`)}
                    >
                      Open
                      <ArrowRight className="size-3.5" />
                    </Button>
                  </div>
                  <div className="flex flex-col gap-2">
                    {group.items.map((item) => (
                      <div
                        key={item.id}
                        className="flex items-start justify-between gap-3 rounded-lg border border-border bg-card p-3 shadow-sm"
                      >
                        <p className="min-w-0 flex-1 text-sm font-medium leading-snug text-foreground">
                          {item.task}
                        </p>
                        <div className="flex shrink-0 flex-col items-end gap-1.5">
                          <StatusBadge status={item.status} />
                          <div className="flex items-center gap-3">
                            {item.owner ? (
                              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                <User className="size-3" />
                                {item.owner}
                              </span>
                            ) : null}
                            {formatDue(item.due_date) ? (
                              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                <CalendarDays className="size-3" />
                                {formatDue(item.due_date)}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function EmptyState({ hasAny }: { hasAny: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3 py-20 text-center">
      <div className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <ClipboardList className="size-5" />
      </div>
      <p className="text-sm font-medium text-foreground">
        {hasAny ? "Nothing in this view" : "No action items yet"}
      </p>
      <p className="max-w-xs text-xs text-muted-foreground">
        {hasAny
          ? "Try a different status filter."
          : "Paste meeting notes in the workspace and your tasks will appear here."}
      </p>
    </div>
  )
}
