import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { NavBar } from './components/NavBar'
import { SettingsLayout } from './components/SettingsLayout'
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
import { GeneralSettingsPage } from './pages/GeneralSettingsPage'
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

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
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
              <Route path="account/api-keys" element={<ApiKeysPage />} />

              <Route element={<SettingsLayout />}>
                <Route path="org/settings" element={<GeneralSettingsPage />} />
                <Route path="org/members" element={<OrgSettingsPage />} />
                <Route path="org/profiles" element={<ProfilesSettingsPage />} />
                <Route path="org/profiles/new" element={<ProfileFormPage />} />
                <Route path="org/profiles/:id/edit" element={<ProfileFormPage />} />
                <Route path="org/shelves" element={<ShelvesSettingsPage />} />
                <Route path="org/categories" element={<CategoriesSettingsPage />} />
                <Route path="org/embedding-models" element={<EmbeddingModelsPage />} />
                <Route path="org/applications" element={<ConnectedApplicationsPage />} />
                <Route path="org/applications/new" element={<ApplicationCreatePage />} />
                <Route path="org/mcp" element={<MCPSettingsPage />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}
