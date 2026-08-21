import { useState } from 'react'
import { Modal } from './Modal'

interface SecretField {
  label: string
  value: string
}

interface Props {
  applicationName: string
  fields: SecretField[]
  onClose: () => void
}

function CopyableField({ label, value }: SecretField) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="mb-3">
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="flex items-center gap-2 rounded-sm border border-border bg-secondary px-4 py-3">
        <code className="flex-1 overflow-x-auto whitespace-nowrap text-[13px] text-foreground">{value}</code>
        <button
          type="button"
          onClick={() => void handleCopy()}
          className="shrink-0 rounded-sm bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-90"
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
    </div>
  )
}

// Shown exactly once, immediately after create/rotate — the raw secret(s) aren't persisted
// anywhere (only their hash is), so this modal is the only chance to ever see or copy them.
export function ApplicationSecretRevealModal({ applicationName, fields, onClose }: Props) {
  return (
    <Modal title="Credentials" onClose={onClose} maxWidthClassName="max-w-lg">
      <p className="mb-4 text-[13.5px] text-muted-foreground">
        This is the only time <span className="font-semibold text-foreground">{applicationName}</span>&apos;s
        credentials will be shown. Copy them now — they can&apos;t be recovered later, only rotated for new ones.
      </p>
      <div className="mb-2">
        {fields.map((field) => (
          <CopyableField key={field.label} label={field.label} value={field.value} />
        ))}
      </div>
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onClose}
          className="rounded-sm bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          Done
        </button>
      </div>
    </Modal>
  )
}
