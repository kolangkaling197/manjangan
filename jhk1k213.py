from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

output_dir = 'debug_json'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def scrap_vision_sniffer():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    
    page = ChromiumPage(co)
    print("\n[*] MEMULAI MODE SUPER SNIFFER (SCROLL & CAPTURE)...")
    
    # Target ID yang kamu cari
    target_ids = ['18894', '13452', '14235', '12420', '18832', '18914', '18916', '18918']
    found_ids = set()

    # Mulai dengerin network
    page.listen.start()
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(url)
        
        # Tunggu sampai halaman stabil
        time.sleep(10)

        # --- SCROLLING BERTAHAP ---
        for i in range(25): # 25 kali scroll
            dist = (i + 1) * 800
            page.run_js(f'window.scrollTo(0, {dist});')
            print(f"    [>] Scroll ke {dist}px... ({i+1}/25)")
            
            # Setiap scroll, kita cek paket yang masuk
            time.sleep(3)
            
            for res in page.listen.steps(count=10, timeout=1):
                try:
                    if '/elements/strips/' in res.url:
                        strip_id = res.url.split('/')[-1].split('?')[0]
                        
                        if strip_id in target_ids and strip_id not in found_ids:
                            body = res.response.body
                            if body:
                                filename = f"{output_dir}/DETAIL_STRIP_{strip_id}.json"
                                with open(filename, "w", encoding="utf-8") as f:
                                    json.dump(body, f, indent=4)
                                
                                found_ids.add(strip_id)
                                print(f"    [FOUND] Berhasil menangkap ID: {strip_id}")
                except:
                    continue
            
            # Jika semua sudah ketemu, berhenti
            if len(found_ids) >= len(target_ids):
                print("[!] Semua target ID sudah tertangkap!")
                break

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        page.listen.stop()
        page.quit()
        print(f"\n[*] SELESAI. Berhasil dapat {len(found_ids)} dari {len(target_ids)} target.")

if __name__ == "__main__":
    scrap_vision_sniffer()
