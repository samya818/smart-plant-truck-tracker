import { useState, useEffect, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import {
  Clock, Truck, AlertTriangle, CheckCircle2, TrendingUp, TrendingDown,
  Activity, Users, BarChart2, Calendar, RefreshCw, Award, Zap
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

type Periode = 'aujourd_hui' | 'semaine' | 'mois';

interface ZoneDuree {
  zone: string;
  key: string;
  moyenne: number;
  seuil: number;
  depassements: number;
}

interface CauseRetard {
  cause: string;
  occurrences: number;
  total_minutes: number;
  poste: string;
  pct_du_retard: number;
  repartition_transporteurs: { transporteur: string; occurrences: number }[];
}

interface EvolutionPoint {
  heure: string;
  nb_camions: number;
}

interface PerformanceTransporteur {
  transporteur: string;
  nb_rotations: number;
  temps_moyen_min: number;
  taux_retard_pct: number;
  retard_cumule_min: number;
  cause_principale: string;
}

interface CamionBloque {
  truck_id: number;
  immatriculation: string;
  poste_actuel: string;
  minutes_attente_poste: number;
  entree_porte: string | null;
}

interface RapportData {
  periode: Periode;
  periode_label: string;
  date_debut: string;
  date_fin: string;
  nb_cycles_total: number;
  nb_cycles_termines: number;
  nb_cycles_en_cours: number;
  nb_cycles_anomalie: number;
  taux_anomalie_pct: number;
  temps_moyen_cycle_min: number;
  variation_pct: number;
  tendance: 'hausse' | 'baisse' | 'stable';
  temps_median_cycle_min: number;
  temps_p25_cycle_min: number;
  temps_p75_cycle_min: number;
  camions_bloques_actuellement: CamionBloque[];
  durees_par_zone: ZoneDuree[];
  top_causes_retard: CauseRetard[];
  repartition_source: Record<string, number>;
  evolution_journaliere: EvolutionPoint[];
  performance_transporteurs: PerformanceTransporteur[];
  retard_global_par_poste: Record<string, number>;
}

const PERIODE_LABELS: Record<Periode, string> = {
  aujourd_hui: "Aujourd'hui",
  semaine: '7 derniers jours',
  mois: '30 derniers jours',
};

const COLORS_PIE = ['#3B82F6', '#F59E0B', '#8B5CF6', '#94A3B8'];
const SOURCE_LABELS: Record<string, string> = {
  camera: '📷 Caméra OCR',
  agent_mobile: '📱 Agent Mobile',
  hybrid: '♻️ Hybride',
  simulation: '🔄 Simulation',
};

export default function StatistiquesPage() {
  const [periode, setPeriode] = useState<Periode>('aujourd_hui');
  const [data, setData] = useState<RapportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRapport = useCallback(async (p: Periode) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/analytics/rapport?periode=${p}`);
      if (!res.ok) throw new Error(`Erreur API: ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message || 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchRapport(periode); }, [periode, fetchRapport]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-6">
      {/* ── En-tête ── */}
      <div className="mb-8">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-extrabold text-gray-900 flex items-center gap-3">
              <BarChart2 className="w-8 h-8 text-blue-600" />
              Rapport Statistique — LafargeHolcim Meknès
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              Analyse des flux camions, performances des postes et indicateurs clés de productivité
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Sélecteur de période */}
            <div className="flex bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
              {(Object.keys(PERIODE_LABELS) as Periode[]).map(p => (
                <button
                  key={p}
                  onClick={() => setPeriode(p)}
                  className={`px-4 py-2 text-sm font-semibold transition-all duration-200 ${
                    periode === p
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <Calendar className="w-3.5 h-3.5 inline mr-1.5" />
                  {PERIODE_LABELS[p]}
                </button>
              ))}
            </div>
            <button
              onClick={() => fetchRapport(periode)}
              className="p-2.5 bg-white border border-gray-200 rounded-xl shadow-sm hover:bg-gray-50 transition-colors"
              title="Actualiser"
            >
              <RefreshCw className={`w-4 h-4 text-gray-600 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {data && (
          <p className="text-xs text-gray-400 mt-2">
            Période : du <strong>{new Date(data.date_debut).toLocaleString('fr-FR')}</strong> au <strong>{new Date(data.date_fin).toLocaleString('fr-FR')}</strong>
          </p>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 mb-6 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" /> {error}
        </div>
      )}

      {loading && !data && (
        <div className="flex items-center justify-center h-64">
          <div className="text-center space-y-3">
            <RefreshCw className="w-10 h-10 text-blue-500 animate-spin mx-auto" />
            <p className="text-gray-500">Chargement des statistiques...</p>
          </div>
        </div>
      )}

      {data && (
        <div className="space-y-6">

          {/* ── 1. KPIs Principaux ── */}
          <section>
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-widest mb-3">
              📊 Indicateurs Clés de Performance
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
              <KpiCard icon={<Truck className="w-5 h-5 text-blue-600" />} label="Cycles Total" value={data.nb_cycles_total} color="blue" span={2} />
              <KpiCard icon={<CheckCircle2 className="w-5 h-5 text-green-600" />} label="Terminés" value={data.nb_cycles_termines} color="green" span={2} />
              <KpiCard icon={<Activity className="w-5 h-5 text-orange-600" />} label="En cours" value={data.nb_cycles_en_cours} color="orange" span={2} />
              <KpiCard icon={<AlertTriangle className="w-5 h-5 text-red-600" />} label="Anomalies" value={data.nb_cycles_anomalie} color="red" span={2} sub={`${data.taux_anomalie_pct}% du total`} />
            </div>
          </section>

          {/* ── 2. Temps de Cycle ── */}
          <section>
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-widest mb-3">
              ⏱️ Analyse des Temps de Séjour en Usine & Distribution
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="rounded-2xl border p-4 bg-white border-gray-100 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs font-semibold text-gray-500 mb-1">
                  <span className="flex items-center gap-1.5"><Clock className="w-4 h-4 text-blue-600" /> Temps Moyen</span>
                  {data.variation_pct !== 0 && (
                    <span className={`flex items-center gap-0.5 font-bold px-1.5 py-0.5 rounded text-[11px] ${
                      data.tendance === 'baisse' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {data.tendance === 'baisse' ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
                      {data.variation_pct > 0 ? `+${data.variation_pct}%` : `${data.variation_pct}%`}
                    </span>
                  )}
                </div>
                <div className="text-2xl font-extrabold text-gray-800">
                  {Math.round(data.temps_moyen_cycle_min)} <span className="text-sm font-normal text-gray-500">min</span>
                </div>
                <div className="text-[11px] text-gray-400 mt-0.5">vs période précédente</div>
              </div>

              <TimeCard label="Temps Médian (P50)" value={data.temps_median_cycle_min} seuil={120} icon={<Activity />} />
              <TimeCard label="Premier Quartile (P25)" value={data.temps_p25_cycle_min} seuil={120} icon={<TrendingDown />} positive />
              <TimeCard label="Troisième Quartile (P75)" value={data.temps_p75_cycle_min} seuil={120} icon={<TrendingUp />} />
            </div>
          </section>

          {/* ── 2.5 Camions Bloqués Actuellement sur le Site ── */}
          {data.camions_bloques_actuellement.length > 0 && (
            <section className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-gray-800 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-500" />
                  🚨 Camions Actuellement Bloqués sur le Site ({data.camions_bloques_actuellement.length})
                </h3>
                <span className="text-xs text-gray-400">Triés par temps d'attente au poste en cours</span>
              </div>
              <div className="overflow-x-auto rounded-xl border border-gray-100">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="bg-slate-50 text-gray-500 font-semibold uppercase">
                      <th className="p-3">Camion</th>
                      <th className="p-3">Poste Actuel</th>
                      <th className="p-3">Attente au Poste</th>
                      <th className="p-3 text-right">Entrée Usine</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.camions_bloques_actuellement.map((c, i) => (
                      <tr key={i} className={c.minutes_attente_poste > 30 ? 'bg-red-50/40' : 'hover:bg-slate-50/50'}>
                        <td className="p-3 font-mono font-bold text-gray-800">{c.immatriculation}</td>
                        <td className="p-3 font-medium text-gray-700 capitalize">{c.poste_actuel.replace('_', ' ')}</td>
                        <td className="p-3 font-bold font-mono">
                          <span className={c.minutes_attente_poste > 30 ? 'text-red-600 font-extrabold' : 'text-gray-700'}>
                            {c.minutes_attente_poste} min
                          </span>
                        </td>
                        <td className="p-3 text-right text-gray-400 font-mono">
                          {c.entree_porte ? new Date(c.entree_porte).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* ── 3. Graphiques principaux ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Évolution des passages */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-bold text-gray-800 mb-1 flex items-center gap-2">
                <Activity className="w-5 h-5 text-blue-500" />
                Volume de Passages par {periode === 'aujourd_hui' ? 'Heure' : periode === 'semaine' ? 'Jour' : 'Semaine'}
              </h3>
              <p className="text-xs text-gray-400 mb-4">Nombre de camions traités sur la période sélectionnée</p>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.evolution_journaliere}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                    <XAxis dataKey="heure" tick={{ fontSize: 11, fill: '#94A3B8' }} />
                    <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} allowDecimals={false} />
                    <Tooltip
                      formatter={(v: number) => [`${v} camions`, 'Volume']}
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
                    />
                    <Bar dataKey="nb_camions" fill="#3B82F6" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Temps moyens par zone */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-bold text-gray-800 mb-1 flex items-center gap-2">
                <BarChart2 className="w-5 h-5 text-violet-500" />
                Temps Moyen vs Objectif par Zone (min)
              </h3>
              <p className="text-xs text-gray-400 mb-4">Zones en rouge = dépassement de l'objectif LafargeHolcim</p>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.durees_par_zone} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#F1F5F9" />
                    <XAxis type="number" unit=" min" tick={{ fontSize: 11, fill: '#94A3B8' }} />
                    <YAxis type="category" dataKey="zone" tick={{ fontSize: 11, fill: '#64748B' }} width={110} />
                    <Tooltip
                      formatter={(v: number) => [`${v} min`, '']}
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="moyenne" name="Réel" radius={[0, 6, 6, 0]}>
                      {data.durees_par_zone.map((entry, index) => (
                        <Cell key={index} fill={entry.moyenne > entry.seuil ? '#EF4444' : '#3B82F6'} />
                      ))}
                    </Bar>
                    <Bar dataKey="seuil" name="Objectif" fill="#E2E8F0" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* ── 4. Tableau Détaillé Zones + Source de Capture ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* Tableau Zones */}
            <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-bold text-gray-800 mb-4 flex items-center gap-2">
                <Clock className="w-5 h-5 text-amber-500" />
                Analyse Détaillée par Zone & Poste
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-gray-500 text-xs uppercase font-semibold">
                      <th className="text-left p-3 rounded-l-xl">Zone</th>
                      <th className="text-right p-3">Temps Moyen</th>
                      <th className="text-right p-3">Objectif Max</th>
                      <th className="text-right p-3">Écart</th>
                      <th className="text-right p-3 rounded-r-xl">Dépassements</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {data.durees_par_zone.map((z) => {
                      const ecart = z.moyenne - z.seuil;
                      const depasse = ecart > 0;
                      return (
                        <tr key={z.key} className={`hover:bg-slate-50/50 transition-colors ${depasse ? 'bg-red-50/30' : ''}`}>
                          <td className="p-3 font-semibold text-gray-800">{z.zone}</td>
                          <td className="p-3 text-right font-mono font-bold text-gray-700">{z.moyenne} min</td>
                          <td className="p-3 text-right font-mono text-gray-400">{z.seuil} min</td>
                          <td className="p-3 text-right font-bold">
                            {depasse ? (
                              <span className="text-red-600 flex items-center justify-end gap-1">
                                <TrendingUp className="w-3.5 h-3.5" />+{ecart.toFixed(1)} min
                              </span>
                            ) : (
                              <span className="text-green-600 flex items-center justify-end gap-1">
                                <CheckCircle2 className="w-3.5 h-3.5" />Conforme
                              </span>
                            )}
                          </td>
                          <td className="p-3 text-right">
                            <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                              z.depassements > 0 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                            }`}>
                              {z.depassements > 0 ? `⚠️ ${z.depassements} cas` : '✅ Aucun'}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Répartition Sources de Capture */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-bold text-gray-800 mb-1 flex items-center gap-2">
                <Zap className="w-5 h-5 text-purple-500" />
                Source de Capture des Données
              </h3>
              <p className="text-xs text-gray-400 mb-4">Répartition Caméra OCR / Agent / Hybride</p>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={Object.entries(data.repartition_source)
                        .filter(([, v]) => v > 0)
                        .map(([k, v]) => ({ name: SOURCE_LABELS[k] || k, value: v }))}
                      cx="50%" cy="50%" innerRadius={45} outerRadius={70}
                      paddingAngle={4} dataKey="value"
                    >
                      {Object.entries(data.repartition_source).filter(([, v]) => v > 0).map((_, i) => (
                        <Cell key={i} fill={COLORS_PIE[i % COLORS_PIE.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v: number) => [`${v} événements`, '']}
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Répartition Cumulative du Retard (nouveau graphique) */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-bold text-gray-800 mb-1 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-red-500" />
                Impact Cumulé des Retards par Etape (min)
              </h3>
              <p className="text-xs text-gray-400 mb-4">Temps d'attente total excédentaire par rapport aux objectifs</p>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={Object.entries(data.retard_global_par_poste).map(([k, v]) => ({ name: k, minutes: v }))}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748B' }} />
                    <YAxis tick={{ fontSize: 10, fill: '#94A3B8' }} />
                    <Tooltip
                      formatter={(v: number) => [`${v} min`, 'Retard cumulé']}
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
                    />
                    <Bar dataKey="minutes" fill="#EF4444" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* ── 5. Analyse Statistique des Causes de Retard ── */}
          {data.top_causes_retard.length > 0 && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="font-bold text-gray-800 flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-500" />
                    Analyse Statistique Complète des Causes de Retard
                  </h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {data.top_causes_retard.length} cause(s) identifiée(s) — triées par impact total (minutes perdues)
                  </p>
                </div>
                <div className="text-right text-sm">
                  <div className="font-bold text-red-600 text-lg">
                    {data.top_causes_retard.reduce((s, c) => s + c.total_minutes, 0)} min
                  </div>
                  <div className="text-xs text-gray-400">Temps total perdu</div>
                </div>
              </div>

              {/* Graphique barre horizontal : minutes par cause */}
              <div className="h-56 mb-6">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.top_causes_retard} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#F1F5F9" />
                    <XAxis type="number" unit=" min" tick={{ fontSize: 10, fill: '#94A3B8' }} />
                    <YAxis type="category" dataKey="cause" tick={{ fontSize: 10, fill: '#64748B' }} width={160} />
                    <Tooltip
                      formatter={(v: number) => [`${v} min`, 'Temps perdu']}
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
                    />
                    <Bar dataKey="total_minutes" radius={[0, 6, 6, 0]}>
                      {data.top_causes_retard.map((_, i) => (
                        <Cell key={i} fill={i === 0 ? '#EF4444' : i === 1 ? '#F97316' : i === 2 ? '#F59E0B' : '#94A3B8'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Tableau détaillé par cause */}
              <div className="space-y-3">
                {data.top_causes_retard.map((c, idx) => {
                  const posteLabelMap: Record<string, string> = {
                    parking: '🅿️ Parking',
                    bascule: '⚖️ Bascule',
                    ensachage: '📦 Ensachage',
                    porte_usine: '🚪 Porte Usine',
                  };
                  const rankColors = ['bg-red-500', 'bg-orange-500', 'bg-amber-500', 'bg-slate-400'];
                  const rank = Math.min(idx, 3);

                  return (
                    <div key={idx} className="border border-gray-100 rounded-xl p-4 hover:bg-slate-50/50 transition-colors">
                      {/* En-tête de la cause */}
                      <div className="flex items-start gap-3 mb-2">
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-extrabold text-white flex-shrink-0 ${rankColors[rank]}`}>
                          #{idx + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-bold text-gray-800">{c.cause}</div>
                          <div className="text-xs text-gray-500 mt-0.5">
                            {posteLabelMap[c.poste] || c.poste.replace('_', ' ')}
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <div className="text-base font-extrabold text-red-600">{c.total_minutes} min</div>
                          <div className="text-xs text-gray-400">{c.occurrences} occurrence{c.occurrences > 1 ? 's' : ''}</div>
                        </div>
                      </div>

                      {/* Barre de progression (part du retard global) */}
                      <div className="flex items-center gap-3 mb-2">
                        <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
                          <div
                            className={`h-2 rounded-full transition-all duration-500 ${rankColors[rank]}`}
                            style={{ width: `${Math.min(c.pct_du_retard, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs font-bold text-gray-600 w-12 text-right">{c.pct_du_retard}%</span>
                        <span className="text-xs text-gray-400">du retard global</span>
                      </div>

                      {/* Répartition par transporteur */}
                      {c.repartition_transporteurs.length > 0 && (
                        <div className="mt-2">
                          <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Transporteurs impactés :</div>
                          <div className="flex flex-wrap gap-1.5">
                            {c.repartition_transporteurs.map((t, ti) => (
                              <span key={ti} className="inline-flex items-center gap-1 text-[11px] bg-blue-50 border border-blue-100 text-blue-700 px-2.5 py-0.5 rounded-full">
                                <Truck className="w-3 h-3" />
                                {t.transporteur} <span className="font-bold">({t.occurrences}x)</span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── 6. Performance des Transporteurs ── */}
          {data.performance_transporteurs.length > 0 && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-bold text-gray-800 mb-4 flex items-center gap-2">
                <Users className="w-5 h-5 text-blue-500" />
                Performance & Responsabilité des Sociétés de Transport (Fournisseurs)
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-gray-500 text-xs uppercase font-semibold">
                      <th className="text-left p-3 rounded-l-xl">Transporteur / Fournisseur</th>
                      <th className="text-right p-3">Rotations</th>
                      <th className="text-right p-3">Temps Moyen (Total)</th>
                      <th className="text-right p-3">Retard Cumulé</th>
                      <th className="text-right p-3">Taux d'Anomalies / Retards</th>
                      <th className="text-left p-3 rounded-r-xl">Cause Principale Rencontrée</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {data.performance_transporteurs
                      .sort((a, b) => b.retard_cumule_min - a.retard_cumule_min)
                      .map((t, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/50 transition-colors">
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              {idx === 0 && t.retard_cumule_min > 0 && (
                                <span title="Plus gros contributeur aux retards">
                                  <AlertTriangle className="w-4 h-4 text-red-500 animate-pulse" />
                                </span>
                              )}
                              {idx === data.performance_transporteurs.length - 1 && (
                                <span title="Transporteur le plus performant">
                                  <Award className="w-4 h-4 text-green-500" />
                                </span>
                              )}
                              <span className="font-semibold text-gray-800">{t.transporteur}</span>
                            </div>
                          </td>
                          <td className="p-3 text-right font-mono font-bold text-gray-700">{t.nb_rotations}</td>
                          <td className="p-3 text-right">
                            <span className={`font-mono font-bold ${t.temps_moyen_min > 120 ? 'text-red-600' : 'text-green-600'}`}>
                              {Math.round(t.temps_moyen_min)} min
                            </span>
                          </td>
                          <td className="p-3 text-right text-red-600 font-mono font-bold">
                            {t.retard_cumule_min > 0 ? `+${t.retard_cumule_min} min` : '0 min'}
                          </td>
                          <td className="p-3 text-right">
                            <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                              t.taux_retard_pct > 15 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                            }`}>
                              {t.taux_retard_pct}%
                            </span>
                          </td>
                          <td className="p-3 text-left">
                            <span className={`text-xs px-2.5 py-1 rounded-lg ${
                              t.cause_principale !== "Aucune déclarée" ? 'bg-amber-50 text-amber-800 border border-amber-100' : 'bg-gray-100 text-gray-500'
                            }`}>
                              {t.cause_principale}
                            </span>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  );
}

// ── Sous-composants ────────────────────────────────────────────────────────────

function KpiCard({ icon, label, value, color, span, sub }: {
  icon: React.ReactNode; label: string; value: number; color: string; span?: number; sub?: string;
}) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 border-blue-100 text-blue-700',
    green: 'bg-green-50 border-green-100 text-green-700',
    orange: 'bg-orange-50 border-orange-100 text-orange-700',
    red: 'bg-red-50 border-red-100 text-red-700',
  };
  return (
    <div className={`col-span-${span || 1} rounded-2xl border p-4 ${colors[color]}`}>
      <div className="flex items-center gap-2 mb-1">{icon}<span className="text-xs font-semibold opacity-75">{label}</span></div>
      <div className="text-3xl font-extrabold">{value}</div>
      {sub && <div className="text-xs opacity-60 mt-0.5">{sub}</div>}
    </div>
  );
}

function TimeCard({ label, value, seuil, icon, positive = false }: {
  label: string; value: number; seuil: number; icon: React.ReactNode; positive?: boolean;
}) {
  const overSeuil = value > seuil && !positive;
  return (
    <div className={`rounded-2xl border p-4 ${overSeuil ? 'bg-red-50 border-red-100' : 'bg-white border-gray-100'}`}>
      <div className={`flex items-center gap-1.5 text-xs font-semibold mb-1 ${overSeuil ? 'text-red-500' : 'text-gray-500'}`}>
        {icon}{label}
      </div>
      <div className={`text-2xl font-extrabold ${overSeuil ? 'text-red-700' : 'text-gray-800'}`}>
        {Math.round(value)} <span className="text-sm font-normal">min</span>
      </div>
      <div className="text-[11px] text-gray-400 mt-0.5">Objectif : {seuil} min</div>
    </div>
  );
}
