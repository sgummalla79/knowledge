import { Outlet } from 'react-router-dom'
import { SettingsSidebar } from './SettingsSidebar'

export function SettingsLayout() {
  return (
    <div className="shell">
      <SettingsSidebar />
      <div className="main main-centered">
        <Outlet />
      </div>
    </div>
  )
}
