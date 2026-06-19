import { CalendarClock, CalendarX2, Check, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { CalendarActionEvent } from "@/lib/types"

/** Renders a single calendar reschedule/cancel awaiting the user's Approve / Decline. */
export function CalendarActionCard({
  action,
  decided,
  busy,
  onApprove,
  onDecline,
}: {
  action: CalendarActionEvent
  decided: "approved" | "declined" | null
  busy: boolean
  onApprove: () => void
  onDecline: () => void
}) {
  const isDelete = action.action === "delete_event"
  const Icon = isDelete ? CalendarX2 : CalendarClock

  return (
    <div className="w-full overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Icon className="size-4 text-muted-foreground" />
        <span className="text-sm font-medium text-foreground">
          {isDelete ? "Remove calendar event" : "Update calendar event"}
        </span>
      </div>
      <div className="px-4 py-3">
        <p className="text-sm font-medium text-foreground">{action.title}</p>
        {action.when ? (
          <p className="mt-0.5 text-xs text-muted-foreground">{action.when}</p>
        ) : null}
        <p className="mt-2 text-sm text-muted-foreground">{action.detail}</p>
      </div>
      <div className="flex items-center justify-end gap-2 px-4 pb-3">
        <Button
          size="sm"
          variant="outline"
          onClick={onDecline}
          disabled={decided !== null || busy}
        >
          <X className="size-4" />
          {decided === "declined" ? "Declined" : "Decline"}
        </Button>
        <Button
          size="sm"
          variant={isDelete ? "destructive" : "default"}
          onClick={onApprove}
          disabled={decided !== null || busy}
        >
          <Check className="size-4" />
          {decided === "approved" ? "Approved" : isDelete ? "Remove event" : "Approve"}
        </Button>
      </div>
    </div>
  )
}
