import { useState, useEffect } from 'react';
import { Camera, AlertTriangle, Check, MapPin } from 'lucide-react';
import { useCamera } from '@/hooks/useCamera';
import type { DelayCause } from '@/types';

interface Props {
  poste: 'porte_usine' | 'parking' | 'bascule' | 'ensachage';
  agentId: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function AgentCapture({ poste, agentId }: Props) {
  const { photo, file, inputRef, triggerCapture, handleCapture, clearPhoto } = useCamera();
  const [causes, setCauses] = useState<DelayCause[]>([]);
  const [selectedCause, setSelectedCause] = useState<number | null>(null);
  const [newCauseName, setNewCauseName] = useState('');
  const [showNewCauseInput, setShowNewCauseInput] = useState(false);
  const [plaque, setPlaque] = useState('');
  const [typeEvent, setTypeEvent] = useState<'entree' | 'sortie'>('entree');
  const [minutesRetard, setMinutesRetard] = useState(0);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/mobile/delay-causes?poste=${poste}&active_only=true`)
      .then(r => r.json())
      .then(data => setCauses(data.sort((a: DelayCause, b: DelayCause) => b.usage_count - a.usage_count)));
  }, [poste]);

  const handleAddNewCause = async () => {
    if (!newCauseName.trim()) return;
    const res = await fetch(`${API_BASE}/api/mobile/delay-causes`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nom: newCauseName, poste_concerne: poste, created_by: agentId })
    });
    const newCause = await res.json();
    setCauses([newCause, ...causes]);
    setSelectedCause(newCause.id);
    setShowNewCauseInput(false);
    setNewCauseName('');
  };

  const handleSubmit = async () => {
    if (!plaque.trim()) return;
    setLoading(true);

    const formData = new FormData();
    formData.append('plaque', plaque.toUpperCase().trim());
    formData.append('poste', poste);
    formData.append('type_event', typeEvent);
    formData.append('agent_id', agentId);
    if (selectedCause) formData.append('delay_cause_id', String(selectedCause));
    if (minutesRetard > 0) formData.append('minutes_retard', String(minutesRetard));

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => {
          formData.append('gps_lat', String(pos.coords.latitude));
          formData.append('gps_lon', String(pos.coords.longitude));
        }, () => {}, { timeout: 3000 }
      );
    }
    if (file) formData.append('photo', file);

    await fetch(`${API_BASE}/api/mobile/events`, { method: 'POST', body: formData });

    setLoading(false);
    setSuccess(true);
    setTimeout(() => {
      setSuccess(false);
      setPlaque('');
      setSelectedCause(null);
      setMinutesRetard(0);
      clearPhoto();
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4 space-y-4 pb-24">
      <div className="bg-white rounded-xl p-4 shadow-sm flex items-center gap-3">
        <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
          <MapPin className="w-5 h-5 text-blue-600" />
        </div>
        <div>
          <h2 className="font-bold text-gray-900 capitalize">{poste.replace('_', ' ')}</h2>
          <p className="text-xs text-gray-500">Agent: {agentId}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl p-4 shadow-sm space-y-3">
        <label className="text-sm font-medium text-gray-700">Immatriculation</label>
        <div className="flex gap-2">
          <input type="text" value={plaque} onChange={e => setPlaque(e.target.value)}
            placeholder="ex: 45231-أ-12"
            className="flex-1 border rounded-lg px-3 py-3 text-lg font-mono uppercase" />
          <button onClick={triggerCapture} className="bg-blue-600 text-white px-4 rounded-lg flex items-center gap-2">
            <Camera className="w-5 h-5" />
          </button>
        </div>
        <input ref={inputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleCapture} />
        {photo && <img src={photo} alt="Plaque" className="w-full h-32  object-cover rounded-lg" />}
      </div>

      <div className="bg-white rounded-xl p-4 shadow-sm space-y-3">
        <label className="text-sm font-medium text-gray-700">Type d'événement</label>
        <div className="grid grid-cols-2 gap-2">
          <button onClick={() => setTypeEvent('entree')} className={`py-3 rounded-lg font-medium transition ${typeEvent === 'entree' ? 'bg-green-600 text-white' : 'bg-gray-100 text-gray-600'}`}>Entrée</button>
          <button onClick={() => setTypeEvent('sortie')} className={`py-3 rounded-lg font-medium transition ${typeEvent === 'sortie' ? 'bg-orange-600 text-white' : 'bg-gray-100 text-gray-600'}`}>Sortie</button>
        </div>
      </div>

      <div className="bg-white rounded-xl p-4 shadow-sm space-y-3">
        <div className="flex items-center gap-2 text-orange-600">
          <AlertTriangle className="w-5 h-5" />
          <h3 className="font-medium">Signaler un retard (optionnel)</h3>
        </div>
        <div className="space-y-2">
          <label className="text-sm text-gray-600">Cause identifiée</label>
          {showNewCauseInput ? (
            <div className="flex gap-2">
              <input type="text" value={newCauseName} onChange={e => setNewCauseName(e.target.value)} placeholder="Nouvelle cause..." className="flex-1 border rounded-lg px-3 py-2 text-sm" autoFocus />
              <button onClick={handleAddNewCause} className="bg-green-600 text-white px-3 rounded-lg text-sm"><Check className="w-4 h-4" /></button>
            </div>
          ) : (
            <select value={selectedCause || ''} onChange={e => { if (e.target.value === '__new__') setShowNewCauseInput(true); else setSelectedCause(Number(e.target.value) || null); }} className="w-full border rounded-lg px-3 py-3 text-sm bg-white">
              <option value="">Aucun retard</option>
              {causes.map(c => <option key={c.id} value={c.id}>{c.nom} {c.usage_count > 0 ? `(${c.usage_count}×)` : ''}</option>)}
              <option value="__new__">➕ Ajouter une nouvelle cause...</option>
            </select>
          )}
        </div>
        {selectedCause && (
          <div className="space-y-2">
            <label className="text-sm text-gray-600">Minutes de retard: <span className="font-bold text-orange-600">{minutesRetard} min</span></label>
            <input type="range" min="0" max="120" step="5" value={minutesRetard} onChange={e => setMinutesRetard(Number(e.target.value))} className="w-full" />
            <div className="flex justify-between text-xs text-gray-400"><span>0</span><span>60</span><span>120</span></div>
          </div>
        )}
      </div>

      <button onClick={handleSubmit} disabled={!plaque.trim() || loading} className={`w-full py-4 rounded-xl font-bold text-lg transition shadow-lg ${success ? 'bg-green-500 text-white' : 'bg-blue-700 text-white active:scale-95 disabled:opacity-50'}`}>
        {loading ? 'Enregistrement...' : success ? '✅ Enregistré !' : "Valider l'événement"}
      </button>
    </div>
  );
}
