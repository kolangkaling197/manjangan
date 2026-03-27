from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_deep_dive():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    
    page = ChromiumPage(co)
    print("\n[*] MEMULAI SNIFFING AGRESIF (TARGET 9 STRIPS)...")
    
    page.listen.start()
    
    try:
        url_main = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(url_main)
        
        # --- BAGIAN KRITIKAL: MEMANCING 9 STRIP ---
        for i in range(10):  # Scroll lebih banyak
            page.scroll.down(1500)
            print(f"    [>] Scrolling ke-{i+1}...")
            time.sleep(2) # Kasih waktu API buat 'nembak'
        
        print("\n[*] Menganalisis paket yang masuk...")
        count = 0
        
        # Ambil paket lebih banyak (count=150)
        for res in page.listen.steps(count=150, timeout=15):
            try:
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, (dict, list)):
                        count += 1
                        
                        # Penamaan File Pintar
                        if 'elements/strips/' in res.url:
                            # Ini adalah 9 event yang kamu cari!
                            strip_id = res.url.split('/')[-1].split('?')[0]
                            filename = f"debug_json/DETAIL_STRIP_{strip_id}.json"
                        elif 'elements/page/4030' in res.url:
                            filename = f"debug_json/paket_{count}_UTAMA_4030.json"
                        else:
                            url_end = res.url.split('/')[-1].split('?')[0] or "api"
                            filename = f"debug_json/paket_{count}_{url_end}.json"
                        
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        print(f"    [SAVED] {filename}")
            except:
                continue

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_deep_dive()
