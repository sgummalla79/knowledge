import { Link } from 'react-router-dom'
import { AccountMenu } from './AccountMenu'
import { ArrowLeftIcon, DocIcon, GearIcon, GlobeIcon, GridIcon, LayersIcon, TableIcon } from './icons'

export function SettingsSidebar() {
  return (
    <aside className="rail">
      <div className="rail-brand">
        <GearIcon />
        <span>Settings</span>
      </div>
      <Link to="/workspace" className="rail-item">
        <ArrowLeftIcon />
        <span>Back to Workspace</span>
      </Link>

      <nav className="rail-list settings-nav">
        <div className="nav-group-label">AI Setup</div>
        <Link to="/settings" className="rail-item active">
          <LayersIcon />
          <span>Providers</span>
        </Link>

        <div className="nav-group-label">Clients</div>
        <a href="/dashboard" className="rail-item">
          <GridIcon />
          <span>Applications</span>
        </a>

        <div className="nav-group-label">Configuration</div>
        <a href="/dashboard/configuration" className="rail-item">
          <GlobeIcon />
          <span>Web Crawler</span>
        </a>

        <div className="nav-group-label">Reference</div>
        <a href="/api-docs" className="rail-item">
          <DocIcon />
          <span>API Documentation</span>
        </a>
        <a href="/dashboard/schema" className="rail-item">
          <TableIcon />
          <span>Data Model</span>
        </a>
      </nav>

      <div className="rail-footer">
        <AccountMenu />
      </div>
    </aside>
  )
}
