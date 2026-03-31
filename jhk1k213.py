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
    co.set_argument('--window-size=1920,1200')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    print("--- MODE DUMP SUPER AGRESIF V5.0 (untuk 18973, 15752, dll) ---")
    
    page.listen.start()
    
    try:
        target_url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(target_url)
        print(f"[*] Membuka: {target_url}")
        page.wait.doc_loaded(timeout=30)
        
        print("[*] SCROLL + FAKE MOUSE + SMOOTH JS (6 menit)...")
        
        count = 0
        strip_count = 0
        start_time = time.time()
        duration = 360  # 6 menit
        
        while time.time() - start_time < duration:
            # PASS 1: Scroll ke bawah dengan smooth JS
            for i in range(15):
                # Smooth scroll via JavaScript
                page.run_js(f"window.scrollBy({{top: {800 + i*50}, left: 0, behavior: 'smooth'}});")
                # Fake mouse movement
                page.mouse.move(500 + (i % 5) * 100, 300 + (i % 7) * 80)
                time.sleep(1.1)
            
            # PASS 2: Scroll ke atas sedikit lalu ke bawah lagi (trigger lazy load)
            page.run_js("window.scrollTo({top: 0, left: 0, behavior: 'smooth'});")
            time.sleep(2)
            for _ in range(8):
                page.run_js("window.scrollBy({top: 1200, left: 0, behavior: 'smooth'});")
                time.sleep(1.3)
            
            # Drain semua packet
            while True:
                res = page.listen.wait(timeout=0.25)
                if not res:
                    break
                
                try:
                    url = res.url
                    body = res.response.body
                    
                    if isinstance(body, (str, bytes)):
                        try:
                            body = json.loads(body.decode('utf-8') if isinstance(body, bytes) else body)
                        except:
                            continue
                    
                    if isinstance(body, (dict, list)):
                        count += 1
                        
                        url_clean = url.split('/')[-1].split('?')[0][:30]
                        filename = f"{output_dir}/paket_{count:03d}_{url_clean}.json"
                        
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump({
                                "url": url,
                                "method": res.request.method,
                                "headers": dict(res.request.headers),
                                "response_body": body
                            }, f, indent=4, ensure_ascii=False)
                        
                        print(f"[{count:03d}] Tersimpan: {filename}")
                        
                        # Simpan clean strip (support /elements/strips/ dan /strips/)
                        if '/strips/' in url:
                            match = re.search(r'/strips/(\d+)', url)
                            if match:
                                strip_id = match.group(1)
                                clean_filename = f"{clean_dir}/clean_strip_{strip_id}.json"
                                
                                with open(clean_filename, "w", encoding="utf-8") as f:
                                    json.dump(body, f, indent=4, ensure_ascii=False)
                                
                                content_count = sum(1 for item in body if isinstance(item, dict) and item.get("cellType") == "CONTENT") if isinstance(body, list) else 0
                                print(f" → ✅ clean_strip_{strip_id}.json → {content_count} event")
                                strip_count += 1
                                
                except:
                    continue
            
            elapsed = int(time.time() - start_time)
            if elapsed % 30 == 0:
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
