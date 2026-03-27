from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

if not os.path.exists('debug_json'):
    os.makedirs('debug_json')
    print("[*] Folder debug_json siap.")

def scrap_vision_target_1799():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    print("--- DIAGNOSTIC MODE: LISTEN ALL + PRINT SEMUA URL ---", flush=True)
   
    # Listen SEMUA request (tidak dibatasi 1799)
    page.listen.start()
   
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka halaman...", flush=True)
        page.get(url)
        page.wait.doc_loaded(timeout=15)
        
        print("[*] Mulai scroll agresif + diagnostic (20 step)...")
        max_content = 0
        best_body = None
        caught_urls = []
        
        for s in range(20):   # 20x scroll biar sangat agresif
            page.scroll.to_bottom()   # pakai to_bottom agar lebih kuat
            print(f" > Scroll step {s+1}/20...", flush=True)
            time.sleep(4)
            
            res = page.listen.wait(timeout=6)
            if res and res.response.body:
                url_str = res.url
                caught_urls.append(url_str)
                print(f"   [CAUGHT] {url_str}", flush=True)
                
                # Cek apakah ini strip/content
                if any(x in url_str for x in ['strips', 'elements', 'content', '1799', '1800']):
                    print(f"   *** POTENTIAL NEW BATCH: {url_str} ***", flush=True)
                
                # Parse body dan hitung event
                try:
                    body = res.response.body
                    if isinstance(body, (bytes, bytearray)):
                        body = json.loads(body.decode('utf-8'))
                    elif isinstance(body, str):
                        body = json.loads(body)
                    
                    content_count = sum(1 for item in body if isinstance(item, dict) and item.get("cellType") == "CONTENT")
                    if content_count > max_content:
                        max_content = content_count
                        best_body = body
                        print(f"   [+] Event CONTENT naik jadi: {content_count}", flush=True)
                except:
                    pass
        
        # Coba klik Load More button (kalau ada)
        print("[*] Mencoba klik Load More button...")
        try:
            # Bisa pakai text atau class (sesuai website Vision+)
            load_more = page.ele('text:contains("Lebih")') or page.ele('text:contains("More")') or page.ele('.load-more') or page.ele('a[href*="pageId=4030"]')
            if load_more:
                load_more.click()
                print("[+] Load More button diklik!", flush=True)
                time.sleep(6)
                res = page.listen.wait(timeout=10)
                if res:
                    print(f"   [CAUGHT after click] {res.url}", flush=True)
        except Exception as click_err:
            print(f"   [-] Tidak menemukan Load More button: {click_err}", flush=True)
        
        # Simpan hasil terbaik
        if best_body:
            filename = "debug_json/paket_21_1799.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(best_body, f, indent=4, ensure_ascii=False)
            print(f"[OK] BERHASIL! Total CONTENT event: {max_content} → disimpan ke {filename}", flush=True)
        else:
            print("[-] Tidak ada data CONTENT yang berhasil diambil.", flush=True)
            
        # Tampilkan semua URL yang pernah tertangkap
        print(f"\n[*] Total {len(caught_urls)} request tertangkap. URL yang berpotensi strip:")
        for u in caught_urls:
            if any(x in u for x in ['strips', 'elements', 'content']):
                print(f"   → {u}")
        
    except Exception as e:
        print(f"[-] Error fatal: {e}", flush=True)
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Browser ditutup. Selesai.", flush=True)

if __name__ == "__main__":
    scrap_vision_target_1799()
