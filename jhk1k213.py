from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Folder hasil scan
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_nested():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    
    page = ChromiumPage(co)
    print("\n[*] MEMULAI SNIFFING STRIP 4030...")
    
    page.listen.start()
    
    try:
        # 1. Buka halaman utama 4030
        url_main = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(url_main)
        
        # Jeda untuk memastikan semua paket strips terpanggil
        print("[*] Menunggu API Strips muncul...")
        time.sleep(5)
        page.scroll.down(3000)
        time.sleep(5)

        print("\n[*] Menyimpan semua paket JSON yang masuk...")
        count = 0
        
        # 2. Tangkap semua file (Termasuk 9 strip detail tersebut)
        for res in page.listen.steps(count=100, timeout=10):
            try:
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, (dict, list)):
                        count += 1
                        
                        # Identifikasi nama file
                        # Jika paket berasal dari /elements/strips/xxxxx
                        if '/elements/strips/' in res.url:
                            strip_id = res.url.split('/')[-1].split('?')[0]
                            filename = f"debug_json/DETAIL_STRIP_{strip_id}.json"
                        elif '/elements/page/4030' in res.url:
                            filename = f"debug_json/MAIN_PAGE_4030.json"
                        else:
                            url_path = res.url.split('/')[-1].split('?')[0] or "api"
                            filename = f"debug_json/paket_{count}_{url_path}.json"
                        
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        print(f"    [SAVED] {filename}")
            except:
                continue

        print(f"\n[+] BERHASIL: Cek folder 'debug_json'.")
        print("[*] File dengan awalan 'DETAIL_STRIP_' adalah isi dari 9 event tersebut.")

    except Exception as e:
        print(f"[-] ERROR: {e}")
    finally:
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_nested()
