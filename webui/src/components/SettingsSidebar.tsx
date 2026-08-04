import { Link, useLocation } from 'react-router-dom'
import { AccountMenu } from './AccountMenu'
import { ArrowLeftIcon, DocIcon, GearIcon, GlobeIcon, GridIcon, LayersIcon, TableIcon } from './icons'

export function SettingsSidebar() {
  const location = useLocation()

  return (
    <aside className="rail">
      <div className="rail-brand">
        <GearIcon />
        <span>Settings</span>
      </div>

      <div className="rail-back-section">
        <Link to="/workspace" className="rail-item">
          <ArrowLeftIcon />
          <span>Back to Knowledge</span>
        </Link>
      </div>

      <nav className="rail-list settings-nav">
        <div className="nav-group-label">Embeddings</div>
        <Link to="/settings" className={`rail-item ${location.pathname === '/settings' ? 'active' : ''}`}>
          <LayersIcon />
          <span>Providers</span>
        </Link>

        <div className="nav-group-label">Clients</div>
        <Link to="/settings/applications" className={`rail-item ${location.pathname === '/settings/applications' ? 'active' : ''}`}>
          <GridIcon />
          <span>Applications</span>
        </Link>

        <div className="nav-group-label">Configuration</div>
        <Link to="/settings/web-crawler" className={`rail-item ${location.pathname === '/settings/web-crawler' ? 'active' : ''}`}>
          <GlobeIcon />
          <span>Web Crawler</span>
        </Link>

        <div className="nav-group-label">Reference</div>
        <Link to="/settings/api-docs" className={`rail-item ${location.pathname === '/settings/api-docs' ? 'active' : ''}`}>
          <DocIcon />
          <span>API Documentation</span>
        </Link>
        <Link to="/settings/data-model" className={`rail-item ${location.pathname === '/settings/data-model' ? 'active' : ''}`}>
          <TableIcon />
          <span>Data Model</span>
        </Link>
      </nav>

      <div className="rail-footer">
        <AccountMenu />
      </div>
    </aside>
  )
}
