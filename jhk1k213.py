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
    co.headless()                    # tetap headless
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--window-size=1920,1080')   # viewport besar biar lazy-load trigger
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    print("--- MODE DUMP TOTAL UNTUK GITHUB ACTIONS ---")
    
    page.listen.start()
    
    try:
        target_url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(target_url)
        print(f"[*] Membuka: {target_url}")
        page.wait.doc_loaded(timeout=15)
        
        print("[*] SCROLL OTOMATIS SUPER AGRESIF + DEBUG LISTENER AKTIF...")
        
        count = 0
        start_time = time.time()
        duration = 120  # naikkan jadi 120 detik biar lebih aman
        
        while time.time() - start_time < duration:
            # Scroll lebih natural (bukan langsung to_bottom)
            page.scroll.to_bottom()
            time.sleep(3.5)
            
            # === DRAIN SEMUA PACKET (ini kuncinya!) ===
            packet_count = 0
            while True:
                res = page.listen.wait(timeout=0.4)  # timeout kecil biar cepat drain
                if not res:
                    break
                
                packet_count += 1
                try:
                    url = res.url
                    body = res.response.body
                    
                    # Debug: tampilkan SEMUA request yang tertangkap
                    print(f"[DEBUG] Request ke: {url[:100]}...")
                    
                    # Parsing body manual (kalau masih string/bytes)
                    if isinstance(body, (str, bytes)):
                        try:
                            body = json.loads(body.decode('utf-8') if isinstance(body, bytes) else body)
                        except:
                            body = None
                    
                    if isinstance(body, (dict, list)):
                        count += 1
                        url_clean = url.split('/')[-1].split('?')[0][:30]
                        paket_filename = f"{output_dir}/paket_{count:03d}_{url_clean}.json"
                        
                        wrapper = {
                            "url": url,
                            "method": res.request.method,
                            "headers": dict(res.request.headers),
                            "response_body": body
                        }
                        
                        with open(paket_filename, "w", encoding="utf-8") as f:
                            json.dump(wrapper, f, indent=4, ensure_ascii=False)
                        
                        print(f"[{count:03d}] Tersimpan: {paket_filename}")
                        
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
                
                except Exception as e:
                    print(f"[ERROR] Gagal proses packet: {e}")
                    continue
            
            if packet_count > 0:
                print(f"[*] Diproses {packet_count} packet di iterasi ini")
            
            elapsed = int(time.time() - start_time)
            if elapsed % 10 == 0:
                print(f"[*] Monitoring berjalan... ({elapsed}/{duration} detik)")
        
        print(f"\n[+] SELESAI! {count} file JSON telah disimpan.")
        print(f"[+] Clean strip disimpan di folder '{clean_dir}'")
        
    except Exception as e:
        print(f"[-] Terjadi kesalahan: {e}")
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Browser ditutup.")

if __name__ == "__main__":
    scrap_vision_github_actions()
