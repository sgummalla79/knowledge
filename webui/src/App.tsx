import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ComingSoonPage } from './components/ComingSoonPage'
import { NavBar } from './components/NavBar'
import { SettingsTabs } from './components/SettingsTabs'
import { ToastProvider } from './components/ToastProvider'
import { BrowsePage } from './pages/BrowsePage'
import { CategoryPage } from './pages/CategoryPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { DashboardPage } from './pages/DashboardPage'
import { HomePage } from './pages/HomePage'
import { ItemPage } from './pages/ItemPage'
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

            <Route element={<NavBar />}>
              <Route index element={<HomePage />} />
              <Route path="browse" element={<BrowsePage />} />
              <Route path="category/:slug" element={<CategoryPage />} />
              <Route path="item/:id" element={<ItemPage />} />
              <Route
                path="search"
                element={
                  <ComingSoonPage
                    eyebrow="Library"
                    title="Search"
                    description="Retrieval search is being built next."
                  />
                }
              />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="upload" element={<UploadPage />} />
              <Route
                path="settings/data-model"
                element={
                  <ComingSoonPage
                    eyebrow="Reference"
                    title="Data model"
                    description="The schema reference diagram is being rebuilt against the current data model next."
                  />
                }
              />

              <Route element={<SettingsTabs />}>
                <Route
                  path="org/settings"
                  element={
                    <ComingSoonPage
                      eyebrow="Org settings"
                      title="General"
                      description="Org name and description settings are being built next."
                    />
                  }
                />
                <Route
                  path="org/members"
                  element={
                    <ComingSoonPage
                      eyebrow="Org settings"
                      title="Members & access"
                      description="Member management is being built next."
                    />
                  }
                />
                <Route
                  path="org/shelves"
                  element={
                    <ComingSoonPage
                      eyebrow="Org settings"
                      title="Shelves"
                      description="Shelf-based access control is being built next."
                    />
                  }
                />
                <Route
                  path="org/embedding-models"
                  element={
                    <ComingSoonPage
                      eyebrow="Org settings"
                      title="Embedding models"
                      description="The embedding model registry is being built next."
                    />
                  }
                />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}
