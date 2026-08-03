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
    <div className="field-wrap">
      <input
        id={id}
        className="field-pill"
        type={visible ? 'text' : 'password'}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoFocus={autoFocus}
      />
      <button
        type="button"
        className="field-icon-btn"
        onClick={() => setVisible((current) => !current)}
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  )
}
