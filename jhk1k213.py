from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Pastikan folder bersih setiap kali jalan agar tidak menumpuk sampah lama
if os.path.exists('debug_json'):
    import shutil
    shutil.rmtree('debug_json')
os.makedirs('debug_json')

def scrap_vision_all_packets():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("--- CAPTURING ALL NETWORK PACKETS ---", flush=True)
    
    page.listen.start() 
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(url)
        print(f"[*] Opening: {url}", flush=True)
        
        # Auto-Scroll lebih dalam untuk memicu paket 5, 6, 7, 8, dst.
        for s in range(8):
            page.scroll.down(2000)
            print(f"    > Scroll step {s+1}/8", flush=True)
            time.sleep(3) 

        print("[*] Saving all captured JSON packets...", flush=True)
        
        count = 0
        for res in page.listen.steps(count=100, timeout=5):
            try:
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, dict):
                        count += 1
                        # Ambil nama unik dari URL agar file tidak tertukar
                        url_name = res.url.split('/')[-1].split('?')[0] or "api_data"
                        filename = f"debug_json/paket_{count}_{url_name}.json"
                        
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        print(f"    [SAVED] {filename}", flush=True)
            except:
                continue

        print(f"\n[OK] Done! Captured {count} packets.", flush=True)

    except Exception as e:
        print(f"[-] Error: {e}", flush=True)
    finally:
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_all_packets()
