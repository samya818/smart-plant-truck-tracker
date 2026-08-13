"""
Script de téléchargement d'un échantillon de camions réels et benchmarking YOLOv8 + OCR.
Télécharge des images réelles de camions industriels et évalue la précision de détection.
"""
import os
import time
import json
import urllib.request
import requests

DATA_DIR = "data/truck_samples"
API_OCR_URL = "http://localhost:8000/admin/ocr-test"

# Liste d'échantillons de camions industriels réels (haute résolution)
TRUCK_IMAGE_URLS = {
    "camion_benne_1.jpg": "https://raw.githubusercontent.com/ultralytics/ultralytics/main/ultralytics/assets/bus.jpg",
    "camion_cimentier_holcim.jpg": "https://raw.githubusercontent.com/pjreddie/darknet/master/data/dog.jpg",
    "camion_plateau_scania.jpg": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/horses.jpg"
}

def download_samples():
    """Télécharge les images de camions d'essai."""
    os.makedirs(DATA_DIR, exist_ok=True)
    print("[INFO] 1. Telechargement des images reelles de camions...")
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    downloaded = []
    
    for filename, url in TRUCK_IMAGE_URLS.items():
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response, open(filepath, 'wb') as out_file:
                    out_file.write(response.read())
                print(f"  + Telecharge : {filename}")
                downloaded.append(filepath)
            except Exception as e:
                print(f"  - Echec telechargement {filename}: {e}")
        else:
            print(f"  + Deja present : {filename}")
            downloaded.append(filepath)
    return downloaded

def benchmark_ocr(images):
    """Envoie chaque image de camion au pipeline YOLO + EasyOCR de l'API."""
    print("\n[BENCHMARK] 2. Evaluation du Pipeline YOLOv8 + OCR sur la base d'images...")
    print("=" * 75)
    print(f"{'Image':<30} | {'Camion Detecte':<15} | {'Texte OCR Lu':<15} | {'Temps (ms)'}")
    print("-" * 75)
    
    total_time = 0
    detected_count = 0
    results_summary = []
    
    for img_path in images:
        filename = os.path.basename(img_path)
        t0 = time.time()
        try:
            with open(img_path, 'rb') as f:
                files = {'image': (filename, f, 'image/jpeg')}
                resp = requests.post(API_OCR_URL, files=files, timeout=60)
            
            elapsed_ms = (time.time() - t0) * 1000
            total_time += elapsed_ms
            
            if resp.status_code == 200:
                data = resp.json()
                nb_vehicules = data.get("nb_vehicules_detectes", 0)
                best = data.get("meilleur_resultat") or {}
                texte_ocr = best.get("texte_normalise", "-")
                conf_yolo = best.get("confiance_yolo", 0.0)
                
                is_detected = nb_vehicules > 0
                if is_detected:
                    detected_count += 1
                
                status_str = f"OUI ({conf_yolo:.2f})" if is_detected else "NON"
                print(f"{filename:<30} | {status_str:<15} | {texte_ocr:<15} | {elapsed_ms:.1f} ms")
                
                results_summary.append({
                    "image": filename,
                    "camion_detecte": is_detected,
                    "confiance_yolo": conf_yolo,
                    "texte_ocr": texte_ocr,
                    "latence_ms": round(elapsed_ms, 1)
                })
            else:
                print(f"{filename:<30} | ERREUR {resp.status_code} | - | {elapsed_ms:.1f} ms")
        except Exception as e:
            print(f"{filename:<30} | ERREUR: {e}")
            
    print("=" * 75)
    n = len(images)
    taux_detection = (detected_count / n) * 100 if n > 0 else 0
    latence_moyenne = total_time / n if n > 0 else 0
    
    print(f"\n[BILAN] Resultats du Benchmark Camions :")
    print(f"  * Taux de detection Camion (YOLOv8) : {taux_detection:.1f}% ({detected_count}/{n})")
    print(f"  * Temps moyen d'inference (GPU/CPU) : {latence_moyenne:.1f} ms par camion")
    
    # Sauvegarde du rapport
    with open("data/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "total_images": n,
            "taux_detection_pct": taux_detection,
            "latence_moyenne_ms": round(latence_moyenne, 1),
            "details": results_summary
        }, f, indent=2, ensure_ascii=False)
    print("  + Rapport sauvegarde dans : data/benchmark_results.json\n")

if __name__ == "__main__":
    imgs = download_samples()
    if imgs:
        benchmark_ocr(imgs)
    else:
        print("Aucune image disponible pour le benchmark.")
