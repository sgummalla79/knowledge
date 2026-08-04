import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteApplication, listApplications, listScopeGroups, revokeApplicationToken } from './applications'

export function useApplications() {
  return useQuery({
    queryKey: ['applications'],
    queryFn: listApplications,
  })
}

export function useScopeGroups() {
  return useQuery({
    queryKey: ['scope-groups'],
    queryFn: listScopeGroups,
  })
}

export function useRevokeApplicationToken() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: revokeApplicationToken,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['applications'] }),
  })
}

export function useDeleteApplication() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteApplication,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['applications'] }),
  })
}
