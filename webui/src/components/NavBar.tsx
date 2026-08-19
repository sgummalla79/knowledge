import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { signOut } from '../api/auth'
import { currentOrgName, currentUsername } from '../api/shell'
import { currentTheme, setTheme } from '../theme'
import { ChevronDownIcon, MoonIcon, SunIcon } from './icons'
import { Logo } from './Logo'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm ${isActive ? 'text-primary' : 'text-foreground/80 hover:text-primary'}`

function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  const letters = parts.length > 1 ? [parts[0][0], parts[parts.length - 1][0]] : [name.slice(0, 2)]
  return letters.join('').toUpperCase()
}

export function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [dark, setDark] = useState(() => currentTheme() === 'dark')
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function toggleTheme() {
    const next = dark ? 'light' : 'dark'
    setTheme(next)
    setDark(next === 'dark')
  }

  const username = currentUsername()
  const orgName = currentOrgName()

  return (
    <div className="min-h-full bg-background">
      <nav className="mx-auto flex max-w-6xl items-center gap-7 px-6 py-4">
        <NavLink to="/" className="mr-auto flex items-center gap-2 text-foreground">
          <Logo className="text-primary" />
          <span className="text-lg font-semibold">Knowledge</span>
        </NavLink>
        <NavLink to="/browse" className={navLinkClass}>
          Browse
        </NavLink>
        <NavLink to="/search" className={navLinkClass}>
          Search
        </NavLink>
        <NavLink to="/dashboard" className={navLinkClass}>
          Dashboard
        </NavLink>
        <NavLink
          to="/upload"
          className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          Contribute
        </NavLink>
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
          className="text-foreground/70 hover:text-foreground"
        >
          {dark ? <SunIcon /> : <MoonIcon />}
        </button>
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="flex items-center gap-1.5"
            aria-label="Account menu"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-[13px] font-semibold text-primary-foreground">
              {username ? initials(username) : '?'}
            </span>
            <ChevronDownIcon className="text-foreground/60" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-[calc(100%+8px)] z-10 min-w-[190px] rounded-sm border border-border bg-popover p-1.5 shadow-lg">
              <div className="mb-1 border-b border-border px-2.5 py-2 text-xs text-muted-foreground">
                {username}
                {orgName ? (
                  <>
                    <br />
                    {orgName}
                  </>
                ) : null}
              </div>
              <NavLink
                to="/org/settings"
                onClick={() => setMenuOpen(false)}
                className="block rounded-sm px-2.5 py-2 text-sm text-foreground hover:bg-secondary"
              >
                Org settings
              </NavLink>
              <button
                type="button"
                onClick={() => void signOut().then(() => (window.location.href = '/sign-in'))}
                className="mt-1 block w-full rounded-sm border-t border-border px-2.5 py-2 pt-2.5 text-left text-sm text-foreground hover:bg-secondary"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </nav>
      <main className="mx-auto max-w-6xl px-6 pb-16">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-6xl px-6 pb-10 pt-10 text-xs text-muted-foreground">
        <div className="flex justify-between border-t border-border pt-6">
          <span>Knowledge — a knowledge library for retrieval-augmented answers.</span>
          <span>© {new Date().getFullYear()} Knowledge</span>
        </div>
      </footer>
    </div>
  )
}
