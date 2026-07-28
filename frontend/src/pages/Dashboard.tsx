import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardStats, getActiveEvents, getPosteConfigs, updatePosteConfig } from '@/services/api';
import { useWebSocket } from '@/hooks/useWebSocket';
import { TruckCard } from '@/components/TruckCard';
import { AlertBanner } from '@/components/AlertBanner';
import { StatsChart } from '@/components/StatsChart';
import type { DashboardStats, Event, PosteConfig } from '@/types';
import { Edit2, Check, X, Camera, Smartphone, RefreshCw, BarChart2, Timer, Save } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface AnomalieItem {
  cycle_id: number;
  immatriculation: string;
  entree_porte: string | null;
  sortie_porte: string | null;
  status: string;
  duree_heures: number | null;
  auto_closed: boolean;
  gap_applique: number | null;
}


interface Etape {
  id: number;
  ordre: number;
  code: string;
  nom: string;
  description: string;
  seuil_minutes: number;
  poste_ref: string | null;
  is_active: boolean;
  is_default: boolean;
  is_custom: boolean;
}

const STEP_COLORS = ['bg-slate-400','bg-blue-500','bg-purple-500','bg-orange-500','bg-purple-400','bg-slate-500','bg-red-500'];


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
  // ── Étapes dynamiques ──────────────────────────────────────────
  const [etapes, setEtapes] = useState<Etape[]>([]);
  const [editingEtapeId, setEditingEtapeId] = useState<number | null>(null);
  const [etapeDraft, setEtapeDraft] = useState<Partial<Etape>>({});
  const [showAddForm, setShowAddForm] = useState(false);
  const [newEtape, setNewEtape] = useState({ nom: '', description: '', seuil_minutes: 30 });
  const [etapeSaving, setEtapeSaving] = useState<number | null>(null);
  // ── Anomalies ───────────────────────────────────────────
  const [anomalies, setAnomalies] = useState<{
    en_cours_vieux: AnomalieItem[];
    auto_fermes: AnomalieItem[];
    expires: AnomalieItem[];
    total_alertes: number;
  } | null>(null);
  const { lastMessage, isConnected } = useWebSocket(WS_URL);

  const loadEtapes = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/etapes`);
      setEtapes(await res.json());
    } catch { /* silencieux */ }
  }, []);

  const loadAnomalies = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/anomalies`);
      setAnomalies(await res.json());
    } catch { /* silencieux */ }
  }, []);

  const runWatchdog = async () => {
    await fetch(`${API_BASE}/api/dashboard/watchdog`, { method: 'POST' });
    loadAnomalies();
  };

  const saveEtape = async (id: number) => {
    setEtapeSaving(id);
    try {
      await fetch(`${API_BASE}/api/dashboard/etapes/${id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(etapeDraft),
      });
      setEtapes(prev => prev.map(e => e.id === id ? { ...e, ...etapeDraft } : e));
      setEditingEtapeId(null);
    } catch { alert('Erreur sauvegarde'); }
    finally { setEtapeSaving(null); }
  };

  const deleteEtape = async (id: number, nom: string) => {
    if (!confirm(`Supprimer l'étape « ${nom} » ?`)) return;
    await fetch(`${API_BASE}/api/dashboard/etapes/${id}`, { method: 'DELETE' });
    setEtapes(prev => prev.filter(e => e.id !== id));
  };

  const addEtape = async () => {
    if (!newEtape.nom.trim()) return;
    const res = await fetch(`${API_BASE}/api/dashboard/etapes`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...newEtape, ordre: etapes.length + 1 }),
    });
    const created = await res.json();
    setEtapes(prev => [...prev, { ...created, is_active: true, is_default: false, is_custom: true, poste_ref: null, ordre: etapes.length + 1, code: created.code, description: newEtape.description }]);
    setNewEtape({ nom: '', description: '', seuil_minutes: 30 });
    setShowAddForm(false);
  };

  const reloadData = () => {
    getDashboardStats().then(setStats);
    getActiveEvents().then(setEvents);
    getPosteConfigs().then(setPosteConfigs);
  };

  useEffect(() => { reloadData(); loadEtapes(); loadAnomalies(); }, [loadEtapes, loadAnomalies]);
  useEffect(() => { if (lastMessage) { reloadData(); loadAnomalies(); } }, [lastMessage]);

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

  // Groupement des événements par camion (tous renvoyés par /api/events/active sont EN_COURS)
  const truckGroups = groupEventsByTruck(events);

  const encours: [number, Event[]][] = [];
  for (const [id, evs] of truckGroups.entries()) {
    const sortedEvs = [...evs].sort(
      (a, b) => new Date(a.horodatage).getTime() - new Date(b.horodatage).getTime()
    );
    encours.push([id, sortedEvs]);
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


        </div>

        {/* Panel droite : Configuration + Seuils */}
        <div className="space-y-4">

          {/* ── Panneau Étapes Dynamiques ── */}
          <div className="bg-white rounded-xl shadow border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Timer className="w-5 h-5 text-orange-500" />
                <h2 className="text-base font-bold text-gray-800">⏱️ Étapes &amp; Seuils du Processus</h2>
              </div>
              <button
                onClick={() => setShowAddForm(v => !v)}
                className="flex items-center gap-1.5 text-xs font-semibold text-violet-600 bg-violet-50 hover:bg-violet-100 px-3 py-1.5 rounded-lg transition-colors"
              >
                <Save className="w-3.5 h-3.5" /> + Ajouter une étape
              </button>
            </div>
            <p className="text-xs text-gray-400 mb-4">
              Modifiez le nom, la description et le seuil de chaque étape. Ajoutez des étapes personnalisées selon vos besoins.
            </p>

            {/* Formulaire ajout */}
            {showAddForm && (
              <div className="bg-violet-50 border border-violet-200 rounded-xl p-3 mb-4 space-y-2">
                <div className="text-xs font-bold text-violet-700 mb-1">➕ Nouvelle étape personnalisée</div>
                <input
                  type="text" placeholder="Nom de l'étape *"
                  value={newEtape.nom} onChange={e => setNewEtape(p => ({ ...p, nom: e.target.value }))}
                  className="w-full text-xs border border-violet-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-400"
                />
                <input
                  type="text" placeholder="Description (optionnel)"
                  value={newEtape.description} onChange={e => setNewEtape(p => ({ ...p, description: e.target.value }))}
                  className="w-full text-xs border border-violet-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-400"
                />
                <div className="flex items-center gap-2">
                  <label className="text-xs text-violet-700 font-semibold w-28 flex-shrink-0">Seuil (minutes) :</label>
                  <input
                    type="number" min={5} max={360}
                    value={newEtape.seuil_minutes} onChange={e => setNewEtape(p => ({ ...p, seuil_minutes: Number(e.target.value) }))}
                    className="w-24 text-xs border border-violet-200 rounded-lg px-2 py-2 focus:outline-none focus:ring-2 focus:ring-violet-400"
                  />
                  <span className="text-xs text-violet-500">min</span>
                </div>
                <div className="flex gap-2 pt-1">
                  <button onClick={addEtape} className="flex-1 text-xs font-semibold bg-violet-600 text-white py-2 rounded-lg hover:bg-violet-700 transition-colors">
                    ✓ Confirmer
                  </button>
                  <button onClick={() => setShowAddForm(false)} className="text-xs text-gray-500 bg-gray-100 px-4 py-2 rounded-lg hover:bg-gray-200">
                    Annuler
                  </button>
                </div>
              </div>
            )}

            {/* Liste des étapes */}
            <div className="space-y-2">
              {etapes.map((etape, idx) => {
                const isEditing = editingEtapeId === etape.id;
                const color = STEP_COLORS[Math.min(idx, STEP_COLORS.length - 1)];
                return (
                  <div key={etape.id} className={`border rounded-xl p-3 transition-colors ${isEditing ? 'border-orange-300 bg-orange-50/40' : 'border-gray-100 hover:bg-slate-50/50'}`}>
                    <div className="flex items-start gap-2">
                      {/* Numéro */}
                      <div className={`w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-extrabold text-white flex-shrink-0 mt-0.5 ${color}`}>
                        {etape.ordre}
                      </div>
                      <div className="flex-1 min-w-0">
                        {isEditing ? (
                          <div className="space-y-1.5">
                            <input
                              type="text"
                              value={etapeDraft.nom ?? etape.nom}
                              onChange={e => setEtapeDraft(p => ({ ...p, nom: e.target.value }))}
                              className="w-full text-xs font-semibold border border-orange-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-orange-400"
                            />
                            <input
                              type="text"
                              value={etapeDraft.description ?? etape.description}
                              onChange={e => setEtapeDraft(p => ({ ...p, description: e.target.value }))}
                              placeholder="Description..."
                              className="w-full text-xs text-gray-500 border border-orange-200 rounded-lg px-2 py-1 focus:outline-none"
                            />
                            <div className="flex items-center gap-2">
                              <label className="text-[11px] text-orange-700 font-semibold">Seuil :</label>
                              <input
                                type="number" min={5} max={360}
                                value={etapeDraft.seuil_minutes ?? etape.seuil_minutes}
                                onChange={e => setEtapeDraft(p => ({ ...p, seuil_minutes: Number(e.target.value) }))}
                                className="w-20 text-xs border border-orange-200 rounded-lg px-2 py-1 focus:outline-none"
                              />
                              <span className="text-[11px] text-gray-400">min</span>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="text-xs font-bold text-gray-800">{etape.nom}</span>
                              {etape.is_default && (
                                <span className="text-[9px] font-bold bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">SYSTÈME</span>
                              )}
                              {etape.is_custom && (
                                <span className="text-[9px] font-bold bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full">CUSTOM</span>
                              )}
                            </div>
                            <div className="text-[10px] text-gray-400 mt-0.5">{etape.description}</div>
                          </>
                        )}
                      </div>
                      {/* Seuil badge */}
                      {!isEditing && (
                        <span className="text-xs font-extrabold text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full flex-shrink-0">
                          {etape.seuil_minutes} min
                        </span>
                      )}
                    </div>

                    {/* Barre progress */}
                    {!isEditing && (
                      <div className="mt-2 ml-8">
                        <div className="w-full bg-gray-100 rounded-full h-1.5">
                          <div className={`h-1.5 rounded-full ${color}`}
                            style={{ width: `${Math.min((etape.seuil_minutes / 120) * 100, 100)}%` }} />
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-1.5 mt-2 ml-8">
                      {isEditing ? (
                        <>
                          <button
                            onClick={() => saveEtape(etape.id)}
                            disabled={etapeSaving === etape.id}
                            className="flex items-center gap-1 text-[11px] font-semibold text-white bg-green-600 hover:bg-green-700 px-3 py-1 rounded-lg transition-colors disabled:opacity-50"
                          >
                            <Check className="w-3 h-3" />{etapeSaving === etape.id ? 'Sauvegarde...' : 'Sauvegarder'}
                          </button>
                          <button
                            onClick={() => setEditingEtapeId(null)}
                            className="text-[11px] text-gray-500 bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded-lg"
                          >
                            Annuler
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => { setEditingEtapeId(etape.id); setEtapeDraft({ nom: etape.nom, description: etape.description, seuil_minutes: etape.seuil_minutes }); }}
                            className="flex items-center gap-1 text-[11px] text-orange-600 hover:text-orange-800 bg-orange-50 hover:bg-orange-100 px-2.5 py-1 rounded-lg transition-colors"
                          >
                            <Edit2 className="w-3 h-3" /> Modifier
                          </button>
                          {etape.is_custom && (
                            <button
                              onClick={() => deleteEtape(etape.id, etape.nom)}
                              className="flex items-center gap-1 text-[11px] text-red-500 hover:text-red-700 bg-red-50 hover:bg-red-100 px-2.5 py-1 rounded-lg transition-colors"
                            >
                              <X className="w-3 h-3" /> Supprimer
                            </button>
                          )}
                        </>
                      )}
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

      {/* ── Panneau Anomalies ── */}
      {anomalies && (
        <div className="mt-6 bg-white rounded-xl shadow border border-gray-100 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="text-lg">🔍</span>
              <h2 className="text-base font-bold text-gray-800">Anomalies &amp; Cycles Incomplets</h2>
              {anomalies.total_alertes > 0 && (
                <span className="text-xs font-extrabold bg-red-500 text-white px-2 py-0.5 rounded-full">
                  {anomalies.total_alertes} alerte{anomalies.total_alertes > 1 ? 's' : ''}
                </span>
              )}
            </div>
            <button
              onClick={runWatchdog}
              className="text-xs font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Lancer Watchdog
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Cycles bloqués (EN_COURS depuis +4h) */}
            <div className="border border-red-100 rounded-xl p-3 bg-red-50/30">
              <div className="text-xs font-bold text-red-700 mb-2 flex items-center gap-1">
                <span>⏳</span> Camions bloqués &gt;4h
                <span className="ml-auto bg-red-100 text-red-700 rounded-full px-1.5 py-0.5 text-[10px]">
                  {anomalies.en_cours_vieux.length}
                </span>
              </div>
              {anomalies.en_cours_vieux.length === 0 ? (
                <p className="text-[11px] text-gray-400 text-center py-2">✅ Aucun camion bloqué</p>
              ) : (
                <div className="space-y-1.5">
                  {anomalies.en_cours_vieux.map(a => (
                    <div key={a.cycle_id} className="text-[11px] bg-white border border-red-100 rounded-lg px-2.5 py-1.5">
                      <div className="font-bold text-gray-800">{a.immatriculation}</div>
                      <div className="text-gray-400">Entré il y a <span className="text-red-600 font-semibold">{a.duree_heures}h</span></div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Cycles auto-fermés */}
            <div className="border border-orange-100 rounded-xl p-3 bg-orange-50/30">
              <div className="text-xs font-bold text-orange-700 mb-2 flex items-center gap-1">
                <span>🔄</span> Auto-fermés
                <span className="ml-auto bg-orange-100 text-orange-700 rounded-full px-1.5 py-0.5 text-[10px]">
                  {anomalies.auto_fermes.length}
                </span>
              </div>
              {anomalies.auto_fermes.length === 0 ? (
                <p className="text-[11px] text-gray-400 text-center py-2">✅ Aucun cycle auto-fermé</p>
              ) : (
                <div className="space-y-1.5">
                  {anomalies.auto_fermes.map(a => (
                    <div key={a.cycle_id} className="text-[11px] bg-white border border-orange-100 rounded-lg px-2.5 py-1.5">
                      <div className="font-bold text-gray-800">{a.immatriculation}</div>
                      <div className="text-gray-400">Gap appliqué : <span className="text-orange-600 font-semibold">{a.gap_applique} min</span></div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Cycles expirés (watchdog) */}
            <div className="border border-gray-100 rounded-xl p-3 bg-gray-50/30">
              <div className="text-xs font-bold text-gray-600 mb-2 flex items-center gap-1">
                <span>☠️</span> Expirés (watchdog)
                <span className="ml-auto bg-gray-200 text-gray-600 rounded-full px-1.5 py-0.5 text-[10px]">
                  {anomalies.expires.length}
                </span>
              </div>
              {anomalies.expires.length === 0 ? (
                <p className="text-[11px] text-gray-400 text-center py-2">✅ Aucun cycle expiré</p>
              ) : (
                <div className="space-y-1.5">
                  {anomalies.expires.map(a => (
                    <div key={a.cycle_id} className="text-[11px] bg-white border border-gray-200 rounded-lg px-2.5 py-1.5">
                      <div className="font-bold text-gray-800">{a.immatriculation}</div>
                      <div className="text-gray-400">Durée : <span className="text-gray-600 font-semibold">{a.duree_heures}h</span></div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
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
