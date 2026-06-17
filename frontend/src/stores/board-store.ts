import { create } from "zustand"

import type { ActionItem, ActionItemEvent } from "@/lib/types"

type BoardState = {
  items: ActionItem[]
  /** ids touched by the live stream this turn — used for a subtle highlight. */
  recentlyChanged: Set<string>
  setAll: (items: ActionItem[]) => void
  applyEvent: (event: ActionItemEvent) => void
  clearRecent: () => void
  reset: () => void
}

function toItem(event: ActionItemEvent, prev?: ActionItem): ActionItem {
  return {
    id: event.id,
    session_id: event.session_id,
    task: event.task,
    owner: event.owner,
    due_date: event.due_date,
    status: event.status,
    external_ref: prev?.external_ref ?? null,
    created_at: event.created_at,
    updated_at: event.updated_at,
  }
}

export const useBoardStore = create<BoardState>((set) => ({
  items: [],
  recentlyChanged: new Set(),
  setAll: (items) => set({ items }),
  applyEvent: (event) =>
    set((state) => {
      const recentlyChanged = new Set(state.recentlyChanged).add(event.id)
      if (event.op === "deleted") {
        return { items: state.items.filter((i) => i.id !== event.id), recentlyChanged }
      }
      const existing = state.items.find((i) => i.id === event.id)
      if (existing) {
        return {
          items: state.items.map((i) => (i.id === event.id ? toItem(event, existing) : i)),
          recentlyChanged,
        }
      }
      return { items: [...state.items, toItem(event)], recentlyChanged }
    }),
  clearRecent: () => set({ recentlyChanged: new Set() }),
  reset: () => set({ items: [], recentlyChanged: new Set() }),
}))
