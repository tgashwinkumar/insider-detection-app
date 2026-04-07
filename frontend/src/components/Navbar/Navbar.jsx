import { NavLink } from 'react-router-dom'
import { useState } from 'react'
import SearchInput from '../SearchInput/SearchInput'

export default function Navbar() {
  const [searchOpen, setSearchOpen] = useState(false)

  return (
    <nav className="sticky top-0 z-40 bg-background/90 backdrop-blur border-b border-border">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-6">
        {/* Logo */}
        <NavLink to="/" className="flex items-center gap-2 shrink-0">
          <span className="text-2xl">🔥</span>
          <span className="text-brand font-headline font-bold text-lg tracking-tight">
            Sentinel
          </span>
        </NavLink>

        {/* Nav links */}
        <div className="flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `px-3 py-1.5 rounded text-sm font-body transition-colors ${
                isActive ? 'text-white bg-surface2' : 'text-muted hover:text-white'
              }`
            }
          >
            Home
          </NavLink>
          <NavLink
            to="/alerts"
            className={({ isActive }) =>
              `px-3 py-1.5 rounded text-sm font-body transition-colors ${
                isActive ? 'text-white bg-surface2' : 'text-muted hover:text-white'
              }`
            }
          >
            Alerts
          </NavLink>
        </div>

        {/* Compact search (collapses in) */}
        <div className="flex-1 max-w-md ml-auto">
          {searchOpen ? (
            <SearchInput compact autoFocus />
          ) : (
            <button
              onClick={() => setSearchOpen(true)}
              className="ml-auto flex items-center gap-2 text-muted hover:text-white transition-colors text-sm font-body"
            >
              <span className="text-lg">⌕</span>
              <span className="hidden sm:inline">Search markets</span>
            </button>
          )}
        </div>
      </div>
    </nav>
  )
}
