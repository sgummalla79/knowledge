import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ApiError } from '../api/errors'
import { signOut } from '../api/auth'
import { useMe, useOrgs } from '../api/queries'
import { currentOrgId } from '../api/shell'
import type { OrgMember } from '../api/types'
import { Modal } from '../components/Modal'
import { PasswordField } from '../components/PasswordField'
import { WarningIcon } from '../components/icons'
import { useToast } from '../components/toastContext'

const fieldClass =
  'w-full rounded-sm border border-border bg-secondary px-4 py-2.5 text-[15px] text-foreground disabled:opacity-60'

interface ConfirmSensitiveChangeModalProps {
  changingUsername: boolean
  changingOrgName: boolean
  onConfirm: (password: string) => Promise<void>
  onClose: () => void
}

// Shown only when Save is clicked with username and/or org name changed — re-verifies the acting
// identity's current password before committing either (see AuthService.change_username /
// OrgMembershipService.change_organization_name), then signs the browser out so it doesn't keep
// running under a now-stale credential or org URL. Cancelling here discards the whole Save, not
// just the sensitive part — nothing is written to the API until this resolves, so a cancel (or a
// wrong password) leaves everything, including any name/email edit, unsaved.
function ConfirmSensitiveChangeModal({
  changingUsername,
  changingOrgName,
  onConfirm,
  onClose,
}: ConfirmSensitiveChangeModalProps) {
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const what =
    changingUsername && changingOrgName
      ? 'your username and organization name'
      : changingUsername
        ? 'your username'
        : 'your organization name'

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await onConfirm(password)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSaving(false)
    }
  }

  return (
    <Modal title="Confirm your password" onClose={onClose}>
      <p className="mb-4 text-sm text-muted-foreground">
        You're changing {what}. Enter your current password to confirm — you'll be signed out
        afterward and need to log back in.
      </p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="confirm-current-password" className="mb-1.5 block text-sm text-foreground">
            Current password
          </label>
          <PasswordField
            id="confirm-current-password"
            placeholder="Your current password"
            value={password}
            onChange={setPassword}
            autoFocus
          />
        </div>
        <div className="mt-2 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground">
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !password}
            className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// Keyed by me.identity_id in the parent so a freshly loaded row seeds initial state directly, no
// reset-effect or render-time setState needed (same pattern as EmbeddingModelsPage's form).
function AccountForm({
  me,
  orgId,
  initialOrgName,
  canEditOrgName,
}: {
  me: OrgMember
  orgId: string
  initialOrgName: string
  canEditOrgName: boolean
}) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  const [name, setName] = useState(me.name)
  const [email, setEmail] = useState(me.email ?? '')
  const [username, setUsername] = useState(me.username)
  const [orgName, setOrgName] = useState(initialOrgName)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)

  const profileDirty = name !== me.name || email !== (me.email ?? '')
  const usernameDirty = username !== me.username
  const orgNameDirty = canEditOrgName && orgName !== initialOrgName
  const dirty = profileDirty || usernameDirty || orgNameDirty

  async function saveProfile() {
    await api.patch('/orgs/me', { name, email })
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    if (usernameDirty || orgNameDirty) {
      setConfirming(true)
      return
    }
    setSaving(true)
    try {
      await saveProfile()
      await queryClient.invalidateQueries({ queryKey: ['orgs', 'me'] })
      showToast('Account updated.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function handleConfirm(password: string) {
    // Password-gated calls run first: if the password is wrong, this throws before anything else
    // is touched, so a failed confirm leaves the whole Save uncommitted — including name/email —
    // not just the sensitive fields. saveProfile() has no password check, so it goes last.
    if (orgNameDirty) {
      await api.patch(`/orgs/${orgId}`, { name: orgName, current_password: password })
    }
    if (usernameDirty) {
      await api.patch('/orgs/me/username', { username, current_password: password })
    }
    if (profileDirty) {
      await saveProfile()
    }
    await signOut()
    window.location.href = '/sign-in'
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[22px] font-semibold text-foreground">Profile</h2>
        <button
          type="submit"
          form="account-form"
          disabled={saving || !dirty || !name.trim() || !email.trim() || !username.trim() || (canEditOrgName && !orgName.trim())}
          className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>

      <div className="mb-6 flex items-start gap-2.5 rounded-sm border border-warning/40 bg-warning/10 px-3.5 py-3 text-[13px] text-warning">
        <WarningIcon className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          Changing your username{canEditOrgName ? ' or organization name' : ''} requires your
          current password and will sign you out immediately.
        </span>
      </div>

      {error && (
        <div className="mb-4 rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <form id="account-form" onSubmit={handleSubmit} className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
        <div className="flex flex-col gap-4">
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
            <p className="mt-1.5 text-xs text-muted-foreground">You can't change your own profile.</p>
          </div>
        </div>
        <div className="flex flex-col gap-4">
          <div>
            <label htmlFor="org-name" className="mb-1.5 block text-sm text-foreground">
              Org name
            </label>
            <input
              id="org-name"
              value={orgName}
              onChange={(event) => setOrgName(event.target.value)}
              disabled={!canEditOrgName}
              className={fieldClass}
            />
            {!canEditOrgName && (
              <p className="mt-1.5 text-xs text-muted-foreground">Only an admin can change the organization name.</p>
            )}
          </div>
          <div>
            <label htmlFor="username" className="mb-1.5 block text-sm text-foreground">
              Username
            </label>
            <input
              id="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className={fieldClass}
            />
          </div>
        </div>
      </form>

      {confirming && (
        <ConfirmSensitiveChangeModal
          changingUsername={usernameDirty}
          changingOrgName={orgNameDirty}
          onConfirm={handleConfirm}
          onClose={() => setConfirming(false)}
        />
      )}
    </div>
  )
}

export function UserSettingsPage() {
  const me = useMe()
  const orgs = useOrgs()
  const org = orgs.data?.find((entry) => entry.id === currentOrgId())

  if (me.isLoading || orgs.isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (!me.data || !org) return <p className="text-sm text-muted-foreground">Could not load your account.</p>

  return (
    <AccountForm
      key={me.data.identity_id}
      me={me.data}
      orgId={org.id}
      initialOrgName={org.name}
      canEditOrgName={org.permissions.includes('org:write')}
    />
  )
}
