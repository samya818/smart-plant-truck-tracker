import { useState } from 'react';
import { AgentCapture } from '@/components/mobile/AgentCapture';

export default function MobilePage() {
  const [poste, setPoste] = useState<'porte_usine' | 'parking' | 'bascule' | 'ensachage'>('parking');

  return (
    <div className="max-w-md mx-auto bg-gray-100 min-h-screen">
      <div className="p-4 bg-blue-700 text-white flex justify-between items-center">
        <h1 className="font-bold">Lafarge Mobile</h1>
        <select 
          value={poste} 
          onChange={e => setPoste(e.target.value as any)}
          className="bg-blue-800 text-white text-sm rounded p-1 border-none"
        >
          <option value="porte_usine">Porte Usine</option>
          <option value="parking">Parking</option>
          <option value="bascule">Bascule</option>
          <option value="ensachage">Ensachage</option>
        </select>
      </div>
      <AgentCapture poste={poste} />
    </div>
  );
}
