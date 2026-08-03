import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LibrariesPage } from './pages/LibrariesPage'
import { LibraryDetailPage } from './pages/LibraryDetailPage'
import './app.css'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/workspace">
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<LibrariesPage />} />
            <Route path="libraries/:libraryId" element={<LibraryDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
