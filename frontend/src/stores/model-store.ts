import { create } from "zustand"
import { persist } from "zustand/middleware"

import { api } from "@/lib/api"
import type { ModelInfo, ReasoningEffort } from "@/lib/types"

type ModelState = {
  /** Catalog from the server (models with a configured key). Not persisted. */
  models: ModelInfo[]
  /** Server default, applied until — and unless — the user picks their own. Not persisted. */
  defaultModel: string | null
  defaultReasoning: ReasoningEffort | null
  loaded: boolean
  /** The user's explicit pick (persisted across reloads). null ⇒ follow the server default. */
  pickedModel: string | null
  pickedReasoning: ReasoningEffort | null
  load: () => Promise<void>
  setModel: (id: string) => void
  setReasoning: (effort: ReasoningEffort) => void
}

export const useModelStore = create<ModelState>()(
  persist(
    (set, get) => ({
      models: [],
      defaultModel: null,
      defaultReasoning: null,
      loaded: false,
      pickedModel: null,
      pickedReasoning: null,

      load: async () => {
        try {
          const res = await api.getModels()
          const available = new Set(res.models.map((m) => m.id))
          // Drop a stale pick (e.g. a provider key was removed) so the default takes over.
          const picked = get().pickedModel
          set({
            models: res.models,
            defaultModel: res.default.model,
            defaultReasoning: res.default.reasoning,
            loaded: true,
            pickedModel: picked && available.has(picked) ? picked : null,
          })
        } catch {
          set({ loaded: true })
        }
      },

      setModel: (id) => {
        const model = get().models.find((m) => m.id === id)
        set({
          pickedModel: id,
          // Seed a sensible reasoning level when switching to a reasoning model.
          pickedReasoning: model?.supports_reasoning
            ? model.default_reasoning ?? "low"
            : get().pickedReasoning,
        })
      },

      setReasoning: (effort) => set({ pickedReasoning: effort }),
    }),
    {
      name: "m32-model",
      // Only the user's choice survives reloads; the catalog is always refetched.
      partialize: (s) => ({ pickedModel: s.pickedModel, pickedReasoning: s.pickedReasoning }),
    }
  )
)

/** The model that should be used right now — the user's pick, or the server default. */
export function activeModel(s: ModelState): ModelInfo | null {
  const id = s.pickedModel ?? s.defaultModel
  return s.models.find((m) => m.id === id) ?? null
}

/** The reasoning effort to send for the active model (only meaningful for reasoning models). */
export function activeReasoning(s: ModelState): ReasoningEffort | null {
  const model = activeModel(s)
  if (!model?.supports_reasoning) return null
  return s.pickedReasoning ?? s.defaultReasoning ?? model.default_reasoning ?? "low"
}
