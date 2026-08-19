interface Props {
  eyebrow: string
  title: string
  description: string
}

// Placeholder for pages not yet built out (see the plan's Phase B build order) — real content
// replaces this one page at a time. Never fabricates data; just says so.
export function ComingSoonPage({ eyebrow, title, description }: Props) {
  return (
    <div className="py-16">
      <div className="mb-3 text-[11px] font-medium uppercase tracking-widest text-primary">{eyebrow}</div>
      <h1 className="mb-3 text-[32px] font-semibold text-foreground">{title}</h1>
      <p className="max-w-lg text-sm text-muted-foreground">{description}</p>
    </div>
  )
}
