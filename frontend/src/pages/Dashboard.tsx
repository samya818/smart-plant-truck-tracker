import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardStats, getActiveEvents, getPosteConfigs, updatePosteConfig } from '@/services/api';
import { useWebSocket } from '@/hooks/useWebSocket';
import { TruckCard } from '@/components/TruckCard';
import { AlertBanner } from '@/components/AlertBanner';
import { StatsChart } from '@/components/StatsChart';
import type { DashboardStats, Event, PosteConfig } from '@/types';
import { Edit2, Check, X, Camera, Smartphone, RefreshCw, BarChart2, Timer, Save, RotateCcw } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Seuils {
  parking: number;
  bascule_tare: number;
  ensachage: number;
  bascule_brut: number;
  cycle_total: number;
}

const SEUILS_DEFAULTS: Seuils = { parking: 30, bascule_tare: 15, ensachage: 45, bascule_brut: 15, cycle_total: 120 };

const ZONES_CONFIG = [
  { key: 'parking',      label: '🅿️ Parking',       desc: 'Attente avant pesage',       min: 5,  max: 120, step: 5,  color: 'blue'   },
  { key: 'bascule_tare', label: '⚖️ Bascule (Tare)', desc: 'Pesage camion vide',         min: 5,  max: 60,  step: 5,  color: 'purple' },
  { key: 'ensachage',    label: '📦 Ensachage',      desc: 'Chargement des sacs',        min: 10, max: 180, step: 5,  color: 'orange' },
  { key: 'bascule_brut', label: '⚖️ Bascule (Brut)', desc: 'Pesage camion chargé',       min: 5,  max: 60,  step: 5,  color: 'purple' },
  { key: 'cycle_total',  label: '🔄 Cycle Total',    desc: 'Durée totale max en usine',  min: 30, max: 360, step: 15, color: 'red'    },
] as const;

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
  // ── Seuils ──────────────────────────────────────────────────────────
  const [seuils, setSeuils] = useState<Seuils>(SEUILS_DEFAULTS);
  const [seuilsDraft, setSeuilsDraft] = useState<Seuils>(SEUILS_DEFAULTS);
  const [seuilsEditing, setSeuilsEditing] = useState(false);
  const [seuilsSaving, setSeuilsSaving] = useState(false);
  const [seuilsSaved, setSeuilsSaved] = useState(false);
  const { lastMessage, isConnected } = useWebSocket(WS_URL);

  const loadSeuils = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/seuils`);
      const data = await res.json();
      setSeuils(data);
      setSeuilsDraft(data);
    } catch { /* fallback silencieux */ }
  }, []);

  const saveSeuils = async () => {
    setSeuilsSaving(true);
    try {
      await fetch(`${API_BASE}/api/dashboard/seuils`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(seuilsDraft),
      });
      setSeuils(seuilsDraft);
      setSeuilsEditing(false);
      setSeuilsSaved(true);
      setTimeout(() => setSeuilsSaved(false), 2500);
    } catch { alert('Erreur lors de la sauvegarde des seuils'); }
    finally { setSeuilsSaving(false); }
  };

  const cancelSeuils = () => {
    setSeuilsDraft(seuils);
    setSeuilsEditing(false);
  };

  const reloadData = () => {
    getDashboardStats().then(setStats);
    getActiveEvents().then(setEvents);
    getPosteConfigs().then(setPosteConfigs);
  };

  useEffect(() => { reloadData(); loadSeuils(); }, [loadSeuils]);
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

        {/* Panel droite : Configuration + Seuils */}
        <div className="space-y-4">

          {/* ── Panneau Seuils de Temps ── */}
          <div className="bg-white rounded-xl shadow border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Timer className="w-5 h-5 text-orange-500" />
                <h2 className="text-base font-bold text-gray-800">⏱️ Seuils de Temps par Zone</h2>
              </div>
              {!seuilsEditing ? (
                <button
                  onClick={() => setSeuilsEditing(true)}
                  className="flex items-center gap-1.5 text-xs font-semibold text-orange-600 hover:text-orange-700 bg-orange-50 hover:bg-orange-100 px-3 py-1.5 rounded-lg transition-colors"
                >
                  <Edit2 className="w-3.5 h-3.5" /> Modifier
                </button>
              ) : (
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={saveSeuils}
                    disabled={seuilsSaving}
                    className="flex items-center gap-1.5 text-xs font-semibold text-white bg-green-600 hover:bg-green-700 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                  >
                    <Save className="w-3.5 h-3.5" />{seuilsSaving ? 'Sauvegarde...' : 'Sauvegarder'}
                  </button>
                  <button
                    onClick={cancelSeuils}
                    className="flex items-center gap-1.5 text-xs font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded-lg transition-colors"
                  >
                    <RotateCcw className="w-3.5 h-3.5" /> Annuler
                  </button>
                </div>
              )}
            </div>

            {seuilsSaved && (
              <div className="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2 mb-3 flex items-center gap-2">
                <Check className="w-3.5 h-3.5" /> Seuils enregistrés avec succès
              </div>
            )}

            <p className="text-xs text-gray-400 mb-4">
              Durée maximale autorisée par zone. Les camions dépassant ces valeurs déclenchent une alerte.
            </p>

            <div className="space-y-4">
              {ZONES_CONFIG.map((zone) => {
                const val = seuilsEditing ? seuilsDraft[zone.key] : seuils[zone.key];
                const colorMap: Record<string, string> = {
                  blue: 'text-blue-600 bg-blue-50', purple: 'text-purple-600 bg-purple-50',
                  orange: 'text-orange-600 bg-orange-50', red: 'text-red-600 bg-red-50',
                };
                const sliderMap: Record<string, string> = {
                  blue: 'accent-blue-600', purple: 'accent-purple-600',
                  orange: 'accent-orange-500', red: 'accent-red-600',
                };
                return (
                  <div key={zone.key}>
                    <div className="flex items-center justify-between mb-1">
                      <div>
                        <span className="text-xs font-bold text-gray-700">{zone.label}</span>
                        <span className="text-[10px] text-gray-400 ml-2">{zone.desc}</span>
                      </div>
                      <span className={`text-xs font-extrabold px-2 py-0.5 rounded-full ${colorMap[zone.color]}`}>
                        {val} min
                      </span>
                    </div>
                    {seuilsEditing ? (
                      <input
                        type="range"
                        min={zone.min} max={zone.max} step={zone.step}
                        value={seuilsDraft[zone.key]}
                        onChange={(e) => setSeuilsDraft(prev => ({ ...prev, [zone.key]: Number(e.target.value) }))}
                        className={`w-full h-2 rounded-full cursor-pointer ${sliderMap[zone.color]}`}
                      />
                    ) : (
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            zone.color === 'blue' ? 'bg-blue-500' : zone.color === 'purple' ? 'bg-purple-500' :
                            zone.color === 'orange' ? 'bg-orange-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${Math.min((val / zone.max) * 100, 100)}%` }}
                        />
                      </div>
                    )}
                    <div className="flex justify-between text-[10px] text-gray-300 mt-0.5">
                      <span>{zone.min} min</span><span>{zone.max} min</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Panel Configuration Postes Bi-Mode ── */}
          <div className="bg-white rounded-xl shadow p-6 border border-gray-100">
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
