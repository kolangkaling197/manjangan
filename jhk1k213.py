from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_9_strips():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    
    page = ChromiumPage(co)
    print("\n[*] MEMULAI SNIFFING STRIP EVENT (TARGET: 9 STRIPS)...")
    
    # Mulai dengerin network
    page.listen.start()
    
    try:
        url_main = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka: {url_main}")
        page.get(url_main)
        
        # --- TEKNIK SCROLLING BERTAHAP ---
        # Kita scroll 15 kali, setiap scroll tunggu 3 detik agar API Strips nembak
        for i in range(15):
            # Scroll pelan-pelan (500-1000 pixel) agar tidak ada strip yang terlewat
            distance = (i + 1) * 1000
            page.run_js(f'window.scrollTo(0, {distance});')
            print(f"    [>] Scrolling ke posisi {distance}px... (Step {i+1}/15)")
            time.sleep(3) 

        print("\n[*] Menganalisis hasil tangkapan...")
        count = 0
        
        # Ambil paket hingga 200 paket agar tidak ada yang ketinggalan
        for res in page.listen.steps(count=200, timeout=15):
            try:
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, (dict, list)):
                        count += 1
                        
                        # LOGIKA PENAMAAN FILE
                        if '/elements/strips/' in res.url:
                            # INI TARGET UTAMA KITA
                            strip_id = res.url.split('/')[-1].split('?')[0]
                            filename = f"debug_json/DETAIL_STRIP_{strip_id}.json"
                        elif '/elements/page/4030' in res.url:
                            filename = f"debug_json/paket_{count}_PAGE_UTAMA_4030.json"
                        else:
                            # API pendukung lainnya
                            url_end = res.url.split('/')[-1].split('?')[0] or "api"
                            filename = f"debug_json/paket_{count}_{url_end}.json"
                        
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        print(f"    [SAVED] {filename}")
            except:
                continue

    except Exception as e:
        print(f"[-] Terjadi kesalahan: {e}")
    finally:
        print("\n[*] Selesai. Menutup browser.")
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_9_strips()
