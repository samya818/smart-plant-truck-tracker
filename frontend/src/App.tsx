import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Dashboard from '@/pages/Dashboard';
import MobilePage from '@/pages/MobilePage';
import StatistiquesPage from '@/pages/StatistiquesPage';
import ConfirmationPage from '@/pages/ConfirmationPage';
import { OfflineBanner } from '@/components/OfflineBanner';
import { LayoutDashboard, Smartphone, BarChart2, ShieldCheck } from 'lucide-react';

const API_BASE = '';

/** Badge rouge animé affiché sur le lien "Confirmation" quand des events sont en attente. */
function PendingBadge() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/events/pending-confirmation/count`);
        if (res.ok) {
          const data = await res.json();
          setCount(data.count ?? 0);
        }
      } catch { /* silencieux */ }
    };
    poll();
    const id = setInterval(poll, 20_000);
    return () => clearInterval(id);
  }, []);

  if (count === 0) return null;
  return (
    <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-red-500 text-white text-[10px] font-extrabold animate-pulse">
      {count > 9 ? '9+' : count}
    </span>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-100 flex flex-col">
        {/* ── Bandeau hors-ligne PWA ── */}
        <OfflineBanner />
        {/* ── Barre de navigation principale ── */}
        <nav className="bg-white border-b border-gray-200 px-6 py-0 flex items-center shadow-sm sticky top-0 z-50">

          {/* Logo / Identité */}
          <div className="flex items-center gap-2.5 mr-8 py-3 border-r border-gray-100 pr-8">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <span className="text-white font-extrabold text-xs">LH</span>
            </div>
            <div>
              <div className="text-sm font-extrabold text-gray-900 leading-tight">LafargeHolcim</div>
              <div className="text-[10px] text-gray-400 leading-tight">Meknès · Tracker Camions</div>
            </div>
          </div>

          {/* Liens de navigation */}
          <div className="flex items-center h-full">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-4 text-sm font-semibold border-b-2 transition-all duration-150 ${
                  isActive
                    ? 'border-blue-600 text-blue-700 bg-blue-50/50'
                    : 'border-transparent text-gray-500 hover:text-gray-800 hover:bg-gray-50'
                }`
              }
            >
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </NavLink>

            <NavLink
              to="/statistiques"
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-4 text-sm font-semibold border-b-2 transition-all duration-150 ${
                  isActive
                    ? 'border-violet-600 text-violet-700 bg-violet-50/50'
                    : 'border-transparent text-gray-500 hover:text-gray-800 hover:bg-gray-50'
                }`
              }
            >
              <BarChart2 className="w-4 h-4" />
              Statistiques
            </NavLink>

            <NavLink
              to="/mobile"
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-4 text-sm font-semibold border-b-2 transition-all duration-150 ${
                  isActive
                    ? 'border-green-600 text-green-700 bg-green-50/50'
                    : 'border-transparent text-gray-500 hover:text-gray-800 hover:bg-gray-50'
                }`
              }
            >
              <Smartphone className="w-4 h-4" />
              Interface Mobile
            </NavLink>

            {/* ── Lien Confirmation OCR avec badge ── */}
            <NavLink
              to="/confirmation"
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-4 text-sm font-semibold border-b-2 transition-all duration-150 ${
                  isActive
                    ? 'border-amber-600 text-amber-700 bg-amber-50/50'
                    : 'border-transparent text-gray-500 hover:text-gray-800 hover:bg-gray-50'
                }`
              }
            >
              <ShieldCheck className="w-4 h-4" />
              Confirmation OCR
              <PendingBadge />
            </NavLink>
          </div>
        </nav>

        {/* ── Contenu de la page ── */}
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/statistiques" element={<StatistiquesPage />} />
            <Route path="/mobile" element={<MobilePage />} />
            <Route path="/confirmation" element={<ConfirmationPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
