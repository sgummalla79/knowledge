import { NavLink, Outlet } from 'react-router-dom'

const TABS = [
  { to: '/org/settings', label: 'General' },
  { to: '/org/members', label: 'Members & access' },
  { to: '/org/shelves', label: 'Shelves' },
  { to: '/org/embedding-models', label: 'Embedding model' },
]

const tabClass = ({ isActive }: { isActive: boolean }) =>
  `block whitespace-nowrap pb-3.5 text-sm ${
    isActive ? 'border-b-2 border-primary text-primary' : 'text-muted-foreground hover:text-foreground'
  }`

export function SettingsTabs() {
  return (
    <div>
      <div className="mb-8 flex gap-6 overflow-x-auto border-b border-border">
        {TABS.map((tab) => (
          <NavLink key={tab.to} to={tab.to} className={tabClass}>
            {tab.label}
          </NavLink>
        ))}
      </div>
      <Outlet />
    </div>
  )
}
