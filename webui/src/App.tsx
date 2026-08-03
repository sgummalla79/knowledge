import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LibrariesPage } from './pages/LibrariesPage'
import { LibraryDetailPage } from './pages/LibraryDetailPage'
import { LoginPage } from './pages/LoginPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { SettingsPage } from './pages/SettingsPage'
import './app.css'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/change-password" element={<ChangePasswordPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/workspace" element={<Layout />}>
            <Route index element={<LibrariesPage />} />
            <Route path="libraries/:libraryId" element={<LibraryDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
