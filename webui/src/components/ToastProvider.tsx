import { useCallback, useRef, useState, type ReactNode } from 'react'
import { ToastContext, type ToastVariant } from './toastContext'

interface Toast {
  id: number
  message: string
  variant: ToastVariant
}

const AUTO_DISMISS_MS = 6000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const showToast = useCallback(
    (message: string, variant: ToastVariant = 'error') => {
      const id = nextId.current++
      setToasts((current) => [...current, { id, message, variant }])
      setTimeout(() => dismiss(id), AUTO_DISMISS_MS)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="toast-viewport">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.variant}`} role="alert">
            <span>{toast.message}</span>
            <button type="button" className="toast-close" aria-label="Dismiss" onClick={() => dismiss(toast.id)}>
              &times;
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
