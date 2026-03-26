from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time
import glob

# Persiapan Folder
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_deep_sniff():
    co = ChromiumOptions()
    co.headless() # Wajib untuk GitHub Actions
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("--- DEEP SNIFFING & AUTO-MERGE FOR CLOUDFLARE ---")
    
    page.listen.start() 
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(url)
        print(f"[*] Membuka: {url}")
        
        # Simulasi Scroll (Pemicu API)
        for s in range(6):
            page.scroll.down(2500)
            time.sleep(3)
            print(f"    > Scroll Step {s+1}/6")

        print("[*] Mengumpulkan paket network...")
        raw_packets_count = 0
        all_nodes = []

        # Ambil semua paket yang tertangkap
        for res in page.listen.steps(count=100, timeout=5):
            try:
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, dict):
                        raw_packets_count += 1
                        
                        # LOGIKA PENYARINGAN: Cari 'nodes' di setiap file yang lewat
                        nodes = []
                        if 'nodes' in body:
                            nodes = body['nodes']
                        elif 'clusters' in body:
                            for c in body.get('clusters', []):
                                if 'nodes' in c: nodes.extend(c['nodes'])
                        
                        if nodes:
                            all_nodes.extend(nodes)
                            # Simpan juga file mentahnya untuk backup/debug
                            filename = f"debug_json/paket_{raw_packets_count}.json"
                            with open(filename, "w", encoding="utf-8") as f:
                                json.dump(body, f, indent=4)
            except:
                continue

        # --- FINALISASI UNTUK CLOUDFLARE ---
        if all_nodes:
            # Hapus duplikat berdasarkan ID agar data bersih
            unique_nodes = {n['id']: n for n in all_nodes if 'id' in n}.values()
            
            # File ini yang akan dibaca oleh Cloudflare Worker
            output_file = "debug_json/live_events.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({"nodes": list(unique_nodes)}, f, indent=4)
            
            print(f"\n[OK] BERHASIL: {len(unique_nodes)} event unik digabung ke {output_file}")
        else:
            print("\n[!] Gagal menemukan data event. Cek log atau screenshot.")

    except Exception as e:
        print(f"[-] Terjadi kesalahan: {e}")
    finally:
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_deep_sniff()
