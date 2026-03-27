from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time
import re

# Folder untuk hasil
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
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    print("--- MODE DUMP TOTAL UNTUK GITHUB ACTIONS ---")
    
    # Listen SEMUA request (sama seperti script VS Code kamu)
    page.listen.start()
    
    try:
        target_url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(target_url)
        print(f"[*] Membuka: {target_url}")
        page.wait.doc_loaded(timeout=15)
        
        print("[*] SCROLL OTOMATIS SUPER AGRESIF (ganti manual scroll)...")
        
        count = 0
        start_time = time.time()
        duration = 90   # naikkan jadi 90 detik biar lebih banyak strip
        
        while time.time() - start_time < duration:
            # Scroll otomatis
            page.scroll.to_bottom()
            time.sleep(2.5)   # jeda optimal
            
            # Ambil paket data
            res = page.listen.wait(timeout=1)
            
            if res:
                try:
                    body = res.response.body
                    
                    # Hanya simpan kalau JSON
                    if isinstance(body, (dict, list)):
                        count += 1
                        
                        # Nama file paket (sama seperti script VS Code kamu)
                        url_clean = res.url.split('/')[-1].split('?')[0][:30]
                        paket_filename = f"{output_dir}/paket_{count:03d}_{url_clean}.json"
                        
                        wrapper = {
                            "url": res.url,
                            "method": res.request.method,
                            "headers": dict(res.request.headers),
                            "response_body": body
                        }
                        
                        with open(paket_filename, "w", encoding="utf-8") as f:
                            json.dump(wrapper, f, indent=4)
                        
                        print(f"[{count:03d}] Tersimpan: {paket_filename}")
                        
                        # === EKSTRAK CLEAN STRIP (yang kamu inginkan) ===
                        if '/strips/' in res.url:
                            match = re.search(r'/strips/(\d+)', res.url)
                            if match:
                                strip_id = match.group(1)
                                clean_filename = f"{clean_dir}/clean_strip_{strip_id}.json"
                                
                                # Simpan hanya response_body bersih
                                with open(clean_filename, "w", encoding="utf-8") as f:
                                    json.dump(body, f, indent=4, ensure_ascii=False)
                                
                                # Hitung event
                                if isinstance(body, list):
                                    content_count = sum(1 for item in body if isinstance(item, dict) and item.get("cellType") == "CONTENT")
                                else:
                                    content_count = 0
                                
                                print(f"   → clean_strip_{strip_id}.json → {content_count} event")
                
                except:
                    continue
            
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
