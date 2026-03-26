from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time
import glob

# Buat folder untuk hasil scan jika belum ada
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_deep_sniff():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("--- DEEP SNIFFING & AUTO MERGE FOR CLOUDFLARE ---")
    
    page.listen.start() 
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(url)
        print(f"[*] Membuka: {url}")
        
        print("[*] Auto-Scroll memicu API...")
        for s in range(6):
            page.scroll.down(2500)
            time.sleep(3)
            print(f"    > Step {s+1}/6")

        print("[*] Menyimpan semua paket mentah...")
        count = 0
        for res in page.listen.steps(count=100, timeout=5):
            try:
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, dict):
                        count += 1
                        url_path = res.url.split('/')[-1].split('?')[0] or "api"
                        filename = f"debug_json/paket_{count}_{url_path}.json"
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
            except:
                continue

        # --- LOGIKA PENYARINGAN UNTUK CLOUDFLARE ---
        print("\n[*] Menyaring data untuk Cloudflare Worker...")
        all_events = []
        files = glob.glob("debug_json/paket_*.json")

        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    nodes = []
                    # Ambil data dari struktur 'nodes' atau 'clusters'
                    if 'nodes' in data:
                        nodes = data['nodes']
                    elif 'clusters' in data:
                        for c in data['clusters']:
                            nodes.extend(c.get('nodes', []))
                    
                    if nodes:
                        all_events.extend(nodes)
            except:
                continue

        if all_events:
            # Hapus duplikat berdasarkan ID pertandingan
            unique_events = {e['id']: e for e in all_events if 'id' in e}.values()
            
            # Simpan file FINAL yang akan dibaca Cloudflare
            with open("debug_json/live_events.json", "w", encoding="utf-8") as f:
                json.dump({"nodes": list(unique_events)}, f, indent=4)
            
            print(f"[+] SUKSES: {len(unique_events)} event digabung ke live_events.json")
        else:
            print("[-] Gagal menyaring event.")

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_deep_sniff()
