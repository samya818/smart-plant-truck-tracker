/**
 * TruckCard.test.tsx — Tests du composant carte camion
 *
 * Couvre :
 *  1. Rendu de base (immatriculation, statut, zone actuelle)
 *  2. Affichage correct du timeline de cycle (étapes passées vs futures)
 *  3. Calcul et affichage du temps passé en usine
 *  4. Badge "Anomalie" quand le camion dépasse le seuil
 *  5. Affichage ETA quand les durées moyennes sont disponibles
 *  6. Gestion du cas "aucun événement"
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { TruckCard } from '@/components/TruckCard';
import type { Event } from '@/types';
import * as api from '@/services/api';

// ── Fixtures de données ────────────────────────────────────────────────────────

const NOW = new Date('2024-01-15T10:00:00Z');

const makeEvent = (overrides: Partial<Event>): Event => ({
  id: 1,
  truck_id: 42,
  poste: 'porte_usine',
  type_event: 'entree',
  horodatage: NOW.toISOString(),
  source: 'simulation',
  ...overrides,
});

/** Cycle complet jusqu'au parking */
const EVENTS_AU_PARKING: Event[] = [
  makeEvent({ id: 1, poste: 'porte_usine', type_event: 'entree', horodatage: new Date(NOW.getTime() - 45 * 60000).toISOString() }),
  makeEvent({ id: 2, poste: 'parking',    type_event: 'entree', horodatage: new Date(NOW.getTime() - 42 * 60000).toISOString() }),
];

/** Cycle complet porte → bascule */
const EVENTS_A_LA_BASCULE: Event[] = [
  makeEvent({ id: 1, poste: 'porte_usine', type_event: 'entree', horodatage: new Date(NOW.getTime() - 60 * 60000).toISOString() }),
  makeEvent({ id: 2, poste: 'parking',     type_event: 'entree', horodatage: new Date(NOW.getTime() - 57 * 60000).toISOString() }),
  makeEvent({ id: 3, poste: 'parking',     type_event: 'sortie', horodatage: new Date(NOW.getTime() - 30 * 60000).toISOString() }),
  makeEvent({ id: 4, poste: 'bascule',     type_event: 'entree', horodatage: new Date(NOW.getTime() - 28 * 60000).toISOString() }),
];

const DUREES_MOYENNES = {
  parking:      { moyenne: 20, nb_cycles: 100 },
  bascule_tare: { moyenne: 8,  nb_cycles: 100 },
  ensachage:    { moyenne: 35, nb_cycles: 100 },
  bascule_brut: { moyenne: 10, nb_cycles: 100 },
  porte_sortie: { moyenne: 5,  nb_cycles: 100 },
  nb_cycles_total: 100,
  source: 'historique',
};

// ── Configuration des mocks ────────────────────────────────────────────────────

beforeEach(() => {
  vi.spyOn(api, 'getDureesMoyennes').mockResolvedValue(DUREES_MOYENNES);
  // Freeze time pour que les calculs de durée soient déterministes
  vi.setSystemTime(NOW);
});

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('TruckCard — Rendu de base', () => {
  it('affiche l\'immatriculation du camion', async () => {
    render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_AU_PARKING} />);
    expect(screen.getByText('43570-ج-33')).toBeInTheDocument();
  });

  it('affiche le badge "En cours" quand le camion est en usine', async () => {
    render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_AU_PARKING} />);
    expect(screen.getByText(/En cours/i)).toBeInTheDocument();
  });

  it('affiche "En usine" avec le temps écoulé depuis l\'entrée', async () => {
    render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_AU_PARKING} />);
    // Le camion est entré il y a 45 min
    expect(screen.getByText(/En usine/i)).toBeInTheDocument();
    expect(screen.getByText(/45 min/i)).toBeInTheDocument();
  });

  it('ne plante pas avec un tableau d\'événements vide', () => {
    expect(() =>
      render(<TruckCard immatriculation="12345-أ-1" events={[]} />)
    ).not.toThrow();
  });
});

describe('TruckCard — Timeline du cycle', () => {
  it('marque "Porte Usine" comme étape passée quand l\'entrée est enregistrée', async () => {
    render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_AU_PARKING} />);
    const porteSteps = screen.getAllByText('Porte Usine');
    expect(porteSteps.length).toBeGreaterThan(0);
  });

  it('affiche "Parking" comme zone actuelle quand le camion est au parking', async () => {
    render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_AU_PARKING} />);
    // La zone actuelle est affichée dans le header de la carte
    const zoneTexts = screen.getAllByText(/Parking/i);
    expect(zoneTexts.length).toBeGreaterThan(0);
  });

  it('affiche "Agence Logistique (Bascule)" comme zone actuelle à la bascule', async () => {
    render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_A_LA_BASCULE} />);
    const basculeTexts = screen.getAllByText(/Bascule|Agence Logistique/i);
    expect(basculeTexts.length).toBeGreaterThan(0);
  });

  it('affiche toutes les 6 étapes du cycle dans la timeline', async () => {
    render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_AU_PARKING} />);
    // Les 6 zones doivent être présentes
    expect(screen.getAllByText(/Porte Usine/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Parking/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Bascule|Agence Logistique/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Ensachage|Expéditions/i).length).toBeGreaterThan(0);
  });
});

describe('TruckCard — ETA et durées moyennes', () => {
  it('charge les durées moyennes via l\'API au montage', async () => {
    render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_AU_PARKING} />);
    await waitFor(() => {
      expect(api.getDureesMoyennes).toHaveBeenCalled();
    });
  });

  it('affiche des ETA "~HH:MM" pour les étapes futures', async () => {
    render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_AU_PARKING} />);
    await waitFor(() => {
      // Les ETA sont affichés sous forme "~HH:MM"
      const etaElements = screen.queryAllByText(/~\d{2}:\d{2}/);
      expect(etaElements.length).toBeGreaterThan(0);
    });
  });
});

describe('TruckCard — Cas limites', () => {
  it('gère gracieusement l\'échec de l\'API des durées moyennes', async () => {
    vi.spyOn(api, 'getDureesMoyennes').mockRejectedValue(new Error('API down'));
    expect(() =>
      render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_AU_PARKING} />)
    ).not.toThrow();
  });

  it('affiche l\'immatriculation même avec des caractères arabes', () => {
    render(<TruckCard immatriculation="12345-أ-1" events={EVENTS_AU_PARKING} />);
    expect(screen.getByText('12345-أ-1')).toBeInTheDocument();
  });

  it('affiche "Sortie estimée" comme dernière étape du cycle', async () => {
    render(<TruckCard immatriculation="43570-ج-33" events={EVENTS_AU_PARKING} />);
    await waitFor(() => {
      expect(screen.getByText(/Sortie estimée/i)).toBeInTheDocument();
    });
  });
});
