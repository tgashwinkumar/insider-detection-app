import { Outlet } from 'react-router-dom'
import Navbar from '../Navbar/Navbar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-background font-body">
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-border mt-16 py-6">
        <p className="text-center text-muted text-xs font-data">
          Powered by Polymarket on-chain data · Real-time detection via OrderFilled events
        </p>
      </footer>
    </div>
  )
}
