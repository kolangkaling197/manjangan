from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time
import random

if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_stealth():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    # Gunakan UA yang persis seperti sniff kamu agar tidak dicurigai
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("\n[*] MEMULAI SNIFFING MODE STEALTH (TARGET 9 STRIPS)...")
    
    page.listen.start()
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(url)
        
        # Jeda awal agar halaman dasar tenang dulu
        time.sleep(5)

        # --- TEKNIK HUMAN SCROLLING ---
        current_y = 0
        # Kita buat step lebih banyak (40 step) tapi jarak pendek-pendek
        for i in range(40):
            # Jarak scroll acak antara 400-700px (biar tidak kaku)
            scroll_dist = random.randint(400, 700)
            current_y += scroll_dist
            
            page.run_js(f'window.scrollTo({{top: {current_y}, behavior: "smooth"}});')
            print(f"    [>] Step {i+1}/40: Scroll ke {current_y}px...")
            
            # Jeda acak antara 3 sampai 5 detik
            time.sleep(random.uniform(3.5, 5.5)) 
            
            # Setiap 3 step, berhenti total lebih lama (simulasi membaca)
            if (i+1) % 3 == 0:
                print("    [!] Berhenti sejenak untuk memancing API...")
                time.sleep(3)
                # Sedikit scroll ke atas lalu ke bawah lagi
                page.run_js('window.scrollBy(0, -100);')
                time.sleep(1)
                page.run_js('window.scrollBy(0, 100);')

        print("\n[*] Selesai Scroll. Memeriksa buffer network...")
        count = 0
        
        # Beri waktu tambahan 10 detik terakhir untuk semua request masuk
        time.sleep(10)

        for res in page.listen.steps(count=250, timeout=20):
            try:
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, (dict, list)):
                        count += 1
                        
                        if '/elements/strips/' in res.url:
                            strip_id = res.url.split('/')[-1].split('?')[0]
                            filename = f"debug_json/DETAIL_STRIP_{strip_id}.json"
                        elif '/elements/page/4030' in res.url:
                            filename = f"debug_json/UTAMA_PAGE_4030.json"
                        else:
                            # Bersihkan endpoint name
                            clean_end = "".join(x for x in res.url.split('/')[-1].split('?')[0] if x.isalnum()) or "api"
                            filename = f"debug_json/paket_{count}_{clean_end}.json"
                        
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        if "DETAIL_STRIP" in filename:
                            print(f"    [FOUND EVENT] {filename}")
            except:
                continue

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        print(f"\n[*] Total {count} paket diproses. Selesai.")
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_stealth()
