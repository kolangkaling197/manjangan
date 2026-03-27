from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

output_dir = 'debug_json'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def scrap_vision_inject():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    print("\n[*] MEMULAI MODE INJEKSI JAVASCRIPT...")
    
    target_ids = ['18894', '13452', '14235', '12420', '18832', '18914', '18916', '18918']
    
    try:
        # 1. Buka halaman utama dulu agar dapat Cookies/Session
        page.get('https://www.visionplus.id/webclient/?pageId=4030')
        print("[*] Menunggu Session/Cookies stabil...")
        time.sleep(10)

        # 2. Hajar API secara internal lewat Fetch JS (Bypass CORS/Bot Detection)
        for s_id in target_ids:
            print(f"    [>] Mengambil Strip ID: {s_id} via Injeksi...")
            
            api_url = f"https://www.visionplus.id/elements/strips/{s_id}?language=ENG&mode=guest&partition=IndonesiaPartition&region=Indonesia&target=WEB"
            
            # Kita suruh browser yang melakukan fetch, bukan Python
            script = f"""
            return fetch('{api_url}')
              .then(response => response.json())
              .catch(err => 'ERROR');
            """
            
            result = page.run_js(script)
            
            if result != 'ERROR' and result is not None:
                filename = f"{output_dir}/DETAIL_STRIP_{s_id}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=4)
                print(f"    [SUCCESS] Berhasil mengamankan ID: {s_id}")
            else:
                print(f"    [FAILED] ID {s_id} diblokir atau gagal.")
            
            time.sleep(3) # Jeda antar request

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        page.quit()
        print("\n[*] PROSES SELESAI.")

if __name__ == "__main__":
    scrap_vision_inject()
