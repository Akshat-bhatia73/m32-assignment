import { CalendarDays, Check, MoreHorizontal, RotateCcw, Trash2, User } from "lucide-react"

import { StatusBadge } from "@/components/board/status-badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { ActionItem } from "@/lib/types"

function formatDue(due: string | null): string | null {
  if (!due) return null
  const date = new Date(`${due}T00:00:00`)
  if (Number.isNaN(date.getTime())) return due
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export function ActionCard({
  item,
  highlighted,
  onChanged,
}: {
  item: ActionItem
  highlighted: boolean
  onChanged: () => void
}) {
  const due = formatDue(item.due_date)

  async function setStatus(status: ActionItem["status"]) {
    await api.updateAction(item.id, { status })
    onChanged()
  }

  async function remove() {
    await api.deleteAction(item.id)
    onChanged()
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-3 shadow-sm transition-colors",
        "animate-in fade-in-0 slide-in-from-bottom-1 duration-300",
        highlighted && "border-primary/40 ring-1 ring-primary/20"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium leading-snug text-foreground">{item.task}</p>
        <DropdownMenu>
          <Tooltip>
            <TooltipTrigger
              render={
                <DropdownMenuTrigger
                  render={
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Task options"
                      className="-mr-1 -mt-1 shrink-0 rounded-full"
                    >
                      <MoreHorizontal className="size-4" />
                    </Button>
                  }
                />
              }
            />
            <TooltipContent>Task options</TooltipContent>
          </Tooltip>
          <DropdownMenuContent align="end">
            {item.status === "done" ? (
              <DropdownMenuItem onClick={() => setStatus("open")}>
                <RotateCcw className="size-4" />
                Reopen
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem onClick={() => setStatus("done")}>
                <Check className="size-4" />
                Mark done
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onClick={remove}>
              <Trash2 className="size-4" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <StatusBadge status={item.status} />
        {item.owner ? (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <User className="size-3" />
            {item.owner}
          </span>
        ) : null}
        {due ? (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <CalendarDays className="size-3" />
            {due}
          </span>
        ) : null}
      </div>
    </div>
  )
}
