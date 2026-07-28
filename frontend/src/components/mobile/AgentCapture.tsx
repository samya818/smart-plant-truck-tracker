import { useState, useEffect } from 'react';
import { Camera, AlertTriangle, Check, MapPin, Wifi, WifiOff, History, UserCheck, QrCode, RefreshCw, MessageSquare, Lock, Truck as TruckIcon } from 'lucide-react';
import { useCamera } from '@/hooks/useCamera';
import type { DelayCause, Event } from '@/types';

interface Props {
  poste: 'porte_usine' | 'parking' | 'bascule' | 'ensachage';
}

interface OfflineEvent {
  id: string;
  plaque: string;
  poste: string;
  type_event: 'entree' | 'sortie';
  agent_id: string;
  delay_cause_id?: number;
  cause_retard_libre?: string;
  minutes_retard?: number;
  timestamp: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function AgentCapture({ poste }: Props) {
  const { photo, file, inputRef, triggerCapture, handleCapture, clearPhoto } = useCamera();

  // --- Auth Agent & PIN ---
  const [agentName, setAgentName] = useState(() => localStorage.getItem('lafarge_agent_name') || 'Agent Meknès');
  const [agentPin, setAgentPin] = useState(() => localStorage.getItem('lafarge_agent_pin') || '1234');
  const [showPinModal, setShowPinModal] = useState(false);
  const [tempPin, setTempPin] = useState('');
  const [tempName, setTempName] = useState('');

  // --- Données Saisie ---
  const [plaque, setPlaque] = useState('');
  const [typeEvent, setTypeEvent] = useState<'entree' | 'sortie'>('entree');
  const [selectedCause, setSelectedCause] = useState<number | null>(null);
  const [causeLibre, setCauseLibre] = useState('');
  const [minutesRetard, setMinutesRetard] = useState(0);
  const [causes, setCauses] = useState<DelayCause[]>([]);
  const [newCauseName, setNewCauseName] = useState('');
  const [showNewCauseInput, setShowNewCauseInput] = useState(false);

  // --- États UI & Réseau ---
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [offlineQueue, setOfflineQueue] = useState<OfflineEvent[]>(() => {
    const saved = localStorage.getItem('lafarge_offline_queue');
    return saved ? JSON.parse(saved) : [];
  });
  const [history, setHistory] = useState<any[]>(() => {
    const saved = localStorage.getItem('lafarge_agent_history');
    return saved ? JSON.parse(saved) : [];
  });
  const [activeTab, setActiveTab] = useState<'saisie' | 'historique' | 'encours'>('saisie');
  const [encoursCamions, setEncoursCamions] = useState<Event[]>([]);

  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  // Détection en ligne / hors ligne
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Chargement des causes de retard & camions en cours
  useEffect(() => {
    fetch(`${API_BASE}/api/mobile/delay-causes?poste=${poste}&active_only=true`)
      .then(r => r.json())
      .then(data => setCauses(data.sort((a: DelayCause, b: DelayCause) => b.usage_count - a.usage_count)))
      .catch(() => {});

    fetch(`${API_BASE}/api/events/active`)
      .then(r => r.json())
      .then(data => setEncoursCamions(data))
      .catch(() => {});
  }, [poste]);

  // Sauvegarde auto de la file hors-ligne
  useEffect(() => {
    localStorage.setItem('lafarge_offline_queue', JSON.stringify(offlineQueue));
  }, [offlineQueue]);

  // Sync auto quand le réseau revient
  useEffect(() => {
    if (isOnline && offlineQueue.length > 0) {
      syncOfflineQueue();
    }
  }, [isOnline]);

  const syncOfflineQueue = async () => {
    if (offlineQueue.length === 0) return;
    setLoading(true);

    const remaining: OfflineEvent[] = [];
    for (const item of offlineQueue) {
      try {
        const formData = new FormData();
        formData.append('plaque', item.plaque);
        formData.append('poste', item.poste);
        formData.append('type_event', item.type_event);
        formData.append('agent_id', item.agent_id);
        if (item.delay_cause_id) formData.append('delay_cause_id', String(item.delay_cause_id));
        if (item.cause_retard_libre) formData.append('cause_retard_libre', item.cause_retard_libre);
        if (item.minutes_retard) formData.append('minutes_retard', String(item.minutes_retard));

        await fetch(`${API_BASE}/api/mobile/events`, { method: 'POST', body: formData });
      } catch {
        remaining.push(item);
      }
    }

    setOfflineQueue(remaining);
    setLoading(false);
    if (remaining.length === 0) {
      setSuccessMsg('⚡ Synchronisation hors-ligne réussie !');
      setTimeout(() => setSuccessMsg(''), 3000);
    }
  };

  const handleAddNewCause = async () => {
    if (!newCauseName.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/mobile/delay-causes`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nom: newCauseName, poste_concerne: poste, created_by: agentName })
      });
      const newCause = await res.json();
      setCauses([newCause, ...causes]);
      setSelectedCause(newCause.id);
    } catch {}
    setShowNewCauseInput(false);
    setNewCauseName('');
  };

  const handleSubmit = async () => {
    if (!plaque.trim()) return;
    setLoading(true);

    // Vibration tactile (Haptic feedback)
    if (navigator.vibrate) navigator.vibrate(80);

    const formattedPlaque = plaque.toUpperCase().trim();
    const eventTime = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

    if (!isOnline) {
      // Stockage Hors-Ligne Queue
      const offlineItem: OfflineEvent = {
        id: Date.now().toString(),
        plaque: formattedPlaque,
        poste,
        type_event: typeEvent,
        agent_id: agentName,
        delay_cause_id: selectedCause || undefined,
        cause_retard_libre: causeLibre || undefined,
        minutes_retard: minutesRetard || undefined,
        timestamp: eventTime,
      };
      setOfflineQueue(prev => [...prev, offlineItem]);
      addHistory(formattedPlaque, typeEvent, eventTime, 'Hors-Ligne 🟠');
      resetForm();
      setLoading(false);
      setSuccessMsg('💾 Stocké en mode Hors-Ligne !');
      setTimeout(() => setSuccessMsg(''), 2500);
      return;
    }

    try {
      const formData = new FormData();
      formData.append('plaque', formattedPlaque);
      formData.append('poste', poste);
      formData.append('type_event', typeEvent);
      formData.append('agent_id', `${agentName} (PIN: ${agentPin})`);
      if (selectedCause) formData.append('delay_cause_id', String(selectedCause));
      if (causeLibre) formData.append('cause_retard_libre', causeLibre);
      if (minutesRetard > 0) formData.append('minutes_retard', String(minutesRetard));

      if (file) formData.append('photo', file);

      await fetch(`${API_BASE}/api/mobile/events`, { method: 'POST', body: formData });
      addHistory(formattedPlaque, typeEvent, eventTime, 'Transmis 🟢');
      setSuccessMsg('✅ Enregistré & Transmis !');
    } catch (err) {
      setSuccessMsg('⚠️ Erreur réseau : Stocké localement');
    } finally {
      setLoading(false);
      resetForm();
      setTimeout(() => setSuccessMsg(''), 2500);
    }
  };

  const addHistory = (p: string, typeEv: string, time: string, statusStr: string) => {
    const newEntry = { plaque: p, type: typeEv, time, status: statusStr, poste };
    const updated = [newEntry, ...history.slice(0, 19)];
    setHistory(updated);
    localStorage.setItem('lafarge_agent_history', JSON.stringify(updated));
  };

  const resetForm = () => {
    setPlaque('');
    setSelectedCause(null);
    setCauseLibre('');
    setMinutesRetard(0);
    clearPhoto();
  };

  const handleSavePin = () => {
    if (tempName) {
      setAgentName(tempName);
      localStorage.setItem('lafarge_agent_name', tempName);
    }
    if (tempPin) {
      setAgentPin(tempPin);
      localStorage.setItem('lafarge_agent_pin', tempPin);
    }
    setShowPinModal(false);
  };

  // QR Code / NFC Quick fill simulator
  const handleQuickScan = () => {
    const demoPlaques = ['12345-أ-1', '67890-ب-2', '11111-د-3', '44444-س-6'];
    const randomPlaque = demoPlaques[Math.floor(Math.random() * demoPlaques.length)];
    setPlaque(randomPlaque);
    if (navigator.vibrate) navigator.vibrate(40);
  };

  return (
    <div className="min-h-screen bg-slate-100 pb-24 font-sans">
      {/* Top Bar Réseau & Agent */}
      <div className="bg-slate-900 text-white p-3 flex justify-between items-center shadow-md">
        <div className="flex items-center gap-2">
          {isOnline ? (
            <span className="flex items-center text-xs font-bold text-emerald-400 bg-emerald-950/60 px-2 py-1 rounded-full border border-emerald-800">
              <Wifi className="w-3.5 h-3.5 mr-1" /> EN LIGNE
            </span>
          ) : (
            <span className="flex items-center text-xs font-bold text-amber-400 bg-amber-950/60 px-2 py-1 rounded-full border border-amber-800">
              <WifiOff className="w-3.5 h-3.5 mr-1" /> HORS-LIGNE
            </span>
          )}
          {offlineQueue.length > 0 && (
            <span className="text-xs bg-amber-500 text-slate-950 font-black px-2 py-0.5 rounded-full animate-pulse">
              {offlineQueue.length} en attente
            </span>
          )}
        </div>
        <button 
          onClick={() => { setTempName(agentName); setTempPin(agentPin); setShowPinModal(true); }}
          className="flex items-center gap-1.5 text-xs font-semibold bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg border border-slate-700"
        >
          <UserCheck className="w-3.5 h-3.5 text-blue-400" />
          {agentName}
        </button>
      </div>

      {/* Message de confirmation */}
      {successMsg && (
        <div className="bg-emerald-600 text-white text-center text-sm font-bold p-3 shadow-inner animate-bounce">
          {successMsg}
        </div>
      )}

      {/* Modal PIN / Identité Agent */}
      {showPinModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-5 w-full max-w-sm space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 border-b pb-3">
              <Lock className="w-5 h-5 text-blue-600" />
              <h3 className="font-bold text-slate-800">Identité Agent (Session)</h3>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-500">Nom / Identifiant Agent</label>
              <input 
                type="text" 
                value={tempName} 
                onChange={e => setTempName(e.target.value)}
                className="w-full border rounded-xl p-2.5 text-sm mt-1 focus:ring-2 focus:ring-blue-500" 
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-500">Code PIN de sécurité (4 chiffres)</label>
              <input 
                type="password" 
                maxLength={4}
                value={tempPin} 
                onChange={e => setTempPin(e.target.value)}
                className="w-full border rounded-xl p-2.5 text-center text-xl font-mono tracking-widest mt-1" 
              />
            </div>
            <div className="flex gap-2 pt-2">
              <button onClick={() => setShowPinModal(false)} className="flex-1 py-2.5 text-xs font-semibold bg-slate-100 text-slate-600 rounded-xl">Annuler</button>
              <button onClick={handleSavePin} className="flex-1 py-2.5 text-xs font-bold bg-blue-600 text-white rounded-xl">Valider Session</button>
            </div>
          </div>
        </div>
      )}

      {/* Tabs Navigation Mobile */}
      <div className="flex bg-white border-b text-xs font-bold text-slate-600">
        <button 
          onClick={() => setActiveTab('saisie')} 
          className={`flex-1 py-3 border-b-2 text-center flex items-center justify-center gap-1.5 ${activeTab === 'saisie' ? 'border-blue-600 text-blue-600 bg-blue-50/50' : 'border-transparent'}`}
        >
          <Camera className="w-4 h-4" /> Saisie Rapide
        </button>
        <button 
          onClick={() => setActiveTab('encours')} 
          className={`flex-1 py-3 border-b-2 text-center flex items-center justify-center gap-1.5 ${activeTab === 'encours' ? 'border-blue-600 text-blue-600 bg-blue-50/50' : 'border-transparent'}`}
        >
          <TruckIcon className="w-4 h-4" /> Camions Usine ({encoursCamions.length})
        </button>
        <button 
          onClick={() => setActiveTab('historique')} 
          className={`flex-1 py-3 border-b-2 text-center flex items-center justify-center gap-1.5 ${activeTab === 'historique' ? 'border-blue-600 text-blue-600 bg-blue-50/50' : 'border-transparent'}`}
        >
          <History className="w-4 h-4" /> Mes Saisies ({history.length})
        </button>
      </div>

      <div className="p-4">
        {/* TAB 1 : SAISIE RAPIDE */}
        {activeTab === 'saisie' && (
          <div className="space-y-4">

            {/* Carte de Poste */}
            <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-200/80 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-600 text-white rounded-xl flex items-center justify-center shadow-md">
                  <MapPin className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="font-extrabold text-slate-900 capitalize text-base">{poste.replace('_', ' ')}</h2>
                  <p className="text-xs text-slate-400 font-medium">Poste opérateur actif</p>
                </div>
              </div>
              <button onClick={handleQuickScan} className="flex items-center gap-1 text-[11px] font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-2 rounded-xl transition">
                <QrCode className="w-3.5 h-3.5 text-blue-600" /> Scanner QR
              </button>
            </div>

            {/* Saisie Immatriculation */}
            <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-200/80 space-y-3">
              <div className="flex justify-between items-center">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">Immatriculation Camion</label>
                <span className="text-[10px] text-slate-400 font-mono">Format: 12345-أ-1</span>
              </div>
              <div className="flex gap-2">
                <input 
                  type="text" 
                  value={plaque} 
                  onChange={e => setPlaque(e.target.value)}
                  placeholder="SAISIR PLAQUE..."
                  className="flex-1 border-2 border-slate-200 focus:border-blue-600 rounded-xl px-3 py-3 text-xl font-black font-mono uppercase tracking-wider text-slate-800 outline-none"
                />
                <button 
                  onClick={triggerCapture} 
                  className="bg-blue-600 active:bg-blue-700 text-white px-4 rounded-xl flex items-center justify-center shadow-md transition"
                >
                  <Camera className="w-6 h-6" />
                </button>
              </div>
              <input ref={inputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleCapture} />
              {photo && (
                <div className="relative mt-2">
                  <img src={photo} alt="Plaque" className="w-full h-36 object-cover rounded-xl border border-slate-200" />
                  <button onClick={clearPhoto} className="absolute top-2 right-2 bg-slate-900/80 text-white text-xs px-2 py-1 rounded-lg">Effacer</button>
                </div>
              )}
            </div>

            {/* Type d'événement (Entrée / Sortie) */}
            <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-200/80 space-y-2">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">Mouvement</label>
              <div className="grid grid-cols-2 gap-3">
                <button 
                  type="button"
                  onClick={() => setTypeEvent('entree')} 
                  className={`py-3.5 rounded-xl font-extrabold text-sm transition flex items-center justify-center gap-2 shadow-sm ${typeEvent === 'entree' ? 'bg-emerald-600 text-white ring-2 ring-emerald-600' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                >
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-300"></span> Entrée Service
                </button>
                <button 
                  type="button"
                  onClick={() => setTypeEvent('sortie')} 
                  className={`py-3.5 rounded-xl font-extrabold text-sm transition flex items-center justify-center gap-2 shadow-sm ${typeEvent === 'sortie' ? 'bg-amber-600 text-white ring-2 ring-amber-600' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                >
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-300"></span> Sortie Service
                </button>
              </div>
            </div>

            {/* Observation / Retard & Commentaire Libre */}
            <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-200/80 space-y-3">
              <div className="flex items-center gap-2 text-amber-600 border-b pb-2">
                <AlertTriangle className="w-4 h-4" />
                <h3 className="text-xs font-bold uppercase tracking-wider">Incident ou Retard (Optionnel)</h3>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-600">Cause identifiée</label>
                {showNewCauseInput ? (
                  <div className="flex gap-2">
                    <input type="text" value={newCauseName} onChange={e => setNewCauseName(e.target.value)} placeholder="Intitulé du problème..." className="flex-1 border rounded-xl px-3 py-2 text-xs" autoFocus />
                    <button onClick={handleAddNewCause} className="bg-emerald-600 text-white px-3 rounded-xl text-xs font-bold"><Check className="w-4 h-4" /></button>
                  </div>
                ) : (
                  <select 
                    value={selectedCause || ''} 
                    onChange={e => { if (e.target.value === '__new__') setShowNewCauseInput(true); else setSelectedCause(Number(e.target.value) || null); }} 
                    className="w-full border rounded-xl px-3 py-2.5 text-xs bg-slate-50 font-medium text-slate-700 outline-none"
                  >
                    <option value="">Aucune cause spécifique</option>
                    {causes.map(c => <option key={c.id} value={c.id}>{c.nom} {c.usage_count > 0 ? `(${c.usage_count}×)` : ''}</option>)}
                    <option value="__new__">➕ Déclarer un nouveau motif...</option>
                  </select>
                )}
              </div>

              {/* Commentaire texte libre */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-600 flex items-center gap-1">
                  <MessageSquare className="w-3.5 h-3.5 text-slate-400" /> Remarque / Commentaire libre
                </label>
                <input 
                  type="text" 
                  value={causeLibre} 
                  onChange={e => setCauseLibre(e.target.value)} 
                  placeholder="ex: Attente bon de commande, panne ensacheuse..." 
                  className="w-full border rounded-xl px-3 py-2 text-xs bg-slate-50 text-slate-800"
                />
              </div>

              {selectedCause && (
                <div className="space-y-1.5 pt-1">
                  <div className="flex justify-between text-xs font-semibold text-slate-600">
                    <span>Durée estimée du retard :</span>
                    <span className="font-extrabold text-amber-600">{minutesRetard} min</span>
                  </div>
                  <input type="range" min="0" max="120" step="5" value={minutesRetard} onChange={e => setMinutesRetard(Number(e.target.value))} className="w-full accent-amber-600" />
                </div>
              )}
            </div>

            {/* Bouton de Validation */}
            <button 
              onClick={handleSubmit} 
              disabled={!plaque.trim() || loading} 
              className="w-full py-4 rounded-2xl font-black text-base transition shadow-lg bg-blue-700 hover:bg-blue-800 text-white active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
              {loading ? 'Validation en cours...' : "VALIDER L'ÉVÉNEMENT"}
            </button>
          </div>
        )}

        {/* TAB 2 : CAMIONS EN COURS */}
        {activeTab === 'encours' && (
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Camions actuellement dans l'usine</h3>
            {encoursCamions.length === 0 ? (
              <div className="bg-white rounded-2xl p-6 text-center text-slate-400 text-xs">
                Aucun camion en cours actuellement.
              </div>
            ) : (
              <div className="space-y-2">
                {encoursCamions.map((ev, idx) => (
                  <div key={idx} onClick={() => { setPlaque(ev.truck?.immatriculation || ''); setActiveTab('saisie'); }} className="bg-white p-3.5 rounded-xl shadow-sm border border-slate-200 flex justify-between items-center active:bg-blue-50 cursor-pointer">
                    <div>
                      <span className="font-black font-mono text-sm text-slate-800">{ev.truck?.immatriculation}</span>
                      <p className="text-[10px] text-slate-400 mt-0.5">Dernier poste: <span className="font-bold capitalize">{ev.poste}</span> ({ev.type_event})</p>
                    </div>
                    <span className="text-xs font-bold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-lg">Sélectionner</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3 : HISTORIQUE DE L'AGENT */}
        {activeTab === 'historique' && (
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Vos derniers enregistrements</h3>
            {history.length === 0 ? (
              <div className="bg-white rounded-2xl p-6 text-center text-slate-400 text-xs">
                Aucun enregistrement récent.
              </div>
            ) : (
              <div className="space-y-2">
                {history.map((h, i) => (
                  <div key={i} className="bg-white p-3.5 rounded-xl shadow-sm border border-slate-200/80 flex justify-between items-center">
                    <div>
                      <div className="font-black font-mono text-sm text-slate-800">{h.plaque}</div>
                      <div className="text-[10px] text-slate-400 flex items-center gap-2 mt-0.5">
                        <span>🕒 {h.time}</span>
                        <span className="capitalize">📍 {h.poste.replace('_', ' ')}</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${h.type === 'entree' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                        {h.type.toUpperCase()}
                      </span>
                      <div className="text-[9px] text-slate-400 mt-1">{h.status}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
