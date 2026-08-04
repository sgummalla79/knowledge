import { useState } from 'react'
import { AuthLayout } from '../components/AuthLayout'
import { PasswordField } from '../components/PasswordField'
import { useToast } from '../components/toastContext'
import { changePassword } from '../api/auth'

export function ChangePasswordPage() {
  const { showToast } = useToast()
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setPending(true)
    try {
      const result = await changePassword(newPassword, confirmPassword)
      window.location.href = result.redirect
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Could not change password.')
      setPending(false)
    }
  }

  return (
    <AuthLayout title="Knowledge">
      <p className="subtitle" style={{ textAlign: 'center' }}>
        Choose a new password to continue.
      </p>
      <form onSubmit={handleSubmit}>
        <PasswordField id="new-password" placeholder="New password" value={newPassword} onChange={setNewPassword} />
        <PasswordField
          id="confirm-password"
          placeholder="Confirm new password"
          value={confirmPassword}
          onChange={setConfirmPassword}
        />
        <button type="submit" className="btn-block" disabled={pending || !newPassword || !confirmPassword}>
          Update password
        </button>
      </form>
    </AuthLayout>
  )
}
