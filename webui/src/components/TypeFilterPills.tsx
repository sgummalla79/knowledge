import { DOCUMENT_TYPES } from '../lib/documentTypes'

interface Props {
  selected: string | null
  onChange: (type: string | null) => void
}

export function TypeFilterPills({ selected, onChange }: Props) {
  return (
    <div className="mb-6 flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => onChange(null)}
        className={`rounded-sm px-3 py-1.5 text-[13px] ${
          selected === null ? 'bg-primary text-primary-foreground' : 'bg-secondary text-foreground/80'
        }`}
      >
        All
      </button>
      {DOCUMENT_TYPES.map((type) => (
        <button
          key={type.value}
          type="button"
          onClick={() => onChange(type.value)}
          className={`rounded-sm px-3 py-1.5 text-[13px] ${
            selected === type.value ? 'bg-primary text-primary-foreground' : 'bg-secondary text-foreground/80'
          }`}
        >
          {type.label}
        </button>
      ))}
    </div>
  )
}
