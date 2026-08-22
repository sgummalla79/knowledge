import { useEffect, useRef, useState } from 'react'
import { CheckIcon, ChevronDownIcon } from './icons'

export interface SelectOption {
  value: string
  label: string
}

interface Props {
  id?: string
  value: string
  options: SelectOption[]
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  // Sizing/width only (padding, text size, w-full vs. inline) — every other visual concern
  // (border, radius, background, focus ring) is fixed by this component so every dropdown in the
  // app opens and looks the same way, native <select> popups couldn't guarantee that consistently.
  className?: string
}

// Custom-styled replacement for native <select> — browsers render a native <select>'s open popup
// themselves (see the color-scheme fix elsewhere in this app), which can drift out of sync with a
// dark-themed, custom-radius page and never matches this app's own dropdown panel styling. This
// renders the options list itself, positioned below the trigger, so it always matches.
export function Select({ id, value, options, onChange, placeholder, disabled, className }: Props) {
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const selected = options.find((option) => option.value === value)

  useEffect(() => {
    if (!open) return
    function handlePointerDown(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  function selectOption(optionValue: string) {
    onChange(optionValue)
    setOpen(false)
  }

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        id={id}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`flex items-center justify-between gap-2 rounded-sm border bg-secondary text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60 ${open ? 'border-ring ring-2 ring-ring' : 'border-border'} ${className ?? ''}`}
      >
        <span className={selected ? 'text-foreground' : 'text-muted-foreground'}>{selected?.label ?? placeholder}</span>
        <ChevronDownIcon className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <ul
          role="listbox"
          className="absolute z-20 mt-1.5 max-h-60 w-full min-w-max overflow-auto rounded-sm border border-border bg-popover py-1 shadow-lg"
        >
          {options.map((option) => (
            <li
              key={option.value}
              role="option"
              aria-selected={option.value === value}
              onClick={() => selectOption(option.value)}
              className={`flex cursor-pointer items-center justify-between gap-3 px-4 py-2.5 text-[15px] hover:bg-accent ${option.value === value ? 'font-medium text-foreground' : 'text-foreground/80'}`}
            >
              {option.label}
              {option.value === value && <CheckIcon className="h-4 w-4 shrink-0 text-primary" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
