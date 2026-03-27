from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Pastikan folder ada
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')
    print("[*] Folder debug_json siap.")

def scrap_vision_target_1799():
    co = ChromiumOptions()
    co.headless() # Wajib untuk GitHub Actions
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage') # Penting untuk lingkungan Docker/Actions
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("--- TARGETED SNIFFING: API 1799 ONLY ---", flush=True)
    
    # Mulai listen sebelum membuka URL
    page.listen.start('1799') # Langsung filter target '1799' agar efisien
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka Vision+ Sports Page...", flush=True)
        page.get(url)
        
        # Trigger scroll agar API dipanggil
        for s in range(3):
            page.scroll.down(1500)
            print(f"    > Triggering data (Step {s+1}/3)...", flush=True)
            time.sleep(3) # Beri jeda lebih lama agar loading selesai

        print("[*] Menunggu paket 1799 muncul...", flush=True)
        
        # GANTI STEPS DENGAN WAIT (Lebih stabil)
        res = page.listen.wait(timeout=60) 
        
        if res:
            print(f"[+] Paket ditemukan: {res.url}", flush=True)
            body = res.response.body
            
            if body:
                filename = "debug_json/paket_21_1799.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(body, f, indent=4)
                print(f"[OK] BERHASIL! Data disimpan ke {filename}", flush=True)
            else:
                print("[-] Respon kosong (body is None)", flush=True)
        else:
            print("[-] Gagal: Paket 1799 tidak lewat dalam 60 detik.", flush=True)

    except Exception as e:
        print(f"[-] Error fatal: {e}", flush=True)
    finally:
        # Stop listener dengan aman
        try:
            page.listen.stop()
        except:
            pass
        page.quit()
        print("[*] Selesai.", flush=True)

if __name__ == "__main__":
    scrap_vision_target_1799()
