from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Pastikan folder ada
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_final():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    # Gunakan User-Agent yang sama dengan hasil sniff kamu
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("\n[*] MEMULAI SNIFFING DEEP-DIVE (TARGET: 9 STRIPS)...")
    
    # Listen Network
    page.listen.start()
    
    try:
        url_main = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka Vision+: {url_main}")
        page.get(url_main)
        
        # --- TEKNIK SLOW SCROLL AGAR SEMUA STRIP KELUAR ---
        current_pos = 0
        for i in range(25):  # 25 kali hentakan scroll
            current_pos += 800
            page.run_js(f'window.scrollTo(0, {current_pos});')
            print(f"    [>] Step {i+1}/25: Scroll ke {current_pos}px...")
            
            # Beri jeda 4 detik setiap scroll agar API sempat 'nembak'
            time.sleep(4) 
            
            # Teknik "Shake": Scroll balik sedikit tiap 5 step untuk memicu trigger Lazy Load
            if (i+1) % 5 == 0:
                page.run_js('window.scrollBy(0, -400);')
                time.sleep(1)

        print("\n[*] Menganalisis paket JSON yang tertangkap...")
        count = 0
        
        # Ambil paket hingga 200 paket
        for res in page.listen.steps(count=200, timeout=15):
            try:
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, (dict, list)):
                        count += 1
                        
                        # LOGIKA PENAMAAN FILE
                        # Jika URL mengandung strips/angka (Ini targetmu!)
                        if '/elements/strips/' in res.url:
                            strip_id = res.url.split('/')[-1].split('?')[0]
                            filename = f"debug_json/DETAIL_STRIP_{strip_id}.json"
                        elif '/elements/page/4030' in res.url:
                            filename = f"debug_json/UTAMA_PAGE_4030.json"
                        else:
                            # File pendukung lainnya
                            url_end = res.url.split('/')[-1].split('?')[0] or "api"
                            # Bersihkan nama file dari karakter ilegal
                            url_end = "".join(x for x in url_end if x.isalnum())
                            filename = f"debug_json/paket_{count}_{url_end}.json"
                        
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        print(f"    [SAVED] {filename}")
            except:
                continue

    except Exception as e:
        print(f"[-] Terjadi Error: {e}")
    finally:
        print("\n[*] Sniffing Selesai. Menutup Session.")
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_final()
