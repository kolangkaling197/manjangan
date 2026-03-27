from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

output_dir = 'debug_json'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def scrap_vision_content_hunter():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    
    page = ChromiumPage(co)
    print("\n[*] MEMULAI MODE CONTENT HUNTER (AMBIL JADWAL ASLI)...")
    
    target_ids = ['18894', '13452', '14235', '12420', '18832', '18914', '18916', '18918']
    
    try:
        # Buka halaman utama untuk validasi session
        page.get('https://www.visionplus.id/webclient/?pageId=4030')
        print("[*] Menunggu Sinkronisasi Session...")
        time.sleep(10)

        for s_id in target_ids:
            print(f"    [>] Menarik Jadwal Lengkap ID: {s_id}...")
            
            # KUNCI UTAMA: Menambahkan page=0 dan pageSize=50 untuk memaksa data jadwal keluar
            api_url = (
                f"https://www.visionplus.id/elements/strips/{s_id}?"
                "language=ENG&mode=guest&page=0&pageSize=50&partition=IndonesiaPartition&region=Indonesia&target=WEB"
            )
            
            # Injeksi Fetch
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
                # Cek apakah ada field 'contents' di dalam JSON-nya
                filename = f"{output_dir}/DETAIL_STRIP_{s_id}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=4)
                
                # Hitung berapa banyak jadwal yang tertangkap
                items = result.get('contents', [])
                print(f"    [SUCCESS] Tersimpan! Ditemukan {len(items)} jadwal pertandingan.")
            else:
                print(f"    [FAILED] Gagal menarik data ID: {s_id}")
            
            time.sleep(5)

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        page.quit()
        print("\n[*] SEMUA JADWAL BERHASIL DIPROSES.")

if __name__ == "__main__":
    scrap_vision_content_hunter()
