import { Check, Copy, Download } from "lucide-react"
import { useState } from "react"

import {
  Artifact,
  ArtifactActions,
  ArtifactClose,
  ArtifactContent,
  ArtifactHeader,
} from "@/components/ai-elements/artifact"
import { artifactMeta } from "@/lib/artifacts"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { IconButton } from "@/components/ui/icon-button"
import type { Artifact as ArtifactT } from "@/lib/types"

export function ArtifactViewer({
  artifact,
  onClose,
}: {
  artifact: ArtifactT | null
  onClose: () => void
}) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    if (!artifact) return
    await navigator.clipboard.writeText(artifact.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  function download() {
    if (!artifact) return
    const blob = new Blob([artifact.content], { type: "text/plain;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    // Images carry transcribed text, so always download the text as .txt.
    a.download =
      artifact.kind === "file" && /\.[a-z0-9]+$/i.test(artifact.name)
        ? artifact.name
        : `${artifact.name.replace(/\.[a-z0-9]+$/i, "")}.txt`
    document.body.append(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <Dialog open={!!artifact} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        showCloseButton={false}
        className="max-w-2xl gap-0 overflow-hidden rounded-2xl p-0"
      >
        {artifact ? (
          <Artifact className="border-0 shadow-none">
            <ArtifactHeader>
              <div className="min-w-0">
                <DialogTitle className="truncate text-sm font-medium text-foreground">
                  {artifact.name}
                </DialogTitle>
                <DialogDescription className="text-xs text-muted-foreground">
                  {artifactMeta(artifact)}
                </DialogDescription>
              </div>
              <ArtifactActions>
                <IconButton
                  tooltip={copied ? "Copied" : "Copy text"}
                  size="icon-sm"
                  variant="ghost"
                  className="text-muted-foreground"
                  onClick={copy}
                >
                  {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                </IconButton>
                <IconButton
                  tooltip="Download as text"
                  size="icon-sm"
                  variant="ghost"
                  className="text-muted-foreground"
                  onClick={download}
                >
                  <Download className="size-4" />
                </IconButton>
                <DialogClose
                  render={<ArtifactClose className="rounded-full" />}
                />
              </ArtifactActions>
            </ArtifactHeader>
            <ArtifactContent className="max-h-[70vh]">
              {artifact.previewUrl && artifact.kind === "image" ? (
                <div className="flex flex-col gap-4">
                  <img
                    src={artifact.previewUrl}
                    alt={artifact.name}
                    className="mx-auto max-h-[40vh] rounded-lg border border-border object-contain"
                  />
                  <div>
                    <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Transcribed text
                    </p>
                    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-foreground">
                      {artifact.content}
                    </pre>
                  </div>
                </div>
              ) : (
                <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-foreground">
                  {artifact.content}
                </pre>
              )}
            </ArtifactContent>
          </Artifact>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
