from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Pastikan folder ada
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_all_vision_events():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("--- GLOBAL SNIFFING: ALL SPORTS EVENTS ---", flush=True)
    
    # Listen ke semua URL yang mengandung pola umum API Vision+
    # Biasanya URL-nya mengandung '/cluster/' atau ID paket tertentu
    page.listen.start('v1/program') 
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka Vision+ Sports Page...", flush=True)
        page.get(url)
        
        # Scroll lebih banyak dan lebih lama untuk memancing semua API keluar
        for s in range(6): # Tambah range scroll
            page.scroll.down(2000)
            print(f"    > Scrolled (Step {s+1}/6)...", flush=True)
            time.sleep(4) 

        print("[*] Mengumpulkan semua paket data yang tertangkap...", flush=True)
        
        captured_count = 0
        all_nodes = []

        # Ambil semua paket yang sudah tertangkap di buffer listener
        for res in page.listen.steps(count=10, timeout=10):
            if res.response.body:
                data = res.response.body
                # Pastikan ini adalah data event (memiliki struktur 'nodes')
                if isinstance(data, dict) and 'nodes' in data:
                    all_nodes.extend(data['nodes'])
                    captured_count += 1
                    print(f"    [+] Berhasil mengambil {len(data['nodes'])} node dari: {res.url[:50]}...", flush=True)

        if all_nodes:
            # Gabungkan semua ke dalam satu file utama agar Cloudflare Worker mudah membacanya
            final_data = {"nodes": all_nodes}
            filename = "debug_json/paket_21_1799.json" # Tetap gunakan nama ini agar Worker tidak perlu diubah
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(final_data, f, indent=4)
            
            print(f"\n[OK] TOTAL: {len(all_nodes)} event disimpan ke {filename}", flush=True)
        else:
            print("[-] Tidak ada data event yang tertangkap.", flush=True)

    except Exception as e:
        print(f"[-] Error: {e}", flush=True)
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Selesai.", flush=True)

if __name__ == "__main__":
    scrap_all_vision_events()
