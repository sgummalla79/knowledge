export type SourceType = 'upload' | 'url' | 'connector'

interface Option {
  value: SourceType
  label: string
  disabled?: boolean
}

// "Connect source" has no backend implementation — sources.type has a 'connector' enum value but
// nothing constructs one (see A.4/the plan's Upload notes) — rendered disabled, not a fake no-op.
const OPTIONS: Option[] = [
  { value: 'upload', label: 'Upload file' },
  { value: 'url', label: 'Add URL' },
  { value: 'connector', label: 'Connect source', disabled: true },
]

interface Props {
  value: SourceType
  onChange: (value: SourceType) => void
}

export function SourceTypeRadio({ value, onChange }: Props) {
  return (
    <div className="mb-6 flex gap-1 rounded-sm bg-secondary p-1">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          disabled={option.disabled}
          title={option.disabled ? 'Coming soon' : undefined}
          onClick={() => onChange(option.value)}
          className={`flex-1 rounded-sm px-3 py-2 text-[13px] font-medium transition-colors ${
            value === option.value ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'
          } ${option.disabled ? 'cursor-not-allowed opacity-50' : 'hover:text-foreground'}`}
        >
          {option.label}
          {option.disabled && <span className="ml-1 text-[10px]">(soon)</span>}
        </button>
      ))}
    </div>
  )
}
