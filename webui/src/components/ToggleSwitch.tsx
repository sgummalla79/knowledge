interface Props {
  checked: boolean
  disabled?: boolean
  label: string
  onClick: (event: React.MouseEvent) => void
}

export function ToggleSwitch({ checked, disabled, label, onClick }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={`toggle-switch ${checked ? 'on' : ''}`}
      disabled={disabled}
      onClick={onClick}
    >
      <span className="toggle-knob" />
    </button>
  )
}
