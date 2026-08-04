import { createContext, useContext } from 'react'

export type ToastVariant = 'error' | 'success'

export interface ToastContextValue {
  // Defaults to 'error' — nearly every existing call site is a failure message (mutation errors,
  // job failures), so this keeps every one of them unchanged; only a genuine success message needs
  // to pass 'success' explicitly.
  showToast: (message: string, variant?: ToastVariant) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within a ToastProvider')
  return context
}
