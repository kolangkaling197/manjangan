from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

output_dir = 'debug_json'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def scrap_vision_brute():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    
    page = ChromiumPage(co)
    print("\n[*] MEMULAI MODE BRUTE FORCE (DIRECT ID ACCESS)...")
    
    try:
        # STEP 1: Ambil Peta Utama (Isinya daftar ID 9 Strip itu)
        main_api = "https://www.visionplus.id/elements/page/4030?language=ENG&mode=guest&partition=IndonesiaPartition&region=Indonesia&target=WEB"
        print(f"[*] Mengambil daftar ID dari: {main_api}")
        
        page.get(main_api)
        time.sleep(5)
        
        # Ekstrak konten JSON dari halaman
        raw_html = page.html
        if 'pre style=' in raw_html:
            json_str = raw_html.split('pre style="word-wrap: break-word; white-space: pre-wrap;">')[1].split('</pre>')[0]
            main_data = json.loads(json_str)
        else:
            # Fallback jika tampilan beda
            main_data = json.loads(page.ele('tag:body').text)

        # Simpan file utama
        with open(f"{output_dir}/UTAMA_4030.json", "w") as f:
            json.dump(main_data, f, indent=4)

        # STEP 2: Cari semua URL Strip
        target_urls = []
        for comp in main_data.get('components', []):
            for content in comp.get('contents', []):
                load_url = content.get('load', {}).get('url')
                if load_url and '/elements/strips/' in load_url:
                    full_url = f"https://www.visionplus.id{load_url}?language=ENG&mode=guest&partition=IndonesiaPartition&region=Indonesia&target=WEB"
                    target_urls.append(full_url)

        print(f"[+] Ditemukan {len(target_urls)} Target Strip. Mulai download paksa...")

        # STEP 3: Hajar satu per satu
        for index, s_url in enumerate(target_urls):
            strip_id = s_url.split('/')[-1].split('?')[0]
            print(f"    [>] Downloading {index+1}/{len(target_urls)}: ID {strip_id}")
            
            page.get(s_url)
            time.sleep(2) # Jeda sopan agar tidak kena block
            
            try:
                # Ambil JSON dari browser
                s_raw = page.html.split('pre style="word-wrap: break-word; white-space: pre-wrap;">')[1].split('</pre>')[0]
                s_json = json.loads(s_raw)
                
                filename = f"{output_dir}/DETAIL_STRIP_{strip_id}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(s_json, f, indent=4)
                print(f"    [SUCCESS] {filename}")
            except:
                print(f"    [FAILED] Gagal ambil ID {strip_id}")

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        page.quit()
        print("\n[*] SEMUA STRIP BERHASIL DIAMANKAN.")

if __name__ == "__main__":
    scrap_vision_brute()
