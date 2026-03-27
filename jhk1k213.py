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
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-blink-features=AutomationControlled')  # anti-detect tambahan
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    print("--- TARGETED SNIFFING: API 1799 ONLY ---", flush=True)
   
    # Mulai listen SEBELUM buka halaman
    page.listen.start('1799')
   
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka Vision+ Sports Page...", flush=True)
        page.get(url)
        
        # Tunggu halaman benar-benar loaded dulu
        print("[*] Menunggu halaman load complete...", flush=True)
        page.wait.load_complete(timeout=15)
        
        # Trigger scroll (lebih agresif)
        for s in range(4):
            page.scroll.down(1200)
            print(f" > Triggering data (Step {s+1}/4)...", flush=True)
            time.sleep(2.5)
        
        print("[*] Menunggu paket 1799 muncul...", flush=True)
        
        # Loop wait biar lebih aman (bisa nangkap kalau ada delay)
        res = None
        for attempt in range(8):  # max 8x percobaan
            res = page.listen.wait(timeout=12)
            if res:
                print(f"[+] Paket ditemukan pada attempt {attempt+1}: {res.url}", flush=True)
                break
            print(f"[-] Attempt {attempt+1}/8: belum ketemu...", flush=True)
        
        if res and res.response.body:
            body = res.response.body
            # Safety: kalau body masih bytes/str, parse dulu
            if isinstance(body, (bytes, bytearray)):
                body = json.loads(body.decode('utf-8'))
            elif isinstance(body, str):
                body = json.loads(body)
            
            filename = "debug_json/paket_21_1799.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(body, f, indent=4, ensure_ascii=False)
            
            print(f"[OK] BERHASIL! Data disimpan ke {filename} ({len(str(body))} chars)", flush=True)
        else:
            print("[-] Gagal: Paket 1799 tidak ditemukan dalam waktu tunggu.", flush=True)
            
    except Exception as e:
        print(f"[-] Error fatal: {e}", flush=True)
    finally:
        try:
            page.listen.stop()
        except:
            pass
        page.quit()
        print("[*] Browser ditutup. Selesai.", flush=True)

if __name__ == "__main__":
    scrap_vision_target_1799()
