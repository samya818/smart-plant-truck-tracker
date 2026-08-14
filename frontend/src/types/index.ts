export interface Truck {
  id: number;
  immatriculation: string;
  type_camion: string;
  transporteur?: Transporteur;
}

export interface Transporteur {
  id: number;
  nom: string;
  est_whitelist: boolean;
}

export interface DelayCause {
  id: number;
  nom: string;
  poste_concerne: string | null;
  usage_count: number;
  is_active: boolean;
}

export interface Event {
  id: number;
  truck_id: number;
  poste: 'porte_usine' | 'parking' | 'bascule' | 'ensachage';
  type_event: 'entree' | 'sortie';
  horodatage: string;
  source: string;
  agent_id?: string;
  cause?: DelayCause;
  minutes_retard?: number;
  confiance_ocr?: number;
  necesita_confirmacion?: boolean;
  image_path?: string;
  truck?: Truck;
}

export interface Cycle {
  id: number;
  immatriculation: string;
  entree_porte: string;
  sortie_porte?: string;
  duree_total: number;
  status: string;
  est_anomalie: boolean;
}

export interface DashboardStats {
  camions_en_cours: number;
  camions_aujourdhui: number;
  temps_moyen_cycle: number;
  poste_plus_contraignant?: string;
  poste_bloquant?: string;
  alertes_actives: number;
  top_cause_retard?: string;
}

export interface PosteConfig {
  poste: string;
  capture_mode: 'camera' | 'agent' | 'hybrid';
  camera_url?: string;
  camera_active: boolean;
  agent_pin?: string;
  seuil_attente_max: number;
  is_active: boolean;
}

export interface DureesMoyennes {
  parking:      { moyenne: number; nb_cycles: number };
  bascule_tare: { moyenne: number; nb_cycles: number };
  ensachage:    { moyenne: number; nb_cycles: number };
  bascule_brut: { moyenne: number; nb_cycles: number };
  porte_sortie: { moyenne: number; nb_cycles: number };
  nb_cycles_total: number;
  source: string;
}
