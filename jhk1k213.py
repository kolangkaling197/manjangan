from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

output_dir = 'debug_json'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def scrap_vision_final_boss():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    
    page = ChromiumPage(co)
    print("\n[*] MEMULAI MODE FINAL BOSS (API DIRECT FETCH)...")
    
    try:
        # STEP 1: Ambil Peta Utama
        main_api = "https://www.visionplus.id/elements/page/4030?language=ENG&mode=guest&partition=IndonesiaPartition&region=Indonesia&target=WEB"
        print(f"[*] Mengambil peta utama...")
        
        page.get(main_api)
        time.sleep(5)
        
        # Ambil data dari elemen body langsung (cara paling aman)
        raw_text = page.ele('tag:body').text
        main_data = json.loads(raw_text)

        # Simpan file utama
        with open(f"{output_dir}/UTAMA_4030.json", "w") as f:
            json.dump(main_data, f, indent=4)

        # STEP 2: Cari semua ID Strip
        target_urls = []
        for comp in main_data.get('components', []):
            for content in comp.get('contents', []):
                load_url = content.get('load', {}).get('url')
                if load_url and '/elements/strips/' in load_url:
                    # Bersihkan URL agar tidak double parameter
                    clean_path = load_url.split('?')[0]
                    full_url = f"https://www.visionplus.id{clean_path}?language=ENG&mode=guest&partition=IndonesiaPartition&region=Indonesia&target=WEB"
                    target_urls.append(full_url)

        print(f"[+] Ditemukan {len(target_urls)} Target Strip. Mulai download...")

        # STEP 3: Download menggunakan direct navigation
        for index, s_url in enumerate(target_urls):
            strip_id = s_url.split('/')[-1].split('?')[0]
            print(f"    [>] Ambil Data Strip {index+1}/{len(target_urls)} (ID: {strip_id})")
            
            # Kunjungi URL API langsung
            page.get(s_url)
            time.sleep(3) # Kasih napas 3 detik
            
            try:
                # Ambil teks mentah dari body browser
                content_text = page.ele('tag:body').text
                
                # Validasi apakah isinya JSON
                strip_json = json.loads(content_text)
                
                filename = f"{output_dir}/DETAIL_STRIP_{strip_id}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(strip_json, f, indent=4)
                print(f"    [SUCCESS] Tersimpan ke {filename}")
            except Exception as e:
                print(f"    [FAILED] Gagal simpan ID {strip_id}. Error: {e}")

    except Exception as e:
        print(f"[-] Error Global: {e}")
    finally:
        page.quit()
        print("\n[*] PROSES SELESAI.")

if __name__ == "__main__":
    scrap_vision_final_boss()
