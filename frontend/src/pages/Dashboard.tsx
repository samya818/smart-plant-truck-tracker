import { useEffect, useState } from 'react';
import { getDashboardStats, getActiveEvents, getPosteConfigs, updatePosteConfig } from '@/services/api';
import { useWebSocket } from '@/hooks/useWebSocket';
import { TruckCard } from '@/components/TruckCard';
import { AlertBanner } from '@/components/AlertBanner';
import { StatsChart } from '@/components/StatsChart';
import type { DashboardStats, Event, PosteConfig } from '@/types';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/live';

const posteLabels: Record<string, string> = {
  porte_usine: 'Porte Usine', parking: 'Parking',
  bascule: 'Bascule', ensachage: 'Ensachage',
};

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [posteConfigs, setPosteConfigs] = useState<PosteConfig[]>([]);
  const { lastMessage, isConnected } = useWebSocket(WS_URL);

  const reloadData = () => {
    getDashboardStats().then(setStats);
    getActiveEvents().then(setEvents);
    getPosteConfigs().then(setPosteConfigs);
  };

  useEffect(() => {
    reloadData();
  }, []);

  useEffect(() => {
    if (lastMessage) {
      reloadData();
    }
  }, [lastMessage]);

  const handleToggleMode = (posteName: string, currentMode: 'camera' | 'agent' | 'hybrid') => {
    const modes: ('camera' | 'agent' | 'hybrid')[] = ['camera', 'agent', 'hybrid'];
    const nextIdx = (modes.indexOf(currentMode) + 1) % modes.length;
    const nextMode = modes[nextIdx];
    
    updatePosteConfig(posteName, { capture_mode: nextMode }).then((updated) => {
      setPosteConfigs(prev => prev.map(p => p.poste === posteName ? updated : p));
    }).catch(err => alert(`Erreur de modification du mode: ${err.message}`));
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">🏭 Espace Superviseur — LafargeHolcim Meknès</h1>
          <p className="text-sm text-gray-500">Traçabilité bi-mode et optimisation des flux camions</p>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
          {isConnected ? '● WebSocket Connecté' : '● WebSocket Déconnecté'}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KPICard title="Camions en cours" value={stats?.camions_en_cours || 0} color="blue" />
        <KPICard title="Aujourd'hui" value={stats?.camions_aujourdhui || 0} color="green" />
        <KPICard title="Temps moyen cycle" value={`${Math.round(stats?.temps_moyen_cycle || 0)} min`} color="purple" />
        <KPICard title="Alertes actives" value={stats?.alertes_actives || 0} color="red" />
      </div>

      {stats?.poste_bloquant && <AlertBanner message={`⚠️ Poste bloquant : ${stats.poste_bloquant}`} type="warning" />}
      {stats?.top_cause_retard && <AlertBanner message={`🔥 Cause fréquente : ${stats.top_cause_retard}`} type="info" />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Liste des camions et photos */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-800">🚚 Suivi Temps Réel & Photos des Camions</h2>
          {events.length === 0 ? (
            <p className="text-gray-500 italic text-sm">Aucun camion en cours dans l'usine.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {events.map(ev => (
                <TruckCard key={ev.id} event={ev} />
              ))}
            </div>
          )}
        </div>

        {/* Panel de configuration des modes par poste */}
        <div className="bg-white rounded-lg shadow p-6 flex flex-col justify-between">
          <div>
            <h2 className="text-lg font-semibold mb-4 text-gray-800">⚙️ Configuration des Postes (Bi-Mode)</h2>
            <p className="text-xs text-gray-500 mb-4">
              Cliquez sur le mode d'un poste pour basculer à chaud entre Caméra OCR, Agent Mobile ou mode Hybride.
            </p>
            <div className="space-y-4">
              {posteConfigs.map((cfg) => (
                <div key={cfg.poste} className="flex items-center justify-between border-b pb-3 last:border-0 last:pb-0">
                  <div>
                    <span className="font-semibold text-gray-700">
                      {posteLabels[cfg.poste] || cfg.poste}
                    </span>
                    <p className="text-xs text-gray-400">
                      {cfg.camera_url ? `Flux: ${cfg.camera_url}` : 'Pas de caméra configurée'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleToggleMode(cfg.poste, cfg.capture_mode)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider shadow-sm transition-all duration-200 hover:shadow ${
                      cfg.capture_mode === 'camera' 
                        ? 'bg-blue-100 text-blue-800 border border-blue-300' 
                        : cfg.capture_mode === 'hybrid'
                        ? 'bg-purple-100 text-purple-800 border border-purple-300'
                        : 'bg-orange-100 text-orange-800 border border-orange-300'
                    }`}
                  >
                    {cfg.capture_mode === 'camera' ? '📷 Caméra' : cfg.capture_mode === 'hybrid' ? '♻️ Hybride' : '📱 Agent'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <StatsChart />
    </div>
  );
}

function KPICard({ title, value, color }: { title: string; value: string | number; color: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-900', green: 'bg-green-50 text-green-900',
    purple: 'bg-purple-50 text-purple-900', red: 'bg-red-50 text-red-900',
  };
  return (
    <div className={`rounded-lg p-4 ${colors[color]}`}>
      <p className="text-sm opacity-75">{title}</p>
      <p className="text-3xl font-bold">{value}</p>
    </div>
  );
}
