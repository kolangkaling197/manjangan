from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Persiapan Folder
# Folder ini akan menampung semua file JSON mentah dari network
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')
    print("[*] Folder 'debug_json' telah dibuat.")

def scrap_vision_raw_per_file():
    # Konfigurasi Browser (Wajib Headless untuk GitHub Actions)
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("\n" + "="*50)
    print("--- MODE SIMPAN RAW JSON PER-FILE ---")
    print("="*50 + "\n")
    
    # Mulai pantau Network
    print("[*] Memulai Network Listener...", flush=True)
    page.listen.start() 
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Menuju URL: {url}", flush=True)
        page.get(url)
        
        # Simulasi Interaksi untuk memancing API keluar
        print("[*] Melakukan Auto-Scroll (6 Step) untuk memicu API...", flush=True)
        for s in range(6):
            page.scroll.down(2500)
            print(f"    > Scroll Step {s+1}/6 dijalankan.", flush=True)
            time.sleep(3) # Jeda agar API sempat merespon

        print("\n[*] Menganalisis dan menyimpan paket JSON...", flush=True)
        count = 0
        
        # Tangkap semua paket yang lewat di buffer
        for res in page.listen.steps(count=120, timeout=5):
            try:
                # Syarat: Harus ada body dan formatnya JSON (dict/list)
                if res.response.body is not None:
                    body = res.response.body
                    
                    if isinstance(body, (dict, list)):
                        count += 1
                        
                        # Ambil nama endpoint URL agar file mudah dikenali (misal: menu.json)
                        url_endpoint = res.url.split('/')[-1].split('?')[0] or "root_api"
                        # Bersihkan karakter aneh jika ada
                        filename = f"debug_json/paket_{count}_{url_endpoint}.json"
                        
                        # Simpan masing-masing paket ke file tersendiri
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        print(f"    [SAVED] #{count}: {filename}", flush=True)
                
            except Exception:
                # Skip jika body bukan JSON atau error lainnya
                continue

        print(f"\n[+] SELESAI: Berhasil menyimpan {count} file JSON di folder 'debug_json'.")

    except Exception as e:
        print(f"\n[-] ERROR FATAL: {e}")
    finally:
        print("\n[*] Menutup browser session...", flush=True)
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_raw_per_file()
