import type { Truck, Event, DashboardStats, Cycle, DelayCause, PosteConfig } from '@/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export const getTrucks = () => apiFetch<Truck[]>('/api/trucks/');
export const getActiveEvents = () => apiFetch<Event[]>('/api/events/active');
export const getDashboardStats = () => apiFetch<DashboardStats>('/api/dashboard/stats');
export const getCycles = () => apiFetch<Cycle[]>('/api/analytics/cycles');
export const getDelayCauses = (poste?: string) => apiFetch<DelayCause[]>(`/api/mobile/delay-causes?poste=${poste || ''}&active_only=true`);
export const createDelayCause = (data: Partial<DelayCause>) => apiFetch<DelayCause>('/api/mobile/delay-causes', {
  method: 'POST', body: JSON.stringify(data)
});
export const getPosteConfigs = () => apiFetch<PosteConfig[]>('/api/mobile/poste-configs');
export const updatePosteConfig = (poste: string, data: Partial<PosteConfig>) => apiFetch<PosteConfig>(`/api/mobile/poste-configs/${poste}`, {
  method: 'PUT', body: JSON.stringify(data)
});

