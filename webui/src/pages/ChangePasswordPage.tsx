import { useState } from 'react'
import { changePassword } from '../api/auth'
import { ApiError } from '../api/errors'
import { AuthCard } from '../components/AuthCard'
import { PasswordField } from '../components/PasswordField'

export function ChangePasswordPage() {
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const { redirect } = await changePassword(newPassword, confirmPassword)
      window.location.href = redirect
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong — please try again.')
      setSubmitting(false)
    }
  }

  return (
    <AuthCard
      eyebrow="First login"
      title="Set a new password"
      subtitle="Your account was created with a temporary password — choose one only you know."
      footer={null}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-sm border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="new-password" className="mb-1.5 block text-sm text-foreground">
            New password
          </label>
          <PasswordField
            id="new-password"
            placeholder="At least 8 characters"
            value={newPassword}
            onChange={setNewPassword}
            autoFocus
          />
        </div>
        <div>
          <label htmlFor="confirm-password" className="mb-1.5 block text-sm text-foreground">
            Confirm password
          </label>
          <PasswordField
            id="confirm-password"
            placeholder="Type it again"
            value={confirmPassword}
            onChange={setConfirmPassword}
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="mt-1 rounded-sm bg-primary px-5 py-2.5 text-[15px] font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {submitting ? 'Saving…' : 'Save password'}
        </button>
      </form>
    </AuthCard>
  )
}
