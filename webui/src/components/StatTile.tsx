interface Props {
  label: string
  value: string | number | null
  loading?: boolean
}

export function StatTile({ label, value, loading }: Props) {
  return (
    <div>
      <div className="text-[28px] font-semibold text-foreground">
        {loading || value === null ? <span className="inline-block h-7 w-16 animate-pulse rounded-sm bg-secondary" /> : value}
      </div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  )
}
