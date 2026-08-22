import { NavLink, Outlet } from 'react-router-dom'

const LINKS = [
  { to: '/org/settings', label: 'User settings' },
  { to: '/org/members', label: 'Members & access' },
  { to: '/org/profiles', label: 'Profiles' },
  { to: '/org/shelves', label: 'Shelves' },
  { to: '/org/categories', label: 'Data categories' },
  { to: '/org/embedding-models', label: 'Embedding model' },
  { to: '/org/applications', label: 'Connected applications' },
  { to: '/org/mcp', label: 'MCP' },
]

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-sm px-3 py-2 text-sm ${
    isActive ? 'bg-accent text-accent-foreground' : 'text-foreground/80 hover:bg-secondary'
  }`

// Same sidebar + content layout as BrowsePage's FilterSidebar (w-56 shrink-0 aside, flex-1
// content) — settings has enough sections now that a horizontal tab row wrapped awkwardly.
export function SettingsLayout() {
  return (
    <div className="py-12">
      <div className="flex gap-10">
        <aside className="w-56 shrink-0">
          <nav className="flex flex-col gap-0.5">
            {LINKS.map((link) => (
              <NavLink key={link.to} to={link.to} className={linkClass}>
                {link.label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
