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
    print("--- TARGETED SNIFFING: ALL STRIPS (untuk load more) ---", flush=True)
   
    # Dengar SEMUA request (bukan hanya 1799) supaya nangkap batch ke-2
    page.listen.start()
   
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka Vision+ Sports Page...", flush=True)
        page.get(url)
        page.wait.doc_loaded(timeout=15)
        
        print("[*] Scroll agresif untuk trigger load more (target 32 event)...")
        events_before = 0
        for s in range(12):          # naikkan jadi 12x
            page.scroll.down(800)
            print(f" > Scroll step {s+1}/12...", flush=True)
            time.sleep(3)            # jeda lebih lama biar loading selesai
            
            # Cek apakah ada paket baru
            res = page.listen.wait(timeout=8)
            if res and res.response.body:
                try:
                    body = res.response.body
                    if isinstance(body, (bytes, bytearray)):
                        body = json.loads(body.decode('utf-8'))
                    elif isinstance(body, str):
                        body = json.loads(body)
                    
                    # Hitung berapa CONTENT event di paket ini
                    content_count = sum(1 for item in body if isinstance(item, dict) and item.get("cellType") == "CONTENT")
                    if content_count > events_before:
                        print(f"   [+] Dapat {content_count} event baru!", flush=True)
                        events_before = content_count
                except:
                    pass
        
        print("[*] Menunggu paket terakhir...", flush=True)
        res = page.listen.wait(timeout=15)
        
        if res and res.response.body:
            body = res.response.body
            if isinstance(body, (bytes, bytearray)):
                body = json.loads(body.decode('utf-8'))
            elif isinstance(body, str):
                body = json.loads(body)
            
            filename = "debug_json/paket_21_1799.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(body, f, indent=4, ensure_ascii=False)
            
            total_content = sum(1 for item in body if isinstance(item, dict) and item.get("cellType") == "CONTENT")
            print(f"[OK] BERHASIL! Total CONTENT event: {total_content} (seharusnya 32)", flush=True)
            print(f"[OK] Data disimpan ke {filename}", flush=True)
        else:
            print("[-] Masih belum ketemu batch ke-2.", flush=True)
            
    except Exception as e:
        print(f"[-] Error fatal: {e}", flush=True)
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Browser ditutup. Selesai.", flush=True)

if __name__ == "__main__":
    scrap_vision_target_1799()
