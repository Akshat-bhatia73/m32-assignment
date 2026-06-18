import type { Artifact } from "@/lib/types"

/** Short, human-readable description of an artifact for chips and headers. */
export function artifactMeta(a: Artifact): string {
  const lines = a.content ? a.content.split("\n").length : 0
  if (a.kind === "image") return "Screenshot · transcribed"
  if (a.kind === "paste") return `Pasted text · ${lines} lines`
  return `${lines} lines`
}
