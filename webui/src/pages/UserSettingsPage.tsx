import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { useMe, useOrgs } from '../api/queries'
import { currentOrgId } from '../api/shell'
import type { OrgMember } from '../api/types'
import { PasswordField } from '../components/PasswordField'
import { useToast } from '../components/toastContext'

const fieldClass =
  'w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground disabled:opacity-60'

// Keyed by me.identity_id in the parent so a freshly loaded row seeds initial state directly, no
// reset-effect or render-time setState needed (same pattern as EmbeddingModelsPage's form).
function AccountForm({ me, orgName }: { me: OrgMember; orgName: string }) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  const [name, setName] = useState(me.name)
  const [email, setEmail] = useState(me.email ?? '')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileError, setProfileError] = useState<string | null>(null)

  const [newUsername, setNewUsername] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [savingUsername, setSavingUsername] = useState(false)
  const [usernameError, setUsernameError] = useState<string | null>(null)

  function invalidateMe() {
    return queryClient.invalidateQueries({ queryKey: ['orgs', 'me'] })
  }

  async function handleProfileSubmit(event: React.FormEvent) {
    event.preventDefault()
    setProfileError(null)
    setSavingProfile(true)
    try {
      await api.patch('/orgs/me', { name, email })
      await invalidateMe()
      showToast('Account updated.')
    } catch (err) {
      setProfileError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
    } finally {
      setSavingProfile(false)
    }
  }

  async function handleUsernameSubmit(event: React.FormEvent) {
    event.preventDefault()
    setUsernameError(null)
    setSavingUsername(true)
    try {
      await api.patch('/orgs/me/username', { username: newUsername, current_password: currentPassword })
      await invalidateMe()
      setNewUsername('')
      setCurrentPassword('')
      showToast('Username updated — use it next time you sign in.')
    } catch (err) {
      setUsernameError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
    } finally {
      setSavingUsername(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">User settings</h2>
        <button
          type="submit"
          form="account-form"
          disabled={savingProfile || !name.trim() || !email.trim()}
          className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {savingProfile ? 'Saving…' : 'Save'}
        </button>
      </div>

      {profileError && (
        <div className="mb-4 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {profileError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
        <form id="account-form" onSubmit={handleProfileSubmit} className="flex flex-col gap-4">
          <div>
            <span className="mb-1.5 block text-sm text-foreground">Org name</span>
            <input value={orgName} disabled className={fieldClass} />
          </div>
          <div>
            <label htmlFor="name" className="mb-1.5 block text-sm text-foreground">
              Full name
            </label>
            <input id="name" value={name} onChange={(event) => setName(event.target.value)} className={fieldClass} />
          </div>
          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm text-foreground">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={fieldClass}
            />
          </div>
          <div>
            <span className="mb-1.5 block text-sm text-foreground">Profile</span>
            <input value={me.profile_name} disabled className={fieldClass} />
            <p className="mt-1.5 text-xs text-muted-foreground">
              You can't change your own profile — ask another admin to change it from Members & access.
            </p>
          </div>
        </form>

        <div>
          <h3 className="mb-1.5 text-sm font-semibold text-foreground">Username</h3>
          <p className="mb-4 text-[13px] text-muted-foreground">
            This is what you sign in with. Changing it requires your current password.
          </p>
          <form onSubmit={handleUsernameSubmit} className="flex flex-col gap-4">
            {usernameError && (
              <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {usernameError}
              </div>
            )}
            <div>
              <label htmlFor="new-username" className="mb-1.5 block text-sm text-foreground">
                New username
              </label>
              <input
                id="new-username"
                placeholder={me.username}
                value={newUsername}
                onChange={(event) => setNewUsername(event.target.value)}
                className={fieldClass}
              />
            </div>
            <div>
              <label htmlFor="current-password" className="mb-1.5 block text-sm text-foreground">
                Current password
              </label>
              <PasswordField
                id="current-password"
                placeholder="Your current password"
                value={currentPassword}
                onChange={setCurrentPassword}
              />
            </div>
            <button
              type="submit"
              disabled={savingUsername || !newUsername.trim() || !currentPassword}
              className="self-start rounded-sm border border-border px-5 py-2 text-sm font-semibold text-foreground hover:bg-secondary disabled:opacity-60"
            >
              {savingUsername ? 'Updating…' : 'Update username'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export function UserSettingsPage() {
  const me = useMe()
  const orgs = useOrgs()
  const org = orgs.data?.find((entry) => entry.id === currentOrgId())

  if (me.isLoading || orgs.isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (!me.data) return <p className="text-sm text-muted-foreground">Could not load your account.</p>

  return <AccountForm key={me.data.identity_id} me={me.data} orgName={org?.name ?? ''} />
}
