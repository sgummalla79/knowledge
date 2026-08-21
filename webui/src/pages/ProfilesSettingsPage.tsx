import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useOrgs, useProfiles } from '../api/queries'
import { currentOrgId } from '../api/shell'
import type { Profile } from '../api/types'
import { useToast } from '../components/toastContext'

export function ProfilesSettingsPage() {
  const orgs = useOrgs()
  const orgId = currentOrgId()
  const profiles = useProfiles()
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const navigate = useNavigate()

  const org = orgs.data?.find((entry) => entry.id === orgId)
  const canManage = org?.permissions.includes('profiles:write') ?? false

  async function handleDelete(profile: Profile) {
    if (!window.confirm(`Delete "${profile.name}"? Members assigned to it must be moved to another profile first.`)) return
    try {
      await api.delete(`/profiles/${profile.id}`)
      void queryClient.invalidateQueries({ queryKey: ['profiles'] })
      showToast('Profile deleted.')
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : 'Something went wrong — please try again.', 'error')
    }
  }

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">Profiles</h2>
        {canManage && (
          <button
            type="button"
            onClick={() => navigate('/org/profiles/new')}
            className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
          >
            New profile
          </button>
        )}
      </div>
      <p className="mb-6 max-w-xl text-[13.5px] text-muted-foreground">
        A profile is a reusable bundle of read/write permissions, assigned to org members (and,
        for a connected application, to whoever it acts as). Admin, Contributor, and Viewer are
        seeded for every org and can't be edited or deleted.
      </p>

      {profiles.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {profiles.data && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="pb-2.5 font-semibold">Profile</th>
                <th className="pb-2.5 font-semibold">Permissions</th>
                <th className="pb-2.5 font-semibold"></th>
              </tr>
            </thead>
            <tbody>
              {profiles.data.map((profile) => (
                <tr key={profile.id} className="border-t border-border align-top">
                  <td className="py-3.5 pr-4">
                    <div className="font-semibold text-foreground">{profile.name}</div>
                    {profile.description && (
                      <div className="max-w-xs text-[12.5px] text-muted-foreground">{profile.description}</div>
                    )}
                  </td>
                  <td className="py-3.5 pr-4">
                    {profile.is_admin ? (
                      <span className="rounded-sm bg-accent px-2.5 py-0.5 text-xs text-accent-foreground">
                        Full access
                      </span>
                    ) : (
                      <div className="flex max-w-sm flex-wrap gap-1.5">
                        {profile.permissions.map((permission) => (
                          <span key={permission} className="rounded-sm bg-secondary px-2 py-0.5 text-[11px] text-foreground">
                            {permission}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="py-3.5 text-right">
                    {canManage && !profile.is_system && (
                      <div className="flex justify-end gap-3">
                        <button
                          type="button"
                          onClick={() => navigate(`/org/profiles/${profile.id}/edit`)}
                          className="text-[13px] text-primary hover:underline"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDelete(profile)}
                          className="text-[13px] text-destructive hover:underline"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                    {profile.is_system && (
                      <button
                        type="button"
                        onClick={() => navigate(`/org/profiles/${profile.id}/edit`)}
                        className="text-[13px] text-primary hover:underline"
                      >
                        View
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
