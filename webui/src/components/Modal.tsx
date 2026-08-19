import type { ReactNode } from 'react'

interface Props {
  title: string
  onClose: () => void
  children: ReactNode
}

export function Modal({ title, onClose, children }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md rounded-md border border-border bg-card p-6 shadow-lg"
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-muted-foreground hover:text-foreground">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
