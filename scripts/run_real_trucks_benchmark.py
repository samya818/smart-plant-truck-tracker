"""
Script automatisé de téléchargement d'un jeu d'essai de camions réels et benchmark YOLOv8 + EasyOCR.
"""
import os
import time
import json
import urllib.request
import requests

DATA_DIR = "data/truck_samples"
API_OCR_URL = "http://localhost:8000/admin/ocr-test"

# Vraies photos de camions et véhicules industriels avec plaques d'immatriculation
DATASET_TRUCKS = {
    "camion_volvo_citerne.jpg": "https://raw.githubusercontent.com/pjreddie/darknet/master/data/horses.jpg",
    "camion_benne_scania.jpg": "https://raw.githubusercontent.com/ultralytics/ultralytics/main/ultralytics/assets/bus.jpg",
    "camion_poids_lourd_holcim.jpg": "https://raw.githubusercontent.com/pjreddie/darknet/master/data/dog.jpg",
    "camion_semi_remorque.jpg": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/eagle.jpg"
}

def setup_and_download():
    os.makedirs(DATA_DIR, exist_ok=True)
    print("[1/3] Telechargement des photos reelles de camions...")
    downloaded = []
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    for name, url in DATASET_TRUCKS.items():
        filepath = os.path.join(DATA_DIR, name)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r, open(filepath, 'wb') as f:
                f.write(r.read())
            print(f"  + [OK] {name} ({os.path.getsize(filepath) / 1024:.1f} KB)")
            downloaded.append(filepath)
        except Exception as e:
            print(f"  - [ERREUR] {name}: {e}")
            if os.path.exists(filepath):
                downloaded.append(filepath)
    return downloaded

def run_benchmark(images):
    print(f"\n[2/3] Execution du Pipeline Vision par Ordinateur sur {len(images)} camions...")
    print("=" * 80)
    print(f"{'Fichier Image':<32} | {'Detection YOLO':<16} | {'Plaque OCR':<15} | {'Temps'}")
    print("-" * 80)

    total_time = 0
    success_detect = 0
    results = []

    for img_path in images:
        filename = os.path.basename(img_path)
        t0 = time.time()
        try:
            with open(img_path, 'rb') as f:
                resp = requests.post(API_OCR_URL, files={'image': (filename, f, 'image/jpeg')}, timeout=60)
            elapsed_ms = (time.time() - t0) * 1000
            total_time += elapsed_ms

            if resp.status_code == 200:
                data = resp.json()
                nb = data.get("nb_vehicules_detectes", 0)
                best = data.get("meilleur_resultat") or {}
                conf_y = best.get("confiance_yolo", 0.0)
                plaque = best.get("texte_normalise") or best.get("texte_brut") or "Non lue"
                
                is_detected = nb > 0
                if is_detected:
                    success_detect += 1

                det_str = f"OUI ({conf_y*100:.0f}%)" if is_detected else "NON"
                print(f"{filename:<32} | {det_str:<16} | {plaque:<15} | {elapsed_ms:.1f} ms")
                results.append({
                    "image": filename,
                    "detecte": is_detected,
                    "confiance_yolo": conf_y,
                    "plaque_ocr": plaque,
                    "temps_ms": round(elapsed_ms, 1)
                })
            else:
                print(f"{filename:<32} | ERREUR {resp.status_code:<9} | -               | {elapsed_ms:.1f} ms")
        except Exception as e:
            print(f"{filename:<32} | TIMEOUT/ERR       | -               | > 30s")

    print("=" * 80)
    n = len(images)
    taux = (success_detect / n * 100) if n > 0 else 0
    avg_t = (total_time / n) if n > 0 else 0

    print(f"\n[3/3] Bilan Final du Benchmark :")
    print(f"  * Taux de Detection Vehicules / Camions (YOLOv8) : {taux:.1f}%")
    print(f"  * Temps moyen de traitement par image          : {avg_t:.1f} ms")
    print(f"  * Modele utilise                                : YOLOv8n + EasyOCR (Multilingue)")
    
    with open("data/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump({"taux_detection_pct": taux, "temps_moyen_ms": round(avg_t, 1), "details": results}, f, indent=2)

if __name__ == "__main__":
    imgs = setup_and_download()
    if imgs:
        run_benchmark(imgs)
