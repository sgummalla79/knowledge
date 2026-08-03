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
  // A real gear/cog silhouette — teeth fused to the body's rim — rather than a sun/asterisk
  // shape (a small circle with thin detached rays), which is what this looked like before.
  return (
    <svg className={className} {...base}>
      <circle cx="8" cy="8" r="3.2" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
        <rect key={deg} x="7.35" y="3.3" width="1.3" height="2.3" rx="0.3" transform={`rotate(${deg} 8 8)`} />
      ))}
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

export function LogoutIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M6.5 1.75H3.75a1 1 0 0 0-1 1v10.5a1 1 0 0 0 1 1H6.5" strokeLinecap="round" />
      <path d="M10.25 11 13.25 8l-3-3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13.25 8H6" strokeLinecap="round" />
    </svg>
  )
}

export function LayersIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M8 1.75 14 5 8 8.25 2 5Z" strokeLinejoin="round" />
      <path d="M2 8.25 8 11.5l6-3.25M2 11.5 8 14.75l6-3.25" strokeLinejoin="round" />
    </svg>
  )
}

export function GlobeIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <circle cx="8" cy="8" r="6.25" />
      <path d="M1.75 8h12.5M8 1.75c1.8 1.8 2.75 4 2.75 6.25S9.8 12.45 8 14.25C6.2 12.45 5.25 10.25 5.25 8S6.2 3.55 8 1.75Z" />
    </svg>
  )
}

export function DocIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M4 1.5h5.5L12 4v9.5a.5.5 0 0 1-.5.5h-7a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5Z" />
      <path d="M4.75 7.5h4.5M4.75 9.75h4.5M4.75 5.25h2" />
    </svg>
  )
}

export function GridIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <rect x="1.75" y="1.75" width="5.25" height="5.25" rx="1" />
      <rect x="9" y="1.75" width="5.25" height="5.25" rx="1" />
      <rect x="1.75" y="9" width="5.25" height="5.25" rx="1" />
      <rect x="9" y="9" width="5.25" height="5.25" rx="1" />
    </svg>
  )
}

export function TableIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <rect x="1.75" y="1.75" width="12.5" height="3.5" rx="0.75" />
      <rect x="1.75" y="6.25" width="12.5" height="3.5" rx="0.75" />
      <rect x="1.75" y="10.75" width="12.5" height="3.5" rx="0.75" />
    </svg>
  )
}
