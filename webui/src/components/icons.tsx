type IconProps = { className?: string }

const base = { viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', strokeWidth: 1.3, 'aria-hidden': true }

export function FolderIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M2 3.5a1 1 0 0 1 1-1h3.5l1.25 1.75H13a1 1 0 0 1 1 1V12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5Z" />
    </svg>
  )
}

export function PlusIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M8 3v10M3 8h10" strokeLinecap="round" />
    </svg>
  )
}

export function PencilIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M10.5 2.5 13.5 5.5 5.5 13.5H2.5v-3Z" strokeLinejoin="round" />
    </svg>
  )
}

export function TrashIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M3 4.5h10M6.5 4.5V3a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1.5M4.5 4.5V13a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1V4.5" />
    </svg>
  )
}

export function GearIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <circle cx="8" cy="8" r="2.1" />
      <path d="M8 1.6v1.7M8 12.7v1.7M14.4 8h-1.7M3.3 8H1.6M12.4 3.6l-1.2 1.2M4.8 11.2l-1.2 1.2M12.4 12.4l-1.2-1.2M4.8 4.8 3.6 3.6" />
    </svg>
  )
}

export function ArrowLeftIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M10.5 13 5.5 8l5-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function EyeIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M1.5 8S4 3 8 3s6.5 5 6.5 5-2.5 5-6.5 5-6.5-5-6.5-5Z" strokeLinejoin="round" />
      <circle cx="8" cy="8" r="1.8" />
    </svg>
  )
}

export function EyeOffIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M1.5 8S4 3 8 3s6.5 5 6.5 5-2.5 5-6.5 5-6.5-5-6.5-5Z" strokeLinejoin="round" />
      <circle cx="8" cy="8" r="1.8" />
      <path d="M2 2l12 12" strokeLinecap="round" />
    </svg>
  )
}

export function ChevronUpDownIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M5 6.5 8 3.5l3 3M5 9.5 8 12.5l3-3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function InfoIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <circle cx="8" cy="8" r="6.25" />
      <path d="M8 7.25v4M8 5.1v.05" strokeLinecap="round" />
    </svg>
  )
}

export function LogoutIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M6.5 1.75H3.75a1 1 0 0 0-1 1v10.5a1 1 0 0 0 1 1H6.5" strokeLinecap="round" />
      <path d="M10.25 11 13.25 8l-3-3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13.25 8H6" strokeLinecap="round" />
    </svg>
  )
}
