from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

if not os.path.exists('debug_json'):
    os.makedirs('debug_json')
    print("[*] Folder debug_json siap.")

def scrap_vision_all_strips():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    print("--- SCRAPING SEMUA STRIP DI PAGE 4030 ---", flush=True)
   
    # Listen ke SEMUA strip (bukan hanya 1799)
    page.listen.start('strips')
   
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka halaman Live Sport Events...", flush=True)
        page.get(url)
        page.wait.doc_loaded(timeout=15)
        
        print("[*] Scroll super agresif untuk load semua strip...")
        strip_data = {}   # simpan per strip
        
        for s in range(18):
            page.scroll.to_bottom()
            print(f" > Scroll step {s+1}/18...", flush=True)
            time.sleep(3.5)
            
            res = page.listen.wait(timeout=8)
            if res and 'strips' in res.url and res.response.body:
                url_str = res.url
                strip_id = url_str.split('/strips/')[1].split('?')[0]
                print(f"   [CAUGHT] Strip ID: {strip_id}", flush=True)
                
                try:
                    body = res.response.body
                    if isinstance(body, (bytes, bytearray)):
                        body = json.loads(body.decode('utf-8'))
                    elif isinstance(body, str):
                        body = json.loads(body)
                    
                    # Hitung berapa event CONTENT
                    content_list = [item for item in body if isinstance(item, dict) and item.get("cellType") == "CONTENT"]
                    count = len(content_list)
                    
                    strip_data[strip_id] = {
                        "url": url_str,
                        "content_count": count,
                        "data": body
                    }
                    
                    print(f"   [+] Strip {strip_id} → {count} event", flush=True)
                    
                    # Simpan tiap strip
                    with open(f"debug_json/strip_{strip_id}.json", "w", encoding="utf-8") as f:
                        json.dump(body, f, indent=4, ensure_ascii=False)
                        
                except:
                    pass
        
        # Cari strip dengan event terbanyak (kemungkinan besar 32)
        if strip_data:
            best_strip = max(strip_data.values(), key=lambda x: x["content_count"])
            best_id = max(strip_data, key=lambda k: strip_data[k]["content_count"])
            
            print(f"\n[OK] STRIP TERBAIK: {best_id} ({best_strip['content_count']} event)")
            print(f"[OK] Total strip yang berhasil di-load: {len(strip_data)}")
            
            # Simpan juga sebagai paket utama
            with open("debug_json/paket_full_events.json", "w", encoding="utf-8") as f:
                json.dump(best_strip["data"], f, indent=4, ensure_ascii=False)
            
            print(f"[OK] Data lengkap disimpan ke debug_json/paket_full_events.json")
        else:
            print("[-] Tidak ada strip yang tertangkap.")
            
    except Exception as e:
        print(f"[-] Error fatal: {e}", flush=True)
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Browser ditutup. Selesai.", flush=True)

if __name__ == "__main__":
    scrap_vision_all_strips()
