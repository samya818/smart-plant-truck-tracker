/**
 * api.test.ts — Tests du service API REST
 *
 * Utilise MSW (Mock Service Worker) pour intercepter les appels fetch
 * sans dépendance au serveur backend.
 *
 * Couvre :
 *  1. getDashboardStats — retourne les stats correctement parsées
 *  2. getActiveEvents   — retourne la liste des événements actifs
 *  3. getDureesMoyennes — retourne les durées moyennes de cycle
 *  4. Gestion des erreurs HTTP 500
 *  5. Gestion des erreurs HTTP 404
 *  6. createDelayCause  — POST avec body JSON
 *  7. updatePosteConfig — PUT avec body JSON
 */
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import {
  getDashboardStats,
  getActiveEvents,
  getDureesMoyennes,
  createDelayCause,
  updatePosteConfig,
} from '@/services/api';

// ── Fixtures ───────────────────────────────────────────────────────────────────

const STATS_FIXTURE = {
  camions_en_cours: 13,
  camions_aujourdhui: 47,
  temps_moyen_cycle: 92,
  poste_bloquant: 'ensachage',
  alertes_actives: 2,
  top_cause_retard: 'Attente chargement',
};

const EVENTS_FIXTURE = [
  {
    id: 101,
    truck_id: 1,
    poste: 'bascule',
    type_event: 'entree',
    horodatage: '2024-01-15T09:30:00Z',
    source: 'camera',
    confiance_ocr: 0.87,
  },
  {
    id: 102,
    truck_id: 2,
    poste: 'ensachage',
    type_event: 'entree',
    horodatage: '2024-01-15T09:45:00Z',
    source: 'agent',
  },
];

const DUREES_FIXTURE = {
  parking:      { moyenne: 22.5, nb_cycles: 120 },
  bascule_tare: { moyenne: 9.1,  nb_cycles: 120 },
  ensachage:    { moyenne: 38.7, nb_cycles: 120 },
  bascule_brut: { moyenne: 11.2, nb_cycles: 120 },
  porte_sortie: { moyenne: 6.0,  nb_cycles: 120 },
  nb_cycles_total: 120,
  source: 'historique',
};

// ── Serveur MSW ────────────────────────────────────────────────────────────────

const server = setupServer(
  http.get('/api/dashboard/stats', () => HttpResponse.json(STATS_FIXTURE)),
  http.get('/api/events/active',   () => HttpResponse.json(EVENTS_FIXTURE)),
  http.get('/api/analytics/durees-moyennes', () => HttpResponse.json(DUREES_FIXTURE)),
  http.post('/api/mobile/delay-causes', async ({ request }) => {
    const body = (await request.json()) as Record<string, any>;
    return HttpResponse.json({ id: 999, ...body }, { status: 201 });
  }),
  http.put('/api/mobile/poste-configs/:poste', async ({ params, request }) => {
    const body = (await request.json()) as Record<string, any>;
    return HttpResponse.json({ poste: params.poste, ...body });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('api.ts — getDashboardStats', () => {
  it('retourne les statistiques du dashboard correctement parsées', async () => {
    const stats = await getDashboardStats();
    expect(stats.camions_en_cours).toBe(13);
    expect(stats.camions_aujourdhui).toBe(47);
    expect(stats.temps_moyen_cycle).toBe(92);
    expect(stats.poste_bloquant).toBe('ensachage');
    expect(stats.alertes_actives).toBe(2);
  });

  it('lance une erreur si le serveur répond 500', async () => {
    server.use(
      http.get('/api/dashboard/stats', () =>
        new HttpResponse(null, { status: 500 })
      )
    );
    await expect(getDashboardStats()).rejects.toThrow('API Error: 500');
  });
});

describe('api.ts — getActiveEvents', () => {
  it('retourne la liste des événements actifs', async () => {
    const events = await getActiveEvents();
    expect(events).toHaveLength(2);
    expect(events[0].id).toBe(101);
    expect(events[0].poste).toBe('bascule');
    expect(events[0].confiance_ocr).toBe(0.87);
  });

  it('retourne un tableau vide si aucun camion en cours', async () => {
    server.use(
      http.get('/api/events/active', () => HttpResponse.json([]))
    );
    const events = await getActiveEvents();
    expect(events).toHaveLength(0);
  });

  it('lance une erreur si le serveur répond 404', async () => {
    server.use(
      http.get('/api/events/active', () =>
        new HttpResponse(null, { status: 404 })
      )
    );
    await expect(getActiveEvents()).rejects.toThrow('API Error: 404');
  });
});

describe('api.ts — getDureesMoyennes', () => {
  it('retourne les durées moyennes avec le bon nombre de cycles', async () => {
    const durees = await getDureesMoyennes();
    expect(durees.parking.moyenne).toBe(22.5);
    expect(durees.ensachage.nb_cycles).toBe(120);
    expect(durees.nb_cycles_total).toBe(120);
    expect(durees.source).toBe('historique');
  });
});

describe('api.ts — createDelayCause (POST)', () => {
  it('envoie un POST avec le body JSON et retourne l\'objet créé', async () => {
    const newCause = {
      nom: 'Panne mécanique',
      poste_concerne: 'bascule',
      is_active: true,
    };
    const result = await createDelayCause(newCause);
    expect(result.id).toBe(999);
    expect(result.nom).toBe('Panne mécanique');
    expect(result.poste_concerne).toBe('bascule');
  });
});

describe('api.ts — updatePosteConfig (PUT)', () => {
  it('envoie un PUT avec le body et retourne la config mise à jour', async () => {
    const result = await updatePosteConfig('bascule', {
      capture_mode: 'hybrid',
      seuil_attente_max: 20,
    });
    expect(result.poste).toBe('bascule');
    expect((result as any).capture_mode).toBe('hybrid');
    expect((result as any).seuil_attente_max).toBe(20);
  });
});
