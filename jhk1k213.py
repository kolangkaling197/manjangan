from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time
import glob

# 1. Persiapan Folder
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')
    print("[*] Folder 'debug_json' siap.")

def merge_sari_pati():
    """Menggabungkan semua nodes dari semua JSON yang berhasil ditangkap"""
    print("\n" + "="*40)
    print("[*] MEMULAI PROSES PENGGABUNGAN (ALL JSON)...")
    all_combined_nodes = []
    
    # Ambil semua file json di folder debug_json
    files = glob.glob("debug_json/paket_*.json")
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Cari data 'nodes' atau 'clusters' secara membabi buta
                nodes = []
                if isinstance(data, dict):
                    if 'nodes' in data:
                        nodes = data['nodes']
                    elif 'clusters' in data:
                        for cluster in data.get('clusters', []):
                            if 'nodes' in cluster:
                                nodes.extend(cluster['nodes'])
                
                if nodes:
                    all_combined_nodes.extend(nodes)
                    print(f"    [+] Ekstrak {len(nodes)} event dari {os.path.basename(file_path)}")
        except:
            continue

    if all_combined_nodes:
        # Hapus duplikat berdasarkan ID agar file ringan untuk Cloudflare
        unique_nodes = {n['id']: n for n in all_combined_nodes if 'id' in n}.values()
        
        # Simpan file FINAL untuk Cloudflare Worker
        with open("debug_json/live_events.json", "w", encoding="utf-8") as f:
            json.dump({"nodes": list(unique_nodes)}, f, indent=4)
        
        print(f"\n[OK] TOTAL: {len(unique_nodes)} event unik disimpan ke live_events.json")
    else:
        print("\n[!] PERINGATAN: Tidak ada data pertandingan yang bisa digabung.")
    print("="*40 + "\n")

def scrap_vision_full_sniff():
    # 2. Konfigurasi Browser (Headless untuk GitHub Actions)
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("\n--- START FULL SNIFFING (NO FILTER) ---")
    
    # Mulai pantau Network
    page.listen.start() 
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka URL: {url}")
        page.get(url)
        
        # 3. Auto-Scroll (Pemicu API)
        print("[*] Scrolling untuk memicu semua API JSON...")
        for s in range(6):
            page.scroll.down(2500)
            print(f"    > Scroll Step {s+1}/6")
            time.sleep(3)

        # 4. TANGKAP SEMUA TANPA TERKECUALI
        print("\n[*] Menyimpan semua paket JSON yang tertangkap...")
        count = 0
        for res in page.listen.steps(count=100, timeout=5):
            try:
                # Pastikan ada body dan formatnya JSON (dict)
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, (dict, list)): # Tangkap dict atau list
                        count += 1
                        
                        # Beri nama file berdasarkan urutan dan endpoint URL-nya
                        url_path = res.url.split('/')[-1].split('?')[0] or "api_root"
                        filename = f"debug_json/paket_{count}_{url_path}.json"
                        
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        print(f"    [SAVED] Paket #{count}: {url_path}")
            except:
                continue

        # 5. Gabungkan semua jadi satu file Master
        merge_sari_pati()

    except Exception as e:
        print(f"\n[-] ERROR: {e}")
    finally:
        print("[*] Menutup Session...")
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_full_sniff()
