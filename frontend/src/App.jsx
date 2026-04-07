import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import HomePage from './pages/HomePage'
import MarketDetailPage from './pages/MarketDetailPage'
import AlertsPage from './pages/AlertsPage'
import SearchResolvePage from './pages/SearchResolvePage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/search" element={<SearchResolvePage />} />
          <Route path="/market/:conditionId" element={<MarketDetailPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
