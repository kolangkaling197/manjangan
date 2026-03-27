from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time
import re

if not os.path.exists('debug_json_clean'):
    os.makedirs('debug_json_clean')

def scrap_vision_all_clean_strips():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    print("--- SCRAPING SEMUA CLEAN STRIP (termasuk 14235) ---", flush=True)
   
    page.listen.start('strips')
   
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(url)
        page.wait.doc_loaded(timeout=15)
        
        print("[*] Scroll super agresif + auto-request semua strip...")
        for s in range(20):
            page.scroll.to_bottom()
            print(f" > Scroll step {s+1}/20", flush=True)
            time.sleep(3)
            
            res = page.listen.wait(timeout=6)
            if res and '/strips/' in res.url:
                match = re.search(r'/strips/(\d+)', res.url)
                if match:
                    strip_id = match.group(1)
                    try:
                        body = res.response.body
                        if isinstance(body, (bytes, bytearray)):
                            body = json.loads(body.decode('utf-8'))
                        elif isinstance(body, str):
                            body = json.loads(body)
                        
                        filename = f"debug_json_clean/clean_strip_{strip_id}.json"
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4, ensure_ascii=False)
                        
                        content_count = sum(1 for item in body if isinstance(item, dict) and item.get("cellType") == "CONTENT")
                        print(f"[OK] clean_strip_{strip_id}.json → {content_count} event", flush=True)
                    except:
                        pass
        
        print("\n[🎉 SELESAI] Semua clean_strip sudah disimpan!")
        
    except Exception as e:
        print(f"[-] Error: {e}", flush=True)
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Browser ditutup.")

if __name__ == "__main__":
    scrap_vision_all_clean_strips()
