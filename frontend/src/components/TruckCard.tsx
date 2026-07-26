import { Truck, MapPin, Clock } from 'lucide-react';
import type { Event } from '@/types';

interface Props { event: Event; }

const posteLabels: Record<string, string> = {
  porte_usine: 'Porte Usine', parking: 'Parking',
  bascule: 'Bascule', ensachage: 'Ensachage',
};

export function TruckCard({ event }: Props) {
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const imageUrl = event.image_path ? `${apiBase}${event.image_path}` : null;

  return (
    <div className="bg-white border rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow flex flex-col">
      {imageUrl && (
        <div className="h-32 w-full overflow-hidden bg-gray-100 border-b">
          <img 
            src={imageUrl} 
            alt={`Camion ${event.truck?.immatriculation}`} 
            className="w-full h-full object-cover hover:scale-105 transition-transform duration-300"
          />
        </div>
      )}
      <div className="p-4 flex-1 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Truck className="w-5 h-5 text-blue-600" />
              <span className="font-mono font-bold text-lg">{event.truck?.immatriculation || 'Inconnu'}</span>
            </div>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${event.type_event === 'entree' ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'}`}>
              {event.type_event === 'entree' ? 'Entrée' : 'Sortie'}
            </span>
          </div>
          <div className="space-y-1 text-sm text-gray-600">
            <div className="flex items-center gap-2"><MapPin className="w-4 h-4" /><span>{posteLabels[event.poste] || event.poste}</span></div>
            <div className="flex items-center gap-2"><Clock className="w-4 h-4" /><span>{new Date(event.horodatage).toLocaleTimeString('fr-FR')}</span></div>
            {event.source !== 'camera' && <span className="text-xs text-blue-600">Source: {event.source}</span>}
          </div>
        </div>
        {event.cause?.nom && (
          <div className="mt-2 p-2 bg-red-50 rounded text-xs text-red-700">
            ⚠️ {event.cause.nom} {event.minutes_retard ? `(${event.minutes_retard} min)` : ''}
          </div>
        )}
      </div>
    </div>
  );
}
