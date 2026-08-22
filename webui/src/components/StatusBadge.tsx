const STYLES: Record<string, string> = {
  queued: 'bg-secondary text-foreground/70',
  processing: 'bg-accent text-accent-foreground',
  indexed: 'bg-accent text-accent-foreground',
  failed: 'bg-destructive/15 text-destructive',
}

const LABELS: Record<string, string> = {
  queued: 'Queued',
  processing: 'Processing',
  indexed: 'Indexed',
  failed: 'Failed',
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`shrink-0 rounded-sm px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide ${
        STYLES[status] ?? 'bg-secondary text-foreground/70'
      }`}
    >
      {LABELS[status] ?? status}
    </span>
  )
}
