import { Check, Copy, Download } from "lucide-react"
import { useState } from "react"

import {
  Artifact,
  ArtifactActions,
  ArtifactClose,
  ArtifactContent,
  ArtifactHeader,
} from "@/components/ai-elements/artifact"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { IconButton } from "@/components/ui/icon-button"
import { artifactMeta } from "@/lib/artifacts"
import type { Artifact as ArtifactT } from "@/lib/types"

type PreviewMode = "image" | "pdf" | "text"

function previewMode(a: ArtifactT): PreviewMode {
  if (a.previewUrl && a.mime?.startsWith("image/")) return "image"
  if (a.previewUrl && a.mime === "application/pdf") return "pdf"
  return "text"
}

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
    const a = document.createElement("a")
    if (artifact.previewUrl && artifact.kind !== "paste") {
      // Download the original uploaded file.
      a.href = artifact.previewUrl
      a.download = artifact.name
    } else {
      const blob = new Blob([artifact.content], { type: "text/plain;charset=utf-8" })
      a.href = URL.createObjectURL(blob)
      a.download = `${artifact.name.replace(/\.[a-z0-9]+$/i, "")}.txt`
    }
    document.body.append(a)
    a.click()
    a.remove()
  }

  const mode = artifact ? previewMode(artifact) : "text"
  // The original couldn't be embedded (e.g. .docx, or after a reload that dropped the blob).
  const noOriginal =
    artifact != null &&
    !artifact.previewUrl &&
    (artifact.mime?.startsWith("image/") || artifact.mime === "application/pdf")

  return (
    <Dialog open={!!artifact} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        showCloseButton={false}
        className="max-w-3xl gap-0 overflow-hidden rounded-2xl p-0"
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
                  tooltip={
                    artifact.previewUrl && artifact.kind !== "paste"
                      ? "Download original"
                      : "Download as text"
                  }
                  size="icon-sm"
                  variant="ghost"
                  className="text-muted-foreground"
                  onClick={download}
                >
                  <Download className="size-4" />
                </IconButton>
                <DialogClose render={<ArtifactClose className="rounded-full" />} />
              </ArtifactActions>
            </ArtifactHeader>

            {mode === "pdf" ? (
              <iframe
                src={artifact.previewUrl}
                title={artifact.name}
                className="h-[72vh] w-full border-0 bg-muted"
              />
            ) : (
              <ArtifactContent className="max-h-[72vh]">
                {mode === "image" ? (
                  <img
                    src={artifact.previewUrl}
                    alt={artifact.name}
                    className="mx-auto max-h-[68vh] rounded-lg border border-border object-contain"
                  />
                ) : (
                  <>
                    {noOriginal ? (
                      <p className="mb-3 rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
                        Original preview isn't available here — showing the extracted text.
                      </p>
                    ) : null}
                    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-foreground">
                      {artifact.content}
                    </pre>
                  </>
                )}
              </ArtifactContent>
            )}
          </Artifact>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
