import { useState, useEffect, useCallback } from 'react';
import {
  CheckCircle2, XCircle, AlertTriangle, Clock, Camera,
  RefreshCw, ShieldCheck, Edit3, Truck, Eye
} from 'lucide-react';

const API_BASE = '';

interface PendingEvent {
  id: number;
  truck_id: number;
  poste: string;
  type_event: 'entree' | 'sortie';
  horodatage: string;
  source: string;
  confiance_ocr: number | null;
  necesita_confirmacion: boolean;
  image_path: string | null;
  truck: {
    id: number;
    immatriculation: string;
    type_camion: string;
    transporteur: { nom: string } | null;
  } | null;
}

const POSTE_LABELS: Record<string, string> = {
  porte_usine: '🚪 Porte Usine',
  parking: '🅿️ Parking',
  bascule: '⚖️ Bascule',
  ensachage: '📦 Ensachage',
};

const CONF_COLOR = (c: number | null) => {
  if (c === null) return 'text-gray-400';
  if (c >= 0.60) return 'text-amber-600';
  if (c >= 0.50) return 'text-orange-600';
  return 'text-red-600';
};

const CONF_BG = (c: number | null) => {
  if (c === null) return 'bg-gray-100';
  if (c >= 0.60) return 'bg-amber-50 border-amber-200';
  if (c >= 0.50) return 'bg-orange-50 border-orange-200';
  return 'bg-red-50 border-red-200';
};

export default function ConfirmationPage() {
  const [events, setEvents] = useState<PendingEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState<number | null>(null);

  // Correction de plaque (par event ID)
  const [editingPlaque, setEditingPlaque] = useState<Record<number, string>>({});
  const [showEditFor, setShowEditFor] = useState<number | null>(null);

  // Preview image
  const [previewImg, setPreviewImg] = useState<string | null>(null);

  const fetchPending = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/events/pending-confirmation`);
      if (!res.ok) throw new Error(`Erreur ${res.status}`);
      setEvents(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPending();
    // Polling toutes les 20s pour voir les nouvelles détections
    const interval = setInterval(fetchPending, 20_000);
    return () => clearInterval(interval);
  }, [fetchPending]);

  const handleConfirm = async (event: PendingEvent) => {
    setProcessing(event.id);
    const plaque_corrigee = editingPlaque[event.id]?.trim() || null;
    try {
      const res = await fetch(`${API_BASE}/api/events/${event.id}/confirm`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plaque_corrigee }),
      });
      if (!res.ok) throw new Error(await res.text());
      setEvents(prev => prev.filter(e => e.id !== event.id));
      setShowEditFor(null);
    } catch (e: any) {
      setError(`Erreur confirmation : ${e.message}`);
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (eventId: number) => {
    if (!window.confirm('Rejeter cet event ? Il sera supprimé définitivement de la base de données.')) return;
    setProcessing(eventId);
    try {
      const res = await fetch(`${API_BASE}/api/events/${eventId}/reject`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raison: 'Rejeté manuellement par agent' }),
      });
      if (!res.ok) throw new Error(await res.text());
      setEvents(prev => prev.filter(e => e.id !== eventId));
    } catch (e: any) {
      setError(`Erreur rejet : ${e.message}`);
    } finally {
      setProcessing(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-amber-50 to-orange-50 p-6">

      {/* Modal preview image */}
      {previewImg && (
        <div
          className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
          onClick={() => setPreviewImg(null)}
        >
          <div className="relative max-w-2xl w-full" onClick={e => e.stopPropagation()}>
            <img src={previewImg} alt="Capture caméra" className="rounded-2xl w-full shadow-2xl" />
            <button
              onClick={() => setPreviewImg(null)}
              className="absolute top-3 right-3 bg-white/90 hover:bg-white rounded-full p-2 shadow"
            >
              <XCircle className="w-5 h-5 text-gray-700" />
            </button>
          </div>
        </div>
      )}

      {/* ── En-tête ── */}
      <div className="mb-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-extrabold text-gray-900 flex items-center gap-3">
              <ShieldCheck className="w-8 h-8 text-amber-600" />
              File de Confirmation OCR
            </h1>
            <p className="text-sm text-gray-500 mt-1 max-w-xl">
              Ces événements ont été détectés par la caméra avec une confiance OCR entre{' '}
              <strong>45% et 65%</strong> — trop incertains pour être automatiquement validés.
              Un agent doit confirmer ou corriger la plaque lue.
            </p>
          </div>
          <button
            onClick={fetchPending}
            className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-xl shadow-sm hover:bg-gray-50 transition-colors text-sm font-medium text-gray-600"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Actualiser
          </button>
        </div>

        {/* Légende confiance */}
        <div className="mt-4 flex flex-wrap gap-3 text-xs font-medium">
          <span className="px-3 py-1.5 rounded-full bg-red-100 text-red-700 border border-red-200">
            🔴 45–50% : Très incertain
          </span>
          <span className="px-3 py-1.5 rounded-full bg-orange-100 text-orange-700 border border-orange-200">
            🟠 50–60% : Douteux
          </span>
          <span className="px-3 py-1.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
            🟡 60–65% : Limite acceptable
          </span>
        </div>
      </div>

      {/* Erreur */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 mb-6 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      {/* Chargement */}
      {loading && events.length === 0 && (
        <div className="flex items-center justify-center h-64">
          <div className="text-center space-y-3">
            <RefreshCw className="w-10 h-10 text-amber-500 animate-spin mx-auto" />
            <p className="text-gray-500">Chargement des détections en attente...</p>
          </div>
        </div>
      )}

      {/* Aucun event en attente */}
      {!loading && events.length === 0 && !error && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-12 text-center">
          <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-gray-800 mb-2">File vide — tout est validé ✓</h2>
          <p className="text-gray-500 text-sm">
            Aucune détection OCR en attente de confirmation. La caméra fonctionne avec une bonne confiance.
          </p>
        </div>
      )}

      {/* Liste des events en attente */}
      {events.length > 0 && (
        <div className="space-y-4">
          {/* Compteur */}
          <div className="flex items-center gap-2 text-sm font-semibold text-amber-800 bg-amber-100 border border-amber-200 px-4 py-2.5 rounded-xl w-fit">
            <AlertTriangle className="w-4 h-4" />
            {events.length} détection{events.length > 1 ? 's' : ''} en attente de validation
          </div>

          {events.map(ev => {
            const conf = ev.confiance_ocr;
            const isProcessing = processing === ev.id;
            const isEditing = showEditFor === ev.id;
            const imageUrl = ev.image_path
              ? `${API_BASE}${ev.image_path.startsWith('/') ? '' : '/'}${ev.image_path}`
              : null;

            return (
              <div
                key={ev.id}
                className={`bg-white rounded-2xl shadow-sm border-2 p-5 transition-all duration-300 ${
                  isProcessing ? 'opacity-50 pointer-events-none' : ''
                } ${CONF_BG(conf)}`}
              >
                <div className="flex flex-col lg:flex-row gap-5">

                  {/* ── Miniature image ── */}
                  <div className="flex-shrink-0">
                    {imageUrl ? (
                      <button
                        onClick={() => setPreviewImg(imageUrl)}
                        className="relative block w-32 h-24 rounded-xl overflow-hidden border border-gray-200 hover:ring-2 hover:ring-amber-400 transition-all group"
                      >
                        <img src={imageUrl} alt="Capture" className="w-full h-full object-cover" />
                        <div className="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                          <Eye className="w-6 h-6 text-white" />
                        </div>
                      </button>
                    ) : (
                      <div className="w-32 h-24 rounded-xl bg-gray-100 border border-gray-200 flex flex-col items-center justify-center gap-1 text-gray-400">
                        <Camera className="w-7 h-7" />
                        <span className="text-[10px]">Pas d'image</span>
                      </div>
                    )}
                  </div>

                  {/* ── Infos event ── */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                      <div>
                        {/* Plaque lue par OCR */}
                        <div className="flex items-center gap-2 mb-1">
                          <Truck className="w-4 h-4 text-gray-500 flex-shrink-0" />
                          <span className="text-lg font-extrabold font-mono text-gray-900">
                            {ev.truck?.immatriculation ?? 'Inconnue'}
                          </span>
                          {ev.truck?.transporteur && (
                            <span className="text-xs text-gray-400 font-normal">
                              · {ev.truck.transporteur.nom}
                            </span>
                          )}
                        </div>
                        {/* Poste + Type */}
                        <div className="flex flex-wrap gap-2 text-xs">
                          <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-semibold">
                            {POSTE_LABELS[ev.poste] ?? ev.poste}
                          </span>
                          <span className={`px-2 py-0.5 rounded-full font-semibold ${
                            ev.type_event === 'entree'
                              ? 'bg-green-100 text-green-700'
                              : 'bg-blue-100 text-blue-700'
                          }`}>
                            {ev.type_event === 'entree' ? '↗ Entrée' : '↙ Sortie'}
                          </span>
                          <span className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                            Event #{ev.id}
                          </span>
                        </div>
                      </div>

                      {/* Confiance OCR */}
                      <div className="text-right flex-shrink-0">
                        <div className={`text-2xl font-extrabold ${CONF_COLOR(conf)}`}>
                          {conf !== null ? `${(conf * 100).toFixed(0)}%` : '—'}
                        </div>
                        <div className="text-[11px] text-gray-400">Confiance OCR</div>
                        {/* Barre de confiance */}
                        <div className="w-20 bg-gray-100 rounded-full h-1.5 mt-1 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              (conf ?? 0) >= 0.60 ? 'bg-amber-400' :
                              (conf ?? 0) >= 0.50 ? 'bg-orange-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${((conf ?? 0) / 0.65) * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    {/* Horodatage */}
                    <div className="flex items-center gap-1.5 text-xs text-gray-400 mb-4">
                      <Clock className="w-3.5 h-3.5" />
                      Détecté le {new Date(ev.horodatage).toLocaleString('fr-FR')}
                      <span className="text-gray-300 mx-1">·</span>
                      Source : <strong className="text-gray-500">{ev.source}</strong>
                    </div>

                    {/* ── Zone correction plaque ── */}
                    {isEditing && (
                      <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-xl">
                        <label className="block text-xs font-semibold text-blue-700 mb-1.5 flex items-center gap-1">
                          <Edit3 className="w-3.5 h-3.5" />
                          Corriger la plaque (optionnel — laisser vide pour confirmer telle quelle)
                        </label>
                        <input
                          type="text"
                          placeholder={ev.truck?.immatriculation ?? 'Ex: 12345-A-1'}
                          value={editingPlaque[ev.id] ?? ''}
                          onChange={e => setEditingPlaque(prev => ({ ...prev, [ev.id]: e.target.value }))}
                          className="w-full px-3 py-2 text-sm font-mono border border-blue-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                          autoFocus
                        />
                        <p className="text-[11px] text-blue-500 mt-1">
                          La correction est appliquée au camion en DB et sera visible dans tout l'historique.
                        </p>
                      </div>
                    )}

                    {/* ── Actions ── */}
                    <div className="flex flex-wrap gap-2">
                      {/* Bouton Confirmer */}
                      <button
                        onClick={() => handleConfirm(ev)}
                        disabled={isProcessing}
                        className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-xl transition-colors shadow-sm"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        {editingPlaque[ev.id]?.trim() ? 'Confirmer avec correction' : 'Confirmer la plaque'}
                      </button>

                      {/* Bouton Modifier la plaque */}
                      <button
                        onClick={() => setShowEditFor(isEditing ? null : ev.id)}
                        className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl transition-colors border ${
                          isEditing
                            ? 'bg-blue-50 border-blue-300 text-blue-700 hover:bg-blue-100'
                            : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        <Edit3 className="w-4 h-4" />
                        {isEditing ? 'Annuler correction' : 'Corriger plaque'}
                      </button>

                      {/* Bouton Rejeter */}
                      <button
                        onClick={() => handleReject(ev.id)}
                        disabled={isProcessing}
                        className="flex items-center gap-2 px-4 py-2 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 text-sm font-semibold rounded-xl transition-colors"
                      >
                        <XCircle className="w-4 h-4" />
                        Fausse détection
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
