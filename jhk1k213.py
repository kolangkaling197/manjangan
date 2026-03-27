from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time
import glob

# 1. Persiapan Folder (Wajib ada untuk GitHub Actions)
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')
    print("[*] Folder 'debug_json' siap.")

def merge_all_json_to_master():
    """Fungsi untuk menyatukan semua paket JSON menjadi satu file sakti"""
    print("\n" + "="*30)
    print("[*] MEMULAI PROSES MERGER (SAPU JAGAT)...")
    all_combined_nodes = []
    
    # Ambil semua file paket_*.json di folder debug_json
    files = glob.glob("debug_json/paket_*.json")
    print(f"[*] Menemukan {len(files)} file mentah untuk dibedah.")
    
    for file_path in files:
        if "live_events.json" in file_path: continue # Lewati file hasil merger itu sendiri
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                nodes = []
                # Cari data 'nodes' di root atau di dalam 'clusters'
                if isinstance(data, dict):
                    if 'nodes' in data:
                        nodes = data['nodes']
                    elif 'clusters' in data:
                        for cluster in data.get('clusters', []):
                            if 'nodes' in cluster:
                                nodes.extend(cluster['nodes'])
                
                if nodes:
                    all_combined_nodes.extend(nodes)
                    print(f"    [+] Berhasil ekstrak {len(nodes)} event dari {os.path.basename(file_path)}")
        except Exception:
            continue

    if all_combined_nodes:
        # Hapus duplikat berdasarkan ID agar file ringan (penting untuk Cloudflare)
        unique_nodes = {n['id']: n for n in all_combined_nodes if 'id' in n}.values()
        
        # SIMPAN HASIL AKHIR UNTUK CLOUDFLARE WORKER
        final_output = "debug_json/live_events.json"
        with open(final_output, "w", encoding="utf-8") as f:
            json.dump({"nodes": list(unique_nodes)}, f, indent=4)
        
        print(f"\n[OK] TOTAL: {len(unique_nodes)} event unik disimpan ke {final_output}")
        print("="*30 + "\n")
    else:
        print("\n[!] PERINGATAN: Tidak ada data event yang ditemukan untuk digabung.")

def scrap_vision_deep_sniff():
    # 2. Konfigurasi Browser Headless (Wajib di GitHub)
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("\n--- DEEP SNIFFING VISION+ START ---")
    
    # Mulai pantau Network
    page.listen.start() 
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Menuju URL: {url}")
        page.get(url)
        
        # 3. Simulasi Interaksi untuk Memancing API
        print("[*] Melakukan Auto-Scroll (6 Step)...")
        for s in range(6):
            page.scroll.down(2500)
            print(f"    > Step {s+1}/6")
            time.sleep(3) # Jeda agar paket sempat terkirim/diterima

        # 4. Tangkap dan Simpan Semua Paket JSON
        print("\n[*] Menyimpan semua paket mentah...")
        count = 0
        for res in page.listen.steps(count=100, timeout=5):
            try:
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, dict):
                        count += 1
                        # Ambil nama unik dari URL (misal: menu, list, page)
                        url_path = res.url.split('/')[-1].split('?')[0] or "api"
                        filename = f"debug_json/paket_{count}_{url_path}.json"
                        
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        # Deteksi instan jika ada target menarik
                        body_str = str(body).lower()
                        if any(x in body_str for x in ['nodes', 'sport', 'originaltitle']):
                            print(f"    [!!!] TARGET DITEMUKAN: Paket #{count} ({url_path})")
            except:
                continue

        # 5. Jalankan Proses Merger (Penyatuan untuk Cloudflare)
        merge_all_json_to_master()

    except Exception as e:
        print(f"\n[-] ERROR FATAL: {e}")
    finally:
        print("[*] Menutup Session...")
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_deep_sniff()
