from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

output_dir = 'debug_json'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def scrap_vision_target_1799():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    
    page = ChromiumPage(co)
    print("\n[*] FOKUS TARGET: STRIP 1799 & 1779 (LIVE EVENTS)...")
    
    # Kita tambahkan 1779 dan 1799 ke daftar buruan
    target_ids = ['1799', '1779', '18894', '13452'] 
    
    try:
        page.get('https://www.visionplus.id/webclient/?pageId=4030')
        print("[*] Sinkronisasi Session... (10 detik)")
        time.sleep(10)

        for s_id in target_ids:
            print(f"    [>] Menarik Konten Strip ID: {s_id}...")
            
            # Gunakan pageSize besar agar semua jadwal keluar
            api_url = (
                f"https://www.visionplus.id/elements/strips/{s_id}?"
                "language=ENG&mode=guest&page=0&pageSize=100&partition=IndonesiaPartition&region=Indonesia&target=WEB"
            )
            
            script = f"""
            return fetch('{api_url}', {{
                "headers": {{
                    "accept": "application/json",
                    "x-requested-with": "XMLHttpRequest"
                }}
            }})
            .then(res => res.json())
            .catch(err => "ERROR");
            """
            
            result = page.run_js(script)
            
            if result and result != "ERROR":
                filename = f"{output_dir}/DETAIL_STRIP_{s_id}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=4)
                
                # Cek isi konten
                items = result.get('contents', [])
                print(f"    [SUCCESS] ID {s_id}: Tersimpan {len(items)} pertandingan.")
                
                # Jika ada konten, tampilkan 3 judul pertama di log buat bukti
                if items:
                    for idx, item in enumerate(items[:3]):
                        print(f"        - Event {idx+1}: {item.get('title')}")
            else:
                print(f"    [FAILED] ID {s_id} tidak merespon.")
            
            time.sleep(5)

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        page.quit()
        print("\n[*] PROSES TARGET KHUSUS SELESAI.")

if __name__ == "__main__":
    scrap_vision_target_1799()
