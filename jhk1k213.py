from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

output_dir = 'debug_json'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def scrap_vision_fix():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    
    page = ChromiumPage(co)
    print("\n[*] MEMULAI SCRAPING (VERSI STABIL)...")
    
    # Mulai sniffing sebelum buka URL
    page.listen.start()
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(url)
        
        # --- PERBAIKAN UTAMA ---
        # Tunggu sampai salah satu elemen strip muncul di layar (timeout 30 detik)
        print("[*] Menunggu konten dimuat...")
        if page.wait.ele_displayed('tag:div', timeout=30):
            print("[+] Konten terdeteksi! Mulai scrolling...")
            
            # Scroll pelan-pelan agar API terpancing
            for i in range(12):
                page.scroll.down(1200)
                print(f"    [>] Scroll {i+1}/12...")
                time.sleep(3) # Jeda wajib agar network tidak kosong
        else:
            print("[-] Konten gagal dimuat dalam 30 detik.")

        print("[*] Menganalisis paket data...")
        count = 0
        
        # Ambil paket dari buffer
        for res in page.listen.steps(count=150, timeout=15):
            try:
                if res.response.body is not None:
                    body = res.response.body
                    if isinstance(body, (dict, list)):
                        count += 1
                        
                        url_end = res.url.split('/')[-1].split('?')[0]
                        
                        if '/elements/strips/' in res.url:
                            filename = f"{output_dir}/DETAIL_STRIP_{url_end}.json"
                        elif '/elements/page/4030' in res.url:
                            filename = f"{output_dir}/UTAMA_4030.json"
                        else:
                            clean_name = "".join(x for x in url_end if x.isalnum())[:20]
                            filename = f"{output_dir}/paket_{count:03d}_{clean_name}.json"
                        
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        if "DETAIL_STRIP" in filename:
                            print(f"    [FOUND] {filename}")
            except:
                continue

    except Exception as e:
        print(f"[-] Terjadi kesalahan: {e}")
    finally:
        page.listen.stop()
        page.quit()
        print(f"\n[+] SELESAI. Total {count} paket tersimpan.")

if __name__ == "__main__":
    scrap_vision_fix()
