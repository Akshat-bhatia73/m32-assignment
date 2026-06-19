import { Check, Copy, Mail, X } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { IconButton } from "@/components/ui/icon-button"
import type { EmailDraftEvent } from "@/lib/types"

/** Renders a follow-up email draft as a structured card with one-click send / dismiss actions. */
export function EmailDraftCard({
  draft,
  onSend,
  onDecline,
  sent,
  declined,
  busy,
}: {
  draft: EmailDraftEvent
  onSend: () => void
  onDecline: () => void
  sent: boolean
  declined: boolean
  busy: boolean
}) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    await navigator.clipboard.writeText(`Subject: ${draft.subject}\n\n${draft.body}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="w-full overflow-hidden rounded-xl border border-border bg-card">
      <div className="space-y-1 border-b border-border px-4 py-3">
        <Field label="To" value={draft.to.join(", ")} />
        <Field label="Subject" value={draft.subject} />
      </div>
      <div className="px-4 py-4">
        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-foreground">
          {draft.body}
        </pre>
      </div>
      <div className="flex items-center justify-end gap-2 px-4 pb-3">
        <IconButton
          tooltip={copied ? "Copied" : "Copy email"}
          size="icon-sm"
          variant="outline"
          onClick={copy}
        >
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
        </IconButton>
        <Button
          size="sm"
          variant="outline"
          onClick={onDecline}
          disabled={sent || declined || busy}
        >
          <X className="size-4" />
          {declined ? "Dismissed" : "Dismiss"}
        </Button>
        <Button size="sm" onClick={onSend} disabled={sent || declined || busy}>
          <Mail className="size-4" />
          {sent ? "Sent" : "Send via Gmail"}
        </Button>
      </div>
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 text-sm">
      <span className="shrink-0 text-muted-foreground">{label}:</span>
      <span className="min-w-0 truncate font-medium text-foreground">{value}</span>
    </div>
  )
}
