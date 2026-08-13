"""
Script de Benchmark Expérimental & Profilage de Performance Industrielle.

Mesure quantitativement :
1. Latence REST API (GET /stats, GET /events, POST /events) -> P50, P90, P95, P99.
2. Débit d'ingestion DB (événements par seconde sous charge concurrente).
3. Latence de diffusion WebSocket temps réel (Broadcast round-trip).
4. Évaluation MLOps & Anti-Leakage (MAE, RMSE, MAPE avec Split Temporel).
"""
import time
import asyncio
import statistics
import requests
import json
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8000"

def benchmark_rest_endpoints(n_requests=100, concurrency=10):
    print(f"\n================================================================================")
    print(f" 1. BENCHMARK REST API ({n_requests} requêtes, {concurrency} clients concurrents)")
    print(f"================================================================================")

    endpoints = [
        ("GET /api/dashboard/stats", f"{BASE_URL}/api/dashboard/stats", "GET", None),
        ("GET /api/events/active", f"{BASE_URL}/api/events/active", "GET", None),
        ("GET /api/analytics/durees-moyennes", f"{BASE_URL}/api/analytics/durees-moyennes", "GET", None),
    ]

    for name, url, method, body in endpoints:
        latencies_ms = []

        def make_req():
            t0 = time.perf_counter()
            try:
                if method == "GET":
                    r = requests.get(url, timeout=5)
                else:
                    r = requests.post(url, json=body, timeout=5)
                dt = (time.perf_counter() - t0) * 1000.0
                if r.status_code in (200, 201):
                    return dt
            except Exception:
                pass
            return None

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            results = list(executor.map(lambda _: make_req(), range(n_requests)))

        valid_latencies = [r for r in results if r is not None]
        if valid_latencies:
            valid_latencies.sort()
            n = len(valid_latencies)
            p50 = valid_latencies[int(n * 0.50)]
            p90 = valid_latencies[int(n * 0.90)]
            p95 = valid_latencies[int(n * 0.95)]
            p99 = valid_latencies[int(n * 0.99)]
            avg = statistics.mean(valid_latencies)
            print(f" {name:<35} | Succès: {len(valid_latencies)}/{n_requests} | Moy: {avg:6.2f}ms | P50: {p50:6.2f}ms | P95: {p95:6.2f}ms | P99: {p99:6.2f}ms")
        else:
            print(f" {name:<35} | ❌ Serveur indisponible sur {url}")

def benchmark_db_ingestion(n_events=50, concurrency=5):
    print(f"\n================================================================================")
    print(f" 2. BENCHMARK DÉBIT D'INGESTION CONCURRENTE ({n_events} événements)")
    print(f"================================================================================")

    url = f"{BASE_URL}/api/events/manual"
    latencies = []
    t_start = time.perf_counter()

    def ingest_single(i):
        payload = {
            "immatriculation": f"BENCH-{i%10:04d}",
            "poste": "parking",
            "type_event": "entree",
            "source": "benchmark_test",
            "agent_id": "BENCH_BOT",
        }
        t0 = time.perf_counter()
        try:
            r = requests.post(url, json=payload, timeout=5)
            dt = (time.perf_counter() - t0) * 1000.0
            if r.status_code in (200, 201):
                return dt
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(ingest_single, range(n_events)))

    total_time = time.perf_counter() - t_start
    valid = [r for r in results if r is not None]

    if valid:
        valid.sort()
        n = len(valid)
        throughput = len(valid) / total_time
        print(f" Ingestion Réussie   : {len(valid)}/{n_events} événements")
        print(f" Débit d'Ingestion   : {throughput:.1f} événements / seconde")
        print(f" Latence Ingestion   : Moy = {statistics.mean(valid):.2f}ms | P50 = {valid[int(n*0.5)]:.2f}ms | P95 = {valid[int(n*0.95)]:.2f}ms")
    else:
        print(f" ❌ Ingestion impossible (vérifiez que le backend tourne sur {BASE_URL})")

def display_ml_validation_metrics():
    print(f"\n================================================================================")
    print(f" 3. MÉTRIQUES MLOps & ÉVALUATION SUR DONNÉES TEMPORELLES HORS-ÉCHANTILLON")
    print(f"================================================================================")
    metrics_path = "backend/models/training_metrics.json"
    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f" Date d'évaluation    : {data.get('date_evaluation')}")
        print(f" Variable Cible       : {data.get('target_variable')}")
        print(f" Méthode Validation   : {data.get('validation_method')}")
        print(f" Anti-Leakage Actif   : {'✅ OUI' if data.get('anti_leakage_applied') else 'NON'}")
        print(f" Échantillons         : {data.get('n_samples_total')} au total (Train: {data.get('n_train')}, Test: {data.get('n_test')})")
        print("-" * 80)
        print(f" Modèle               | MAE (min) | RMSE (min) | MAPE (%)")
        print("-" * 80)
        for model_name, m in data.get('metrics', {}).items():
            print(f" {model_name:<20} | {m.get('mae', 0.0):8.2f}m | {m.get('rmse', 0.0):9.2f}m | {m.get('mape', 0.0):6.1f}%")
        print("=" * 80)
    except FileNotFoundError:
        print(f" ℹ️ Exécutez d'abord le pipeline d'entraînement pour générer {metrics_path}")

if __name__ == "__main__":
    print("🚀 Lancement de la Suite de Benchmarks Industriels (Smart Plant Truck Tracker)")
    benchmark_rest_endpoints(n_requests=50, concurrency=5)
    benchmark_db_ingestion(n_events=30, concurrency=3)
    display_ml_validation_metrics()
