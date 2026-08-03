import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts';
import { ShieldAlert, Clock, AlertTriangle, CheckCircle2, Info, ArrowUpRight } from 'lucide-react';
import { getStatsRetardsServices } from '@/services/api';

interface ZoneDetail {
  key: string;
  etape: string;
  nom: string;
  action: string;
  temps_moyen: number;
  seuil_max: number;
  depassement: number;
  taux_retard_pct: number;
  temps_perdu_total_min: number;
  causes: { cause: string; occurrences: number; total_minutes: number }[];
}

interface AnalyticsData {
  zones: ZoneDetail[];
  nb_cycles_analyses: number;
  zone_la_plus_bloquante: string;
  total_temps_perdu_heures: number;
}

export function StatsChart() {
  const [data, setData] = useState<AnalyticsData | null>(null);

  useEffect(() => {
    getStatsRetardsServices().then(setData).catch(() => null);
  }, []);

  if (!data) return null;

  const chartData = data.zones.map(z => ({
    name: z.nom,
    'Temps Moyen Réel (min)': z.temps_moyen,
    'Seuil Toléré (min)': z.seuil_max,
    depassement: z.depassement,
    isCritique: z.depassement > 0,
  }));

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-6">

      {/* ── 1. En-tête du Panneau Analytique ────────────────────────────────── */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b pb-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-red-600" />
            <h2 className="text-xl font-bold text-gray-900">📊 Diagnostic & Analyse Détaillée des Retards par Service</h2>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Décomposition des temps de passage réels vs objectifs métiers sur {data.nb_cycles_analyses} cycles analysés.
          </p>
        </div>

        {/* Badges Synthèse Globale */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="bg-red-50 border border-red-200 px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 text-red-700 font-medium">
            <AlertTriangle className="w-4 h-4 text-red-600" />
            <span>Goulot principal : <strong>{data.zone_la_plus_bloquante}</strong></span>
          </div>
          <div className="bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 text-amber-800 font-medium">
            <Clock className="w-4 h-4 text-amber-600" />
            <span>Cumul temps perdu : <strong>{data.total_temps_perdu_heures}h</strong></span>
          </div>
        </div>
      </div>

      {/* ── 2. Graphique Comparatif & Synthèse de l'Impact ───────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Graphique de comparaison Temps Moyen vs Seuil */}
        <div className="lg:col-span-2 bg-slate-50/50 rounded-2xl p-4 border border-gray-100 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-gray-800 flex items-center gap-1.5">
              <ArrowUpRight className="w-4 h-4 text-blue-600" /> Temps Réel vs Seuil Toléré par Zone (en Minutes)
            </h3>
            <span className="text-[11px] text-gray-400">Objectifs LafargeHolcim</span>
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748B' }} interval={0} />
                <YAxis unit=" min" tick={{ fontSize: 11, fill: '#64748B' }} />
                <Tooltip
                  formatter={(val: number) => [`${val} min`, '']}
                  contentStyle={{ borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', border: 'none' }}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Bar dataKey="Temps Moyen Réel (min)" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.isCritique ? '#EF4444' : '#3B82F6'}
                    />
                  ))}
                </Bar>
                <Bar dataKey="Seuil Toléré (min)" fill="#CBD5E1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Analyse du Taux de Retard (%) par Service */}
        <div className="bg-slate-50/50 rounded-2xl p-4 border border-gray-100 flex flex-col justify-between space-y-3">
          <h3 className="text-sm font-bold text-gray-800 flex items-center gap-1.5">
            🎯 Taux d'Anomalie / Retard par Service
          </h3>
          <div className="space-y-3 flex-1 justify-center flex flex-col">
            {data.zones.map(z => (
              <div key={z.key} className="bg-white p-3 rounded-xl border border-gray-100 shadow-sm space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-gray-800">{z.nom}</span>
                  <span className={`font-bold px-2 py-0.5 rounded-full text-[11px] ${
                    z.taux_retard_pct > 20 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                  }`}>
                    {z.taux_retard_pct}% de retards
                  </span>
                </div>
                {/* Barre de progression (%) */}
                <div className="w-full bg-gray-100 h-2 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-500 ${
                      z.taux_retard_pct > 20 ? 'bg-red-500' : 'bg-blue-500'
                    }`}
                    style={{ width: `${Math.max(5, z.taux_retard_pct)}%` }}
                  />
                </div>
                <div className="flex justify-between text-[11px] text-gray-500">
                  <span>Dépassement moyen :</span>
                  <span className="font-bold text-gray-700">+{z.depassement} min / camion</span>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* ── 3. Tableau Détaillé par Zone ───────────────── */}
      <div className="mt-6 border-t pt-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
            <Info className="w-5 h-5 text-blue-600" /> Tableau Synthétique Détaillé par Étape
          </h3>
        </div>

        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-100 text-gray-700 text-xs uppercase font-semibold">
                <th className="p-3">Étape & Zone Usine</th>
                <th className="p-3">Temps Moyen</th>
                <th className="p-3">Objectif Max</th>
                <th className="p-3">Écart / Dépassement</th>
                <th className="p-3">% Retard Camions</th>
                <th className="p-3">Temps Perdu Total (Est.)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-xs">
              {data.zones.map(z => (
                <tr key={z.key} className={`hover:bg-slate-50/80 transition-colors ${
                  z.depassement > 0 ? 'bg-red-50/30' : ''
                }`}>
                  <td className="p-3">
                    <div className="font-bold text-gray-900">{z.nom}</div>
                    <div className="text-[11px] text-gray-400">{z.etape} — {z.action}</div>
                  </td>
                  <td className="p-3 font-bold font-mono text-gray-800">{z.temps_moyen} min</td>
                  <td className="p-3 text-gray-500 font-mono">{z.seuil_max} min</td>
                  <td className="p-3 font-bold">
                    {z.depassement > 0 ? (
                      <span className="text-red-600 flex items-center gap-1">
                        <AlertTriangle className="w-3.5 h-3.5" /> +{z.depassement} min
                      </span>
                    ) : (
                      <span className="text-green-600 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Conforme
                      </span>
                    )}
                  </td>
                  <td className="p-3 font-semibold text-gray-700">{z.taux_retard_pct}%</td>
                  <td className="p-3 font-mono font-semibold text-gray-700">
                    {z.temps_perdu_total_min} min
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
