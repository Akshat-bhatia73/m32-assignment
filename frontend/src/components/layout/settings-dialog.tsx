import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Calendar, Check, Mail, RefreshCw } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { TeamSettings } from "@/components/layout/team-settings"
import { api, ApiError } from "@/lib/api"
import type { IntegrationStatus } from "@/lib/types"

type ToolkitKey = keyof IntegrationStatus

const TOOLKITS: { key: ToolkitKey; label: string; description: string; icon: typeof Mail }[] = [
  {
    key: "gmail",
    label: "Gmail",
    description: "Send follow-up emails to the people who own each action item.",
    icon: Mail,
  },
  {
    key: "googlecalendar",
    label: "Google Calendar",
    description: "See your upcoming schedule and add events for dated action items.",
    icon: Calendar,
  },
]

export function SettingsDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const statusQuery = useQuery({
    queryKey: ["integrations"],
    queryFn: api.getIntegrations,
    enabled: open,
  })
  const [connecting, setConnecting] = useState<ToolkitKey | null>(null)

  async function connect(toolkit: ToolkitKey) {
    setConnecting(toolkit)
    try {
      const { url } = await api.connectIntegration(toolkit)
      window.open(url, "_blank", "noopener,noreferrer")
      toast.info("Finish connecting in the new tab", {
        description: "Authorize access, then come back and refresh the status here.",
      })
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "Please try again."
      toast.error("Couldn't start the connection", { description: detail })
    } finally {
      setConnecting(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85svh] w-full flex-col gap-4 overflow-x-hidden overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Connect your tools so the copilot can send emails and manage your calendar.
          </DialogDescription>
        </DialogHeader>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-foreground">Connections</h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => queryClient.invalidateQueries({ queryKey: ["integrations"] })}
              disabled={statusQuery.isFetching}
            >
              <RefreshCw className={statusQuery.isFetching ? "size-4 animate-spin" : "size-4"} />
              Refresh
            </Button>
          </div>

          <ul className="space-y-2">
            {TOOLKITS.map(({ key, label, description, icon: Icon }) => {
              const connected = statusQuery.data?.[key] ?? false
              return (
                <li
                  key={key}
                  className="flex items-center gap-3 rounded-xl border border-border bg-card p-3"
                >
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                    <Icon className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground">{label}</p>
                    <p className="truncate text-xs text-muted-foreground">{description}</p>
                  </div>
                  {statusQuery.isLoading ? (
                    <Spinner className="size-4 text-muted-foreground" />
                  ) : connected ? (
                    <span className="flex shrink-0 items-center gap-1.5 text-sm font-medium text-chart-2">
                      <Check className="size-4" />
                      Connected
                    </span>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      className="shrink-0"
                      disabled={connecting === key}
                      onClick={() => connect(key)}
                    >
                      {connecting === key ? <Spinner className="size-4" /> : null}
                      Connect
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
        </section>

        <Separator />

        <TeamSettings open={open} />
      </DialogContent>
    </Dialog>
  )
}
