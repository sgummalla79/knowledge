import { Suspense, lazy } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { SettingsLayout } from './components/SettingsLayout'
import { ToastProvider } from './components/ToastProvider'
import { IngestionProvider } from './components/IngestionProvider'
import { LibrariesPage } from './pages/LibrariesPage'
import { LibraryDetailPage } from './pages/LibraryDetailPage'
import { LoginPage } from './pages/LoginPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { ProvidersPage } from './pages/ProvidersPage'
import { ApplicationsPage } from './pages/ApplicationsPage'
import { WebCrawlerPage } from './pages/WebCrawlerPage'
import { ApiDocsPage } from './pages/ApiDocsPage'
import { AuthorizePage } from './pages/AuthorizePage'
import './app.css'

// Lazy-loaded: mermaid (and its per-diagram-type sub-renderers) is a genuinely heavy dependency
// that only this one page needs — a static import would put its whole module graph in every
// route's bundle, including /login, for a page most sessions never visit.
const DataModelPage = lazy(() => import('./pages/DataModelPage').then((m) => ({ default: m.DataModelPage })))

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <IngestionProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/change-password" element={<ChangePasswordPage />} />
              <Route path="/oauth/authorize" element={<AuthorizePage />} />
              <Route path="/settings" element={<SettingsLayout />}>
                <Route index element={<ProvidersPage />} />
                <Route path="applications" element={<ApplicationsPage />} />
                <Route path="web-crawler" element={<WebCrawlerPage />} />
                <Route path="api-docs" element={<ApiDocsPage />} />
                <Route
                  path="data-model"
                  element={
                    <Suspense fallback={<p className="subtitle">Loading…</p>}>
                      <DataModelPage />
                    </Suspense>
                  }
                />
              </Route>
              <Route path="/workspace" element={<Layout />}>
                <Route index element={<LibrariesPage />} />
                <Route path="libraries/:libraryId" element={<LibraryDetailPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </IngestionProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}
