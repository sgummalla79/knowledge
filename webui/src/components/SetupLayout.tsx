import { NavLink, Outlet } from 'react-router-dom'

const LINKS = [
  { to: '/setup/users', label: 'Users' },
  { to: '/setup/profiles', label: 'Profiles' },
  { to: '/setup/shelves', label: 'Shelves' },
  { to: '/setup/categories', label: 'Data categories' },
  { to: '/setup/embedding-models', label: 'Embedding model' },
  { to: '/setup/applications', label: 'Connected applications' },
  { to: '/setup/mcp', label: 'MCP' },
]

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-sm px-3 py-2 text-sm ${
    isActive ? 'bg-accent text-accent-foreground' : 'text-foreground/80 hover:bg-secondary'
  }`

// Org-admin settings (/setup/...), split out from personal settings (UserSettingsLayout,
// /user/...) — same sidebar + content layout as BrowsePage's FilterSidebar (w-56 shrink-0 aside,
// flex-1 content).
export function SetupLayout() {
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
