import { Calendar, CircleDashed, Mail, Check } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { ActionStatus } from "@/lib/types"

const CONFIG: Record<
  ActionStatus,
  { label: string; variant: "default" | "secondary" | "outline"; Icon: typeof Check }
> = {
  open: { label: "Open", variant: "outline", Icon: CircleDashed },
  scheduled: { label: "Scheduled", variant: "secondary", Icon: Calendar },
  sent: { label: "Sent", variant: "secondary", Icon: Mail },
  done: { label: "Done", variant: "default", Icon: Check },
}

export function StatusBadge({ status }: { status: ActionStatus }) {
  const { label, variant, Icon } = CONFIG[status]
  return (
    <Badge variant={variant} className="gap-1">
      <Icon className="size-3" />
      {label}
    </Badge>
  )
}
