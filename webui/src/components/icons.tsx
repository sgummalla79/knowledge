type IconProps = { className?: string }

const base = { viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', strokeWidth: 1.3, 'aria-hidden': true }

export function LibraryIcon({ className }: IconProps) {
  // Fixed multi-color fills (not currentColor) — a deliberate flat-color bookshelf illustration,
  // matching the colorful brand-icon.png already used elsewhere, not a monochrome line icon.
  return (
    <svg className={className} viewBox="0 0 280.027 280.027" aria-hidden>
      <path fill="#3F95D4" d="M52.505,35.003h35.003c4.839,0,8.751,3.929,8.751,8.768v175c0,4.839-3.912,8.751-8.751,8.751H52.505 c-4.839,0-8.751-3.912-8.751-8.751V43.763C43.754,38.933,47.666,35.003,52.505,35.003z" />
      <path fill="#367FB4" d="M61.256,218.771V43.763c0-4.83,3.912-8.76,8.751-8.76H52.505c-4.839,0-8.751,3.929-8.751,8.76 v175.008c0,4.839,3.912,8.751,8.751,8.751h17.502C65.168,227.522,61.256,223.602,61.256,218.771z" />
      <path fill="#D99666" d="M0,227.522h280.027v52.505H0V227.522z" />
      <path fill="#F7CB8B" d="M43.754,166.266h52.505v35.021H43.754V166.266z" />
      <path fill="#349886" d="M105.01,0h52.505c4.839,0,8.751,3.929,8.751,8.768v210.003c0,4.839-3.912,8.751-8.751,8.751H105.01 c-4.839,0-8.751-3.912-8.751-8.751V8.76C96.259,3.929,100.171,0,105.01,0z" />
      <path fill="#9ACCC3" d="M122.512,192.528h17.502V70.007h-17.502C122.512,70.007,122.512,192.528,122.512,192.528z M122.512,35.003v17.502h17.502V35.003H122.512z" />
      <path fill="#E2574C" d="M175.017,52.505h52.505c4.839,0,8.751,3.929,8.751,8.751v157.515c0,4.839-3.912,8.751-8.751,8.751 h-52.505c-4.839,0-8.751-3.912-8.751-8.751V61.256C166.266,56.434,170.178,52.505,175.017,52.505z" />
      <rect x="43.754" y="166.266" fill="#D2AD77" width="17.502" height="35.021" />
      <path fill="#2C8172" d="M113.761,218.771V8.76c0-4.83,3.912-8.76,8.751-8.76H105.01c-4.839,0-8.751,3.929-8.751,8.76 v210.012c0,4.839,3.912,8.751,8.751,8.751h17.502C117.673,227.522,113.761,223.602,113.761,218.771z" />
      <path fill="#C04A40" d="M183.768,218.771V61.256c0-4.822,3.912-8.751,8.751-8.751h-17.502c-4.839,0-8.751,3.929-8.751,8.751 v157.515c0,4.839,3.912,8.751,8.751,8.751h17.502C187.68,227.522,183.768,223.602,183.768,218.771z" />
      <path fill="#F7CB8B" d="M166.266,140.014h70.007V105.01h-70.007V140.014z M166.266,87.509v8.768h70.007v-8.768H166.266z" />
      <rect x="166.266" y="87.509" fill="#D2AD77" width="17.502" height="8.768" />
      <rect x="166.266" y="105.01" fill="#D2AD77" width="17.502" height="35.003" />
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

export function SearchIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M13.25 13.25 10.4 10.4" strokeLinecap="round" />
    </svg>
  )
}

export function UploadIcon({ className }: IconProps) {
  return (
    <svg className={className} {...base}>
      <path d="M8 10.5v-8M4.5 5.75 8 2.25l3.5 3.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2.5 10.5v2a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-2" strokeLinecap="round" />
    </svg>
  )
}

export function MoreIcon({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <circle cx="8" cy="3.25" r="1.35" />
      <circle cx="8" cy="8" r="1.35" />
      <circle cx="8" cy="12.75" r="1.35" />
    </svg>
  )
}
