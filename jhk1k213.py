from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Pastikan folder ada
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_target_1799():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("--- TARGETED SNIFFING: API 1799 ONLY ---", flush=True)
    
    # Mulai monitor network
    page.listen.start() 
    
    try:
        # Langsung buka halaman yang memicu API tersebut
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka Vision+ Sports Page...", flush=True)
        page.get(url)
        
        found = False
        # Simulasi sedikit scroll untuk trigger loading API
        for s in range(3):
            page.scroll.down(1500)
            time.sleep(2)
            print(f"    > Triggering data (Step {s+1}/3)...", flush=True)

        print("[*] Mencari paket 1799 di lalu lintas data...", flush=True)
        
        # Loop paket yang lewat
        for res in page.listen.steps():
            # FILTER UTAMA: Hanya ambil jika ada '1799' di URL-nya
            if '1799' in res.url:
                try:
                    if res.response.body is not None:
                        body = res.response.body
                        
                        # Simpan hanya file ini
                        filename = "debug_json/paket_21_1799.json"
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        print(f"\n[OK] BERHASIL! File disimpan: {filename}", flush=True)
                        print(f"[OK] Endpoint: {res.url}", flush=True)
                        found = True
                        break # LANGSUNG BERHENTI setelah ketemu
                except Exception:
                    continue
            
            # Timeout proteksi agar tidak stuck (60 detik saja)
            if time.time() - page.listen._start_time > 60:
                print("[!] Timeout: Paket 1799 tidak ditemukan dalam 60 detik.", flush=True)
                break

        if not found:
            print("[-] Gagal mendapatkan paket 1799. Coba jalankan ulang.", flush=True)

    except Exception as e:
        print(f"[-] Error: {e}", flush=True)
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Selesai.", flush=True)

if __name__ == "__main__":
    scrap_vision_target_1799()
