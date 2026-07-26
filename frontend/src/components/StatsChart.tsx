import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getCycles } from '@/services/api';

export function StatsChart() {
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    getCycles().then(cycles => {
      const formatted = cycles.slice(0, 10).map(c => ({
        name: c.immatriculation,
        duree: Math.round(c.duree_total),
      }));
      setData(formatted);
    });
  }, []);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h2 className="text-lg font-semibold mb-4">Durée des derniers cycles (minutes)</h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="duree" fill="#1d4ed8" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
