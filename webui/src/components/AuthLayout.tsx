import type { ReactNode } from 'react'

export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <img src="/static/brand-icon.png" alt="" />
          <h1>{title}</h1>
        </div>
        {children}
      </div>
    </div>
  )
}
