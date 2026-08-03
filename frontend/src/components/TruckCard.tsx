import { useEffect, useState } from 'react';
import { Truck, Clock, AlertTriangle, Circle, Navigation, TrendingUp, ChevronRight } from 'lucide-react';
import type { Event, DureesMoyennes } from '@/types';
import { getDureesMoyennes } from '@/services/api';

interface Props {
  immatriculation: string;
  events: Event[];
}

// ─── Les 6 étapes officielles du cycle LafargeHolcim Meknès ─────────────────
const CYCLE_STEPS = [
  {
    key: 'porte_usine_entree',
    zone: 'Porte Usine',
    action: 'Entrée & contrôle sécurité',
    icon: '①',
    color: 'blue',
    etaKey: null, // point de départ
  },
  {
    key: 'parking_entree',
    zone: 'Parking',
    action: "Zone d'attente avant pesage",
    icon: '②',
    color: 'indigo',
    etaKey: 'parking',
  },
  {
    key: 'bascule_entree',
    zone: 'Agence Logistique (Bascule)',
    action: '1er passage — Pesage à vide (Tare)',
    icon: '③',
    color: 'violet',
    etaKey: 'bascule_tare',
  },
  {
    key: 'ensachage_entree',
    zone: 'Expéditions / Ensachage',
    action: 'Chargement — Sacs de ciment',
    icon: '④',
    color: 'amber',
    etaKey: 'ensachage',
  },
  {
    key: 'bascule_sortie',
    zone: 'Agence Logistique (Bascule)',
    action: '2ème passage — Pesage plein (Brut)',
    icon: '③↩',
    color: 'orange',
    etaKey: 'bascule_brut',
  },
  {
    key: 'porte_usine_sortie',
    zone: 'Porte Usine',
    action: 'Sortie avec bon de livraison',
    icon: '⑤',
    color: 'green',
    etaKey: 'porte_sortie',
  },
] as const;


const COLOR_MAP: Record<string, { bg: string; text: string; border: string; badge: string; pulse: string }> = {
  blue:   { bg: 'bg-blue-50',   text: 'text-blue-700',   border: 'border-blue-400',   badge: 'bg-blue-500',   pulse: 'ring-blue-300'   },
  indigo: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-400', badge: 'bg-indigo-500', pulse: 'ring-indigo-300' },
  violet: { bg: 'bg-violet-50', text: 'text-violet-700', border: 'border-violet-400', badge: 'bg-violet-500', pulse: 'ring-violet-300' },
  amber:  { bg: 'bg-amber-50',  text: 'text-amber-700',  border: 'border-amber-400',  badge: 'bg-amber-500',  pulse: 'ring-amber-300'  },
  orange: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-400', badge: 'bg-orange-500', pulse: 'ring-orange-300' },
  green:  { bg: 'bg-green-50',  text: 'text-green-700',  border: 'border-green-400',  badge: 'bg-green-500',  pulse: 'ring-green-300'  },
};

// ─── Construction de la map étape → événement ────────────────────────────────
function buildStepMap(events: Event[]): Map<string, Event> {
  const map = new Map<string, Event>();
  let basculeTareAdded = false;
  let ensachagePassed = false;

  const sorted = [...events].sort(
    (a, b) => new Date(a.horodatage).getTime() - new Date(b.horodatage).getTime()
  );

  for (const ev of sorted) {
    if (ev.poste === 'porte_usine' && ev.type_event === 'entree') {
      map.set('porte_usine_entree', ev);
    } else if (ev.poste === 'parking' && ev.type_event === 'entree') {
      map.set('parking_entree', ev);
    } else if (ev.poste === 'bascule' && ev.type_event === 'entree' && !basculeTareAdded) {
      map.set('bascule_entree', ev);
      basculeTareAdded = true;
    } else if (ev.poste === 'ensachage' && ev.type_event === 'entree') {
      map.set('ensachage_entree', ev);
    } else if (ev.poste === 'ensachage' && ev.type_event === 'sortie') {
      ensachagePassed = true;
    } else if (ev.poste === 'bascule' && ev.type_event === 'sortie' && ensachagePassed) {
      map.set('bascule_sortie', ev);
    } else if (ev.poste === 'porte_usine' && ev.type_event === 'sortie') {
      map.set('porte_usine_sortie', ev);
    }
  }
  return map;
}

// ─── Index de l'étape active (dernière atteinte) ─────────────────────────────
function getActiveStepIndex(stepMap: Map<string, Event>): number {
  for (let i = CYCLE_STEPS.length - 1; i >= 0; i--) {
    if (stepMap.has(CYCLE_STEPS[i].key)) return i;
  }
  return -1;
}

// ─── Formatage heure ──────────────────────────────────────────────────────────
function fmtHeure(iso: string) {
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

// ─── Formatage durée entre deux événements ───────────────────────────────────
function fmtDuree(from: Event, to: Event): string {
  const mins = Math.round(
    (new Date(to.horodatage).getTime() - new Date(from.horodatage).getTime()) / 60000
  );
  return `${mins} min`;
}

// ─── Calcul des ETAs cumulatifs depuis maintenant ────────────────────────────
function calcEtas(
  activeIdx: number,
  durees: DureesMoyennes,
  activeStepEntreeTime: Date | null
): Map<number, string> {
  const etaMap = new Map<number, string>();
  if (activeIdx < 0 || !activeStepEntreeTime) return etaMap;

  // Durées pour chaque étape future (en minutes)
  const stepDurations: (number | null)[] = [
    null,                        // ① Porte usine entrée — pas de durée
    durees.parking.moyenne,      // ② Parking
    durees.bascule_tare.moyenne, // ③ Bascule tare
    durees.ensachage.moyenne,    // ④ Ensachage
    durees.bascule_brut.moyenne, // ③↩ Bascule brut
    durees.porte_sortie.moyenne, // ⑤ Porte sortie
  ];

  // Temps accumulé depuis maintenant
  let accMs = Date.now() - activeStepEntreeTime.getTime(); // temps déjà passé à l'étape active
  // On part du temps restant à l'étape active (duree_moy - temps_ecoule, min 0)
  const dureeActive = stepDurations[activeIdx] ?? 0;
  const resteActive = Math.max(0, dureeActive * 60000 - accMs);
  let cursor = Date.now() + resteActive;

  for (let i = activeIdx + 1; i < CYCLE_STEPS.length; i++) {
    const d = stepDurations[i];
    etaMap.set(i, new Date(cursor).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }));
    cursor += (d ?? 5) * 60000;
  }

  return etaMap;
}

// ─── Composant principal ──────────────────────────────────────────────────────
export function TruckCard({ immatriculation, events }: Props) {
  const [durees, setDurees] = useState<DureesMoyennes | null>(null);
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  useEffect(() => {
    getDureesMoyennes().then(setDurees).catch(() => null);
  }, []);

  const stepMap = buildStepMap(events);
  const activeIdx = getActiveStepIndex(stepMap);
  const isTermine = stepMap.has('porte_usine_sortie');
  const hasAnomalie = events.some(e => (e.minutes_retard || 0) > 0);

  // Zone actuelle
  const activeStep = activeIdx >= 0 ? CYCLE_STEPS[activeIdx] : null;

  // Image la plus récente
  const lastImageEvent = [...events].reverse().find(e => e.image_path);
  const imageUrl = lastImageEvent?.image_path ? `${apiBase}${lastImageEvent.image_path}` : null;

  // Durée totale en cours
  const entreeEv = stepMap.get('porte_usine_entree');
  const sortieEv = stepMap.get('porte_usine_sortie');
  const dureeTotale = entreeEv && sortieEv
    ? Math.round((new Date(sortieEv.horodatage).getTime() - new Date(entreeEv.horodatage).getTime()) / 60000)
    : entreeEv
    ? Math.round((Date.now() - new Date(entreeEv.horodatage).getTime()) / 60000)
    : null;

  // ETAs des étapes futures
  const activeEntreeTime = activeStep ? (stepMap.get(activeStep.key)?.horodatage
    ? new Date(stepMap.get(activeStep.key)!.horodatage)
    : null) : null;
  const etaMap = durees && !isTermine
    ? calcEtas(activeIdx, durees, activeEntreeTime)
    : new Map<number, string>();

  return (
    <div className={`bg-white border-2 rounded-2xl overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col ${
      isTermine ? 'border-green-200' : hasAnomalie ? 'border-red-300' : 'border-gray-100'
    }`}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className={`px-4 py-3 flex items-center justify-between ${
        isTermine ? 'bg-gradient-to-r from-green-50 to-emerald-50'
          : hasAnomalie ? 'bg-gradient-to-r from-red-50 to-orange-50'
          : 'bg-gradient-to-r from-slate-50 to-blue-50'
      }`}>
        <div className="flex items-center gap-2">
          <Truck className={`w-5 h-5 ${isTermine ? 'text-green-600' : hasAnomalie ? 'text-red-500' : 'text-blue-600'}`} />
          <span className="font-mono font-bold text-base tracking-widest text-gray-800">{immatriculation}</span>
        </div>
        <div className="flex items-center gap-2">
          {events.some(e => e.necesita_confirmacion) && (
            <span className="flex items-center gap-1 text-xs text-amber-800 bg-amber-100 px-2 py-0.5 rounded-full font-bold border border-amber-300 animate-pulse" title="Confiance OCR < 65% - confirmation requise">
              ⚠️ OCR faible (<65%) — À confirmer
            </span>
          )}
          {hasAnomalie && (
            <span className="flex items-center gap-1 text-xs text-red-600 bg-red-100 px-2 py-0.5 rounded-full font-medium">
              <AlertTriangle className="w-3 h-3" /> Retard
            </span>
          )}
          <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${
            isTermine ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
          }`}>
            {isTermine ? '✅ Terminé' : '🔄 En cours'}
          </span>
        </div>
      </div>

      {/* ── Zone actuelle (camions en cours uniquement) ─────────────────────── */}
      {!isTermine && activeStep && (
        <div className={`px-4 py-2.5 border-b flex items-center gap-3 ${COLOR_MAP[activeStep.color].bg}`}>
          <div className={`w-2.5 h-2.5 rounded-full ${COLOR_MAP[activeStep.color].badge} animate-pulse`} />
          <div className="flex-1 min-w-0">
            <div className={`text-xs font-bold uppercase tracking-wider ${COLOR_MAP[activeStep.color].text}`}>
              📍 Zone actuelle
            </div>
            <div className="text-sm font-semibold text-gray-800 truncate">{activeStep.zone}</div>
            <div className="text-xs text-gray-500 truncate">{activeStep.action}</div>
          </div>
          {dureeTotale !== null && (
            <div className={`text-right flex-shrink-0 ${dureeTotale > 120 ? 'text-red-600' : 'text-gray-500'}`}>
              <div className="text-xs font-medium">En usine</div>
              <div className="text-sm font-bold flex items-center gap-0.5">
                <Clock className="w-3 h-3" /> {dureeTotale} min
                {dureeTotale > 120 && ' ⚠️'}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Image camion ────────────────────────────────────────────────────── */}
      {imageUrl && (
        <div className="h-24 w-full overflow-hidden bg-gray-100 border-b">
          <img
            src={imageUrl}
            alt={`Camion ${immatriculation}`}
            className="w-full h-full object-cover hover:scale-105 transition-transform duration-300"
          />
        </div>
      )}

      {/* ── Timeline ────────────────────────────────────────────────────────── */}
      <div className="px-4 py-3 flex-1">
        <div className="relative">
          {/* Ligne verticale */}
          <div className="absolute left-[13px] top-4 bottom-4 w-0.5 bg-gray-100 z-0" />

          <div className="space-y-1.5">
            {CYCLE_STEPS.map((step, idx) => {
              const ev = stepMap.get(step.key);
              const done = !!ev;
              const isCurrentStep = idx === activeIdx && !isTermine;
              const isFuture = !done && !isCurrentStep;
              const colors = COLOR_MAP[step.color];
              const eta = etaMap.get(idx);

              // Durée passée entre cette étape et la suivante (si les deux sont faites)
              const nextDoneEv = done && idx < CYCLE_STEPS.length - 1
                ? stepMap.get(CYCLE_STEPS[idx + 1].key)
                : null;

              return (
                <div key={step.key} className="flex items-start gap-2.5 relative z-10">
                  {/* Icône état */}
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 border-2 text-xs font-bold transition-all ${
                    isCurrentStep
                      ? `${colors.bg} ${colors.border} ring-2 ${colors.pulse} ring-offset-1 animate-pulse`
                      : done
                      ? `${colors.bg} ${colors.border}`
                      : 'bg-gray-50 border-gray-200'
                  }`}>
                    {isCurrentStep ? (
                      <Navigation className={`w-3.5 h-3.5 ${colors.text}`} />
                    ) : done ? (
                      <span>{step.icon}</span>
                    ) : (
                      <Circle className="w-3 h-3 text-gray-300" />
                    )}
                  </div>

                  {/* Contenu */}
                  <div className={`flex-1 rounded-xl px-3 py-2 transition-all border ${
                    isCurrentStep
                      ? `${colors.bg} ${colors.border} shadow-sm`
                      : done
                      ? `${colors.bg} border-transparent`
                      : 'bg-gray-50 border-transparent'
                  }`}>
                    <div className="flex items-start justify-between gap-1">
                      <div className="min-w-0">
                        {/* Nom de la zone */}
                        <div className={`text-xs font-bold leading-tight ${
                          isCurrentStep ? colors.text
                            : done ? colors.text
                            : 'text-gray-400'
                        }`}>
                          {step.zone}
                        </div>
                        {/* Action */}
                        <div className={`text-xs leading-tight mt-0.5 ${
                          isCurrentStep ? 'text-gray-600'
                            : done ? 'text-gray-500'
                            : 'text-gray-350'
                        }`}>
                          {step.action}
                        </div>
                      </div>

                      <div className="text-right flex-shrink-0">
                        {/* Heure réelle si fait */}
                        {ev && (
                          <div className="flex items-center gap-0.5 text-xs text-gray-500 font-mono">
                            <Clock className="w-2.5 h-2.5" />
                            {fmtHeure(ev.horodatage)}
                          </div>
                        )}
                        {/* ETA si étape future */}
                        {isFuture && eta && !isTermine && (
                          <div className="flex items-center gap-0.5 text-xs text-blue-500 font-mono italic">
                            <ChevronRight className="w-2.5 h-2.5" />
                            ~{eta}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Durée passée entre cette étape et la suivante */}
                    {done && nextDoneEv && (
                      <div className="mt-1 text-xs text-gray-400 flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" />
                        Durée : {fmtDuree(ev!, nextDoneEv)}
                      </div>
                    )}

                    {/* Cause retard */}
                    {ev?.cause?.nom && (
                      <div className="mt-1 text-xs text-red-500 flex items-center gap-1">
                        <AlertTriangle className="w-2.5 h-2.5" />
                        {ev.cause.nom}{ev.minutes_retard ? ` (+${ev.minutes_retard} min)` : ''}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      {isTermine && dureeTotale !== null && (
        <div className="px-4 py-2 bg-green-50 border-t border-green-100 flex items-center justify-between">
          <span className="text-xs text-green-600 font-medium">Cycle complet</span>
          <span className={`text-xs font-bold flex items-center gap-1 ${dureeTotale > 120 ? 'text-red-600' : 'text-green-700'}`}>
            <Clock className="w-3 h-3" /> {dureeTotale} min total
          </span>
        </div>
      )}

      {/* ETA sortie globale */}
      {!isTermine && etaMap.has(CYCLE_STEPS.length - 1) && (
        <div className="px-4 py-2 bg-blue-50 border-t border-blue-100 flex items-center justify-between">
          <span className="text-xs text-blue-600 font-medium flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> Sortie estimée
          </span>
          <span className="text-xs font-bold text-blue-700 font-mono">
            ~{etaMap.get(CYCLE_STEPS.length - 1)}
          </span>
        </div>
      )}
    </div>
  );
}
