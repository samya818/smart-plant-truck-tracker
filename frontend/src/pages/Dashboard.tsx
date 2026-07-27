import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardStats, getActiveEvents, getPosteConfigs, updatePosteConfig } from '@/services/api';
import { useWebSocket } from '@/hooks/useWebSocket';
import { TruckCard } from '@/components/TruckCard';
import { AlertBanner } from '@/components/AlertBanner';
import { StatsChart } from '@/components/StatsChart';
import type { DashboardStats, Event, PosteConfig } from '@/types';
import { Edit2, Check, X, Camera, Smartphone, RefreshCw, BarChart2 } from 'lucide-react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/live';

const posteLabels: Record<string, string> = {
  porte_usine: 'Porte Usine', parking: 'Parking',
  bascule: 'Bascule', ensachage: 'Ensachage',
};

/** Regroupe les événements par truck_id */
function groupEventsByTruck(events: Event[]): Map<number, Event[]> {
  const map = new Map<number, Event[]>();
  for (const ev of events) {
    const list = map.get(ev.truck_id) ?? [];
    list.push(ev);
    map.set(ev.truck_id, list);
  }
  return map;
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [posteConfigs, setPosteConfigs] = useState<PosteConfig[]>([]);
  const [editingPoste, setEditingPoste] = useState<string | null>(null);
  const [tempUrl, setTempUrl] = useState<string>('');
  const { lastMessage, isConnected } = useWebSocket(WS_URL);

  const reloadData = () => {
    getDashboardStats().then(setStats);
    getActiveEvents().then(setEvents);
    getPosteConfigs().then(setPosteConfigs);
  };

  useEffect(() => { reloadData(); }, []);
  useEffect(() => { if (lastMessage) reloadData(); }, [lastMessage]);

  const handleToggleMode = (posteName: string, currentMode: 'camera' | 'agent' | 'hybrid') => {
    const modes: ('camera' | 'agent' | 'hybrid')[] = ['camera', 'agent', 'hybrid'];
    const nextIdx = (modes.indexOf(currentMode) + 1) % modes.length;
    const nextMode = modes[nextIdx];
    updatePosteConfig(posteName, { capture_mode: nextMode }).then((updated) => {
      setPosteConfigs(prev => prev.map(p => p.poste === posteName ? updated : p));
    }).catch(err => alert(`Erreur de modification du mode: ${err.message}`));
  };

  const handleStartEditUrl = (posteName: string, currentUrl: string = '') => {
    setEditingPoste(posteName);
    setTempUrl(currentUrl);
  };

  const handleSaveUrl = (posteName: string) => {
    updatePosteConfig(posteName, { camera_url: tempUrl }).then((updated) => {
      setPosteConfigs(prev => prev.map(p => p.poste === posteName ? updated : p));
      setEditingPoste(null);
    }).catch(err => alert(`Erreur d'enregistrement de l'URL: ${err.message}`));
  };

  // Groupement des événements par camion + séparation en cours / terminés
  const truckGroups = groupEventsByTruck(events);

  // Un camion est "en cours" si son événement le PLUS RÉCENT n'est PAS (porte_usine + sortie)
  const encours: [number, Event[]][] = [];
  const termines: [number, Event[]][] = [];
  for (const [id, evs] of truckGroups.entries()) {
    const sortedEvs = [...evs].sort(
      (a, b) => new Date(a.horodatage).getTime() - new Date(b.horodatage).getTime()
    );
    const lastEvent = sortedEvs[sortedEvs.length - 1];
    const estActuellementSorti = lastEvent && lastEvent.poste === 'porte_usine' && lastEvent.type_event === 'sortie';

    if (estActuellementSorti) termines.push([id, sortedEvs]);
    else encours.push([id, sortedEvs]);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">🏭 Espace Superviseur — LafargeHolcim Meknès</h1>
          <p className="text-sm text-gray-500">Traçabilité bi-mode et optimisation des flux camions</p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/statistiques"
            className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold rounded-lg transition-colors shadow-sm"
          >
            <BarChart2 className="w-4 h-4" />
            📊 Voir les Statistiques
          </Link>
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {isConnected ? '● WebSocket Connecté' : '● WebSocket Déconnecté'}
          </div>
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
        {/* Liste des camions avec timeline complète du cycle */}
        <div className="lg:col-span-2 space-y-6">

          {/* ── Camions EN COURS ── */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-800">🚚 Camions en cours dans l'usine</h2>
              <span className="text-xs font-medium bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                {encours.length} actif{encours.length > 1 ? 's' : ''}
              </span>
            </div>
            {encours.length === 0 ? (
              <p className="text-gray-500 italic text-sm">Aucun camion en cours actuellement.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {encours.map(([truckId, truckEvents]) => {
                  const immat = truckEvents[0]?.truck?.immatriculation || `Camion #${truckId}`;
                  return <TruckCard key={truckId} immatriculation={immat} events={truckEvents} />;
                })}
              </div>
            )}
          </div>

          {/* ── Camions TERMINÉS (dernières 24h) ── */}
          {termines.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-800">✅ Cycles terminés (24h)</h2>
                <span className="text-xs font-medium bg-green-100 text-green-700 px-2 py-1 rounded-full">
                  {termines.length} terminé{termines.length > 1 ? 's' : ''}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {termines.map(([truckId, truckEvents]) => {
                  const immat = truckEvents[0]?.truck?.immatriculation || `Camion #${truckId}`;
                  return <TruckCard key={truckId} immatriculation={immat} events={truckEvents} />;
                })}
              </div>
            </div>
          )}
        </div>

        {/* Panel de configuration des modes par poste */}
        <div className="bg-white rounded-xl shadow p-6 flex flex-col justify-between border border-gray-100">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-800">⚙️ Configuration des Postes (Bi-Mode)</h2>
            </div>
            <p className="text-xs text-gray-500 mb-6">
              Basculez entre Caméra OCR, Agent Mobile ou Hybride et configurez le flux vidéo RTSP/IP de chaque poste.
            </p>
            <div className="space-y-5">
              {posteConfigs.map((cfg) => {
                const isEditing = editingPoste === cfg.poste;
                return (
                  <div key={cfg.poste} className="border-b border-gray-100 pb-4 last:border-0 last:pb-0 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-gray-800 text-sm">
                        {posteLabels[cfg.poste] || cfg.poste}
                      </span>
                      <button
                        onClick={() => handleToggleMode(cfg.poste, cfg.capture_mode)}
                        className={`px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider shadow-sm transition-all duration-200 hover:shadow flex items-center gap-1.5 ${
                          cfg.capture_mode === 'camera'
                            ? 'bg-blue-100 text-blue-800 border border-blue-300'
                            : cfg.capture_mode === 'hybrid'
                            ? 'bg-purple-100 text-purple-800 border border-purple-300'
                            : 'bg-orange-100 text-orange-800 border border-orange-300'
                        }`}
                      >
                        {cfg.capture_mode === 'camera' ? <Camera className="w-3 h-3" /> : cfg.capture_mode === 'hybrid' ? <RefreshCw className="w-3 h-3" /> : <Smartphone className="w-3 h-3" />}
                        {cfg.capture_mode === 'camera' ? 'Caméra' : cfg.capture_mode === 'hybrid' ? 'Hybride' : 'Agent'}
                      </button>
                    </div>

                    {/* Édition de l'URL de la caméra */}
                    {isEditing ? (
                      <div className="flex items-center gap-1.5 mt-2">
                        <input
                          type="text"
                          value={tempUrl}
                          onChange={(e) => setTempUrl(e.target.value)}
                          placeholder="rtsp://admin:pass@192.168.1.XX:554/stream"
                          className="text-xs border rounded-lg px-2.5 py-1.5 flex-1 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        <button
                          onClick={() => handleSaveUrl(cfg.poste)}
                          className="p-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                          title="Enregistrer l'URL"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setEditingPoste(null)}
                          className="p-1.5 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                          title="Annuler"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between text-xs bg-slate-50 p-2 rounded-lg border border-gray-100 mt-1">
                        <span className="text-gray-500 font-mono truncate max-w-[200px]" title={cfg.camera_url || 'Non configuré'}>
                          {cfg.camera_url ? `🎥 ${cfg.camera_url}` : 'Pas de caméra IP'}
                        </span>
                        <button
                          onClick={() => handleStartEditUrl(cfg.poste, cfg.camera_url)}
                          className="text-blue-600 hover:text-blue-800 p-1 flex items-center gap-1 text-[11px] font-medium"
                        >
                          <Edit2 className="w-3 h-3" /> Modifier
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
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
