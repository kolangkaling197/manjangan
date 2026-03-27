from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_direct():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    
    page = ChromiumPage(co)
    print("\n[*] MEMULAI MODE AUTO-COLLECTOR (DIRECT STRIP ACCESS)...")
    
    try:
        # STEP 1: Ambil daftar ID dari halaman utama
        url_main = 'https://www.visionplus.id/elements/page/4030?language=ENG&mode=guest&partition=IndonesiaPartition&region=Indonesia&target=WEB'
        print(f"[*] Mengambil peta utama dari API...")
        page.get(url_main)
        
        # Ambil JSON mentah dari body halaman
        main_data = json.loads(page.html.split('pre style="word-wrap: break-word; white-space: pre-wrap;">')[1].split('</pre>')[0])
        
        # Simpan file utama
        with open("debug_json/UTAMA_PAGE_4030.json", "w") as f:
            json.dump(main_data, f, indent=4)

        # STEP 2: Cari semua ID Strip (target 9 event)
        strip_urls = []
        for comp in main_data.get('components', []):
            for content in comp.get('contents', []):
                load_url = content.get('load', {}).get('url')
                if load_url and '/elements/strips/' in load_url:
                    # Buat URL lengkap dengan parameter agar valid
                    full_strip_url = f"https://www.visionplus.id{load_url}?language=ENG&mode=guest&partition=IndonesiaPartition&region=Indonesia&target=WEB"
                    strip_urls.append(full_strip_url)
        
        print(f"[*] Ditemukan {len(strip_urls)} target strip. Mulai mendownload satu per satu...")

        # STEP 3: Hajar satu-satu secara direct
        for index, s_url in enumerate(strip_urls):
            strip_id = s_url.split('/')[-1].split('?')[0]
            print(f"    [>] Mengambil Strip {index+1}/{len(strip_urls)} (ID: {strip_id})...")
            
            page.get(s_url)
            time.sleep(2) # Jeda singkat biar gak dianggap DDOS
            
            try:
                # Ambil JSON dari tampilan browser
                strip_json = json.loads(page.html.split('pre style="word-wrap: break-word; white-space: pre-wrap;">')[1].split('</pre>')[0])
                filename = f"debug_json/DETAIL_STRIP_{strip_id}.json"
                
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(strip_json, f, indent=4)
                print(f"    [SUCCESS] Tersimpan: {filename}")
            except:
                print(f"    [FAILED] Gagal parsing JSON untuk ID: {strip_id}")

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        print("\n[*] Misi Selesai. Semua strip target telah diproses.")
        page.quit()

if __name__ == "__main__":
    scrap_vision_direct()
