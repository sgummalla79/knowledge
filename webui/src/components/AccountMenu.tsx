import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronUpDownIcon, GearIcon, InfoIcon, LogoutIcon } from './icons'
import { currentUsername } from '../api/shell'
import { signOut } from '../api/auth'

export function AccountMenu() {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const username = currentUsername()

  useEffect(() => {
    if (!open) return
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  async function handleSignOut() {
    await signOut()
    window.location.href = '/login'
  }

  return (
    <div className="account-menu" ref={containerRef}>
      {open && (
        <div className="account-menu-popover">
          <div className="account-menu-user">{username}</div>
          <Link to="/settings" className="account-menu-item">
            <GearIcon />
            Settings
          </Link>
          <a href="/api-docs" className="account-menu-item">
            <InfoIcon />
            About
          </a>
          <button type="button" className="account-menu-item account-menu-item-destructive" onClick={handleSignOut}>
            <LogoutIcon />
            Sign out
          </button>
        </div>
      )}
      <button type="button" className="account-menu-trigger" onClick={() => setOpen((current) => !current)}>
        <span className="account-avatar">{username.slice(0, 1).toUpperCase() || '?'}</span>
        <span className="account-name">{username}</span>
        <ChevronUpDownIcon className="account-chevron" />
      </button>
    </div>
  )
}
