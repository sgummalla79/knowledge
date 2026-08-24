import { useEffect, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { bootstrap, currentOrgSlug } from './api/shell'
import { NavBar } from './components/NavBar'
import { SetupLayout } from './components/SetupLayout'
import { UserSettingsLayout } from './components/UserSettingsLayout'
import { ToastProvider } from './components/ToastProvider'
import { BrowsePage } from './pages/BrowsePage'
import { CategoriesSettingsPage } from './pages/CategoriesSettingsPage'
import { CategoryPage } from './pages/CategoryPage'
import { AuthorizePage } from './pages/AuthorizePage'
import { ApiKeysPage } from './pages/ApiKeysPage'
import { ApplicationCreatePage } from './pages/ApplicationCreatePage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { ConnectedApplicationsPage } from './pages/ConnectedApplicationsPage'
import { DashboardPage } from './pages/DashboardPage'
import { EmbeddingModelsPage } from './pages/EmbeddingModelsPage'
import { HomePage } from './pages/HomePage'
import { ItemPage } from './pages/ItemPage'
import { MCPSettingsPage } from './pages/MCPSettingsPage'
import { OrgSettingsPage } from './pages/OrgSettingsPage'
import { ProfileFormPage } from './pages/ProfileFormPage'
import { ProfilesSettingsPage } from './pages/ProfilesSettingsPage'
import { SearchPage } from './pages/SearchPage'
import { ShelvesSettingsPage } from './pages/ShelvesSettingsPage'
import { SignInPage } from './pages/SignInPage'
import { SignUpPage } from './pages/SignUpPage'
import { UploadPage } from './pages/UploadPage'
import { UserSettingsPage } from './pages/UserSettingsPage'

const queryClient = new QueryClient()

// Routes reachable without a session — everything else lives under the NavBar route tree below
// and requires one.
const PUBLIC_PATHS = ['/sign-in', '/sign-up', '/change-password', '/oauth/authorize']

export default function App() {
  const [ready, setReady] = useState(false)

  // bootstrap() fetches the CSRF token + session (GET /csrf-token, GET /session) once before
  // anything renders — this API injects nothing into the page anymore (see this repo's CLAUDE.md
  // session history on the standalone-API change), so this replaces what used to be available
  // synchronously the instant the served HTML shell loaded. currentOrgSlug()/currentUsername()/
  // currentOrgId() below all read from that fetched (or absent, if not logged in) session.
  useEffect(() => {
    void bootstrap().finally(() => setReady(true))
  }, [])

  if (!ready) return null

  const orgSlug = currentOrgSlug()

  if (orgSlug) {
    // The session's *real* org slug — never derived from the URL itself — so a mismatch here
    // means the browser's address bar is stale (an old bookmark, a manually edited URL, a next=
    // redirect built before login resolved which org this identity belongs to). Corrects silently
    // to the org's own home rather than trying to preserve whatever sub-path was requested, since
    // a wrong org's deep link (e.g. an item id) wouldn't resolve to anything meaningful in the
    // real org anyway.
    const expectedPrefix = `/${orgSlug}`
    const { pathname } = window.location
    if (pathname !== expectedPrefix && !pathname.startsWith(`${expectedPrefix}/`)) {
      window.location.replace(expectedPrefix)
      return null
    }
  } else {
    // No session — every route below except the public auth pages requires one. Without this
    // check the protected route tree (NavBar/HomePage/...) would mount anyway, fire its data
    // queries unauthenticated, and only bounce to /sign-in once those queries 401 (client.ts) —
    // a visible flash of the home page before the redirect. Redirecting here, before the router
    // ever mounts, matches the org-slug correction above: skip trying to preserve the requested
    // path, since it wasn't reachable without a session anyway.
    const { pathname } = window.location
    const isPublicPath = PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`))
    if (!isPublicPath) {
      window.location.replace('/sign-in')
      return null
    }
  }

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* basename is the single place the org slug enters routing — every existing absolute
            Link/navigate call (e.g. to="/browse") is automatically prefixed and matched against it
            by React Router, so no individual route/link needs to know about the org slug at all.
            Pre-login pages (sign-in/sign-up/change-password/oauth/authorize) get a 401 from
            GET /session, so orgSlug stays null and basename is unset for them — same
            BrowserRouter, just a fresh mount once bootstrap() re-resolves after login, since every
            login/logout boundary is already a full page reload (see webui/src/api/auth.ts). */}
        <BrowserRouter basename={orgSlug ? `/${orgSlug}` : undefined}>
          <Routes>
            <Route path="/sign-in" element={<SignInPage />} />
            <Route path="/sign-up" element={<SignUpPage />} />
            <Route path="/change-password" element={<ChangePasswordPage />} />
            <Route path="/oauth/authorize" element={<AuthorizePage />} />

            <Route element={<NavBar />}>
              <Route index element={<HomePage />} />
              <Route path="browse" element={<BrowsePage />} />
              <Route path="category/:slug" element={<CategoryPage />} />
              <Route path="item/:id" element={<ItemPage />} />
              <Route path="search" element={<SearchPage />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="upload" element={<UploadPage />} />

              <Route element={<UserSettingsLayout />}>
                <Route path="user/profile" element={<UserSettingsPage />} />
                <Route path="user/api-keys" element={<ApiKeysPage />} />
              </Route>

              <Route element={<SetupLayout />}>
                <Route path="setup/users" element={<OrgSettingsPage />} />
                <Route path="setup/profiles" element={<ProfilesSettingsPage />} />
                <Route path="setup/profiles/new" element={<ProfileFormPage />} />
                <Route path="setup/profiles/:id/edit" element={<ProfileFormPage />} />
                <Route path="setup/shelves" element={<ShelvesSettingsPage />} />
                <Route path="setup/categories" element={<CategoriesSettingsPage />} />
                <Route path="setup/embedding-models" element={<EmbeddingModelsPage />} />
                <Route path="setup/applications" element={<ConnectedApplicationsPage />} />
                <Route path="setup/applications/new" element={<ApplicationCreatePage />} />
                <Route path="setup/mcp" element={<MCPSettingsPage />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}
