import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Logo } from './Logo'

interface Props {
  eyebrow: string
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
  // Narrow (max-w-md) fits every single-column auth form (sign-in, change-password, authorize).
  // Sign-up's two-column layout needs more room, so it opts into a wider card instead of widening
  // every other auth page.
  wide?: boolean
}

export function AuthCard({ eyebrow, title, subtitle, children, footer, wide = false }: Props) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center bg-background px-6 py-16">
      <Link to="/" className="mb-10 flex items-center gap-2 text-primary">
        <Logo />
        <span className="text-xl font-semibold text-foreground">Knowledge</span>
      </Link>
      <div className={`w-full rounded-md border border-border bg-card p-8 ${wide ? 'max-w-2xl' : 'max-w-md'}`}>
        <div className="mb-1 text-[11px] font-medium uppercase tracking-widest text-primary">{eyebrow}</div>
        <h1 className="mb-2 text-[26px] font-semibold text-foreground">{title}</h1>
        <p className="mb-7 text-sm text-muted-foreground">{subtitle}</p>
        {children}
      </div>
      <p className="mt-6 text-sm text-muted-foreground">{footer}</p>
    </div>
  )
}
