import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { ApiError, api } from "@/lib/api"
import type { User } from "@/lib/types"

export function useCurrentUser() {
  return useQuery<User | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api.me()
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null
        throw err
      }
    },
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.login,
    onSuccess: (user) => qc.setQueryData(["me"], user),
  })
}

export function useSignup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.signup,
    onSuccess: (user) => qc.setQueryData(["me"], user),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      qc.setQueryData(["me"], null)
      qc.clear()
    },
  })
}
