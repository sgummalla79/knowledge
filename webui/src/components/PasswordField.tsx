import { useState } from 'react'
import { EyeIcon, EyeOffIcon } from './icons'

interface Props {
  id: string
  placeholder: string
  value: string
  onChange: (value: string) => void
  autoFocus?: boolean
}

export function PasswordField({ id, placeholder, value, onChange, autoFocus }: Props) {
  const [visible, setVisible] = useState(false)

  return (
    <div className="relative">
      <input
        id={id}
        type={visible ? 'text' : 'password'}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoFocus={autoFocus}
        className="w-full rounded-sm border border-border bg-secondary px-4 py-2.5 pr-11 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        aria-label={visible ? 'Hide password' : 'Show password'}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
      >
        {visible ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  )
}
