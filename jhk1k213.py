from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time
import re

output_dir = 'debug_json'
clean_dir = 'debug_json_clean'
os.makedirs(output_dir, exist_ok=True)
os.makedirs(clean_dir, exist_ok=True)

def scrap_vision_github_actions():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--window-size=1920,1080')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    print("--- MODE DUMP TOTAL SUPER AGRESIF (untuk 15+ event) ---")
    
    page.listen.start()
    
    try:
        target_url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(target_url)
        print(f"[*] Membuka: {target_url}")
        page.wait.doc_loaded(timeout=20)
        
        print("[*] SCROLL SUPER AGRESIF + DELAY NATURAL...")
        
        count = 0
        strip_count = 0
        start_time = time.time()
        duration = 180  # 3 menit biar semua strip ke-load
        
        while time.time() - start_time < duration:
            # Scroll bertahap (lebih natural)
            for _ in range(5):  # 5x scroll kecil tiap iterasi
                page.scroll.down(800)
                time.sleep(1.2)
            
            # Drain SEMUA packet
            packet_count = 0
            while True:
                res = page.listen.wait(timeout=0.5)
                if not res:
                    break
                packet_count += 1
                
                try:
                    url = res.url
                    body = res.response.body
                    
                    # Parsing body (bisa str/bytes/dict)
                    if isinstance(body, (str, bytes)):
                        try:
                            body = json.loads(body.decode('utf-8') if isinstance(body, bytes) else body)
                        except:
                            continue
                    
                    if isinstance(body, (dict, list)):
                        count += 1
                        
                        # Simpan semua paket
                        url_clean = url.split('/')[-1].split('?')[0][:30]
                        paket_filename = f"{output_dir}/paket_{count:03d}_{url_clean}.json"
                        wrapper = {"url": url, "method": res.request.method, "headers": dict(res.request.headers), "response_body": body}
                        with open(paket_filename, "w", encoding="utf-8") as f:
                            json.dump(wrapper, f, indent=4, ensure_ascii=False)
                        
                        # === CLEAN STRIP ===
                        if '/strips/' in url:
                            match = re.search(r'/strips/(\d+)', url)
                            if match:
                                strip_id = match.group(1)
                                clean_filename = f"{clean_dir}/clean_strip_{strip_id}.json"
                                
                                with open(clean_filename, "w", encoding="utf-8") as f:
                                    json.dump(body, f, indent=4, ensure_ascii=False)
                                
                                content_count = sum(1 for item in body if isinstance(item, dict) and item.get("cellType") == "CONTENT") if isinstance(body, list) else 0
                                print(f" → clean_strip_{strip_id}.json → {content_count} event")
                                strip_count += 1
                                
                except:
                    continue
            
            elapsed = int(time.time() - start_time)
            if elapsed % 15 == 0:
                print(f"[*] Monitoring... ({elapsed}/{duration}s) | Strip ditemukan: {strip_count}")
        
        print(f"\n[+] SELESAI! Total paket: {count} | Strip tersimpan: {strip_count}")
        print(f"[+] Clean strip disimpan di folder '{clean_dir}'")
        
    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Browser ditutup.")

if __name__ == "__main__":
    scrap_vision_github_actions()
