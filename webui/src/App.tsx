import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { currentOrgSlug } from './api/shell'
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

export default function App() {
  const orgSlug = currentOrgSlug()

  // __ORG_SLUG__ is only ever injected server-side (app_shell.py) from the session's *real* org —
  // never derived from the URL itself — so a mismatch here means the browser's address bar is
  // stale (an old bookmark, a manually edited URL, a next= redirect built before login resolved
  // which org this identity belongs to). Corrects silently to the org's own home rather than
  // trying to preserve whatever sub-path was requested, since a wrong org's deep link (e.g. an
  // item id) wouldn't resolve to anything meaningful in the real org anyway. Runs before the
  // router ever mounts so there's no flash of a non-matching route.
  if (orgSlug) {
    const expectedPrefix = `/${orgSlug}`
    const { pathname } = window.location
    if (pathname !== expectedPrefix && !pathname.startsWith(`${expectedPrefix}/`)) {
      window.location.replace(expectedPrefix)
      return null
    }
  }

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* basename is the single place the org slug enters routing — every existing absolute
            Link/navigate call (e.g. to="/browse") is automatically prefixed and matched against it
            by React Router, so no individual route/link needs to know about the org slug at all.
            Pre-login pages (sign-in/sign-up/change-password/oauth/authorize) never get an
            __ORG_SLUG__ global, so basename is unset for them — same BrowserRouter, just a fresh
            mount with different globals, since every login/logout boundary is already a full page
            reload (see webui/src/api/auth.ts). */}
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
