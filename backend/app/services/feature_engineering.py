"""
Module Centralisé de Feature Engineering — Prédiction Causale des Temps de Séjour.
Garantit l'alignement strict (Zero Mismatch) entre l'entraînement (AutoTrain) et l'inférence (PredictionService).
"""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

# Liste ordonnée et immuable des features du modèle XGBoost
FEATURE_COLUMNS: List[str] = [
    'heure',
    'jour_semaine',
    'hour_sin',
    'hour_cos',
    'dow_sin',
    'dow_cos',
    'is_weekend',
    'is_morning_rush',
    'is_afternoon_rush',
    'lag_1_cycle',
    'lag_5_cycles',
    'rolling_mean_5',
    'rolling_std_5',
]

def build_temporal_features(dt: datetime) -> Dict[str, float]:
    """Extrait les composantes cycliques et calendaires à partir d'un timestamp."""
    hour = dt.hour + dt.minute / 60.0
    dow = dt.weekday()
    return {
        'heure': float(dt.hour),
        'jour_semaine': float(dow),
        'hour_sin': float(np.sin(2 * np.pi * hour / 24.0)),
        'hour_cos': float(np.cos(2 * np.pi * hour / 24.0)),
        'dow_sin': float(np.sin(2 * np.pi * dow / 7.0)),
        'dow_cos': float(np.cos(2 * np.pi * dow / 7.0)),
        'is_weekend': 1.0 if dow >= 5 else 0.0,
        'is_morning_rush': 1.0 if 8 <= dt.hour <= 11 else 0.0,
        'is_afternoon_rush': 1.0 if 14 <= dt.hour <= 17 else 0.0,
    }

def build_features_matrix_train(df: pd.DataFrame, train_median_y: Optional[float] = None) -> tuple[pd.DataFrame, float]:
    """
    Construit la matrice de features pour l'entraînement avec anti-leakage strict.
    - Utilise shift(1) pour les lags et fenêtres glissantes.
    - Calcule train_median_y sur le train set si non fourni (pour éviter le data leakage).
    """
    df = df.sort_values('entree_porte').copy()
    
    # Features calendaires
    df['dt'] = pd.to_datetime(df['entree_porte'])
    hour = df['dt'].dt.hour + df['dt'].dt.minute / 60.0
    dow = df['dt'].dt.weekday

    df['heure'] = df['dt'].dt.hour.astype(float)
    df['jour_semaine'] = dow.astype(float)
    df['hour_sin'] = np.sin(2 * np.pi * hour / 24.0)
    df['hour_cos'] = np.cos(2 * np.pi * hour / 24.0)
    df['dow_sin'] = np.sin(2 * np.pi * dow / 7.0)
    df['dow_cos'] = np.cos(2 * np.pi * dow / 7.0)
    df['is_weekend'] = (dow >= 5).astype(float)
    df['is_morning_rush'] = ((df['dt'].dt.hour >= 8) & (df['dt'].dt.hour <= 11)).astype(float)
    df['is_afternoon_rush'] = ((df['dt'].dt.hour >= 14) & (df['dt'].dt.hour <= 17)).astype(float)

    # Anti-Leakage : features séquentielles calculées UNIQUEMENT avec shift(1)
    if train_median_y is None:
        train_median_y = float(df['y'].median()) if not df.empty else 90.0

    df['lag_1_cycle'] = df['y'].shift(1).fillna(train_median_y)
    df['lag_5_cycles'] = df['y'].shift(5).fillna(train_median_y)
    df['rolling_mean_5'] = df['y'].shift(1).rolling(5, min_periods=1).mean().fillna(train_median_y)
    df['rolling_std_5'] = df['y'].shift(1).rolling(5, min_periods=1).std().fillna(0.0)

    return df, train_median_y

def build_single_inference_vector(
    dt: datetime,
    recent_durations: List[float],
    train_median_y: float = 90.0
) -> pd.DataFrame:
    """
    Construit le vecteur unitaire d'inférence en production (exactement les 13 colonnes attendues par XGBoost).
    """
    feats = build_temporal_features(dt)

    if len(recent_durations) >= 1:
        feats['lag_1_cycle'] = float(recent_durations[-1])
    else:
        feats['lag_1_cycle'] = float(train_median_y)

    if len(recent_durations) >= 5:
        feats['lag_5_cycles'] = float(recent_durations[-5])
        feats['rolling_mean_5'] = float(np.mean(recent_durations[-5:]))
        feats['rolling_std_5'] = float(np.std(recent_durations[-5:]))
    elif len(recent_durations) > 0:
        feats['lag_5_cycles'] = float(recent_durations[0])
        feats['rolling_mean_5'] = float(np.mean(recent_durations))
        feats['rolling_std_5'] = float(np.std(recent_durations))
    else:
        feats['lag_5_cycles'] = float(train_median_y)
        feats['rolling_mean_5'] = float(train_median_y)
        feats['rolling_std_5'] = 0.0

    # Retourne un DataFrame avec l'ordre exact des colonnes
    return pd.DataFrame([[feats[c] for c in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
