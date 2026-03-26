from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Pastikan folder ada
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_auto_sniff():
    # 1. Konfigurasi Browser untuk Server (Headless)
    co = ChromiumOptions()
    co.headless() 
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("--- AUTOMATED DEEP SNIFFING VISION+ ---", flush=True)
    
    # 2. Mulai Listen Network
    page.listen.start() 
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka: {url}", flush=True)
        page.get(url)
        
        all_nodes = []
        found_count = 0

        # 3. Simulasi Scroll Otomatis (Menggantikan tangan kamu)
        for i in range(10): # Scroll 10 kali
            page.scroll.down(2000)
            print(f"[*] Scroll step {i+1}/10...", flush=True)
            time.sleep(3) # Tunggu loading API tiap scroll

            # 4. Ambil semua paket yang tertangkap saat scroll
            for res in page.listen.steps(count=5, timeout=1):
                try:
                    body = res.response.body
                    if isinstance(body, dict):
                        # Cek apakah ini data program/event
                        # Kita cari property 'nodes' atau 'clusters'
                        nodes = []
                        if 'nodes' in body:
                            nodes = body['nodes']
                        elif 'clusters' in body:
                            # Jika struktur clusters, ambil nodes di dalamnya
                            for cluster in body.get('clusters', []):
                                if 'nodes' in cluster:
                                    nodes.extend(cluster['nodes'])

                        if nodes:
                            all_nodes.extend(nodes)
                            found_count += 1
                            print(f"    [+] Menemukan {len(nodes)} event baru!", flush=True)
                except:
                    continue

        # 5. Gabungkan dan Simpan Hasil Akhir
        if all_nodes:
            # Hapus Duplikat berdasarkan id jika perlu
            unique_nodes = {node['id']: node for node in all_nodes if 'id' in node}.values()
            
            final_filename = "debug_json/paket_21_1799.json"
            with open(final_filename, "w", encoding="utf-8") as f:
                json.dump({"nodes": list(unique_nodes)}, f, indent=4)
            
            print(f"\n[OK] BERHASIL! Total {len(unique_nodes)} event unik disimpan.", flush=True)
        else:
            print("\n[-] Gagal mendapatkan data event apapun.", flush=True)

    except Exception as e:
        print(f"[-] Terjadi kesalahan: {e}", flush=True)
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Proses Selesai.", flush=True)

if __name__ == "__main__":
    scrap_vision_auto_sniff()
