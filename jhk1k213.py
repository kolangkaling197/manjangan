from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Folder output
output_dir = 'debug_json'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def scrap_vision_auto():
    # Setting headless agar bisa jalan di server GitHub
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    
    page = ChromiumPage(co)
    print("[*] MEMULAI SCRAPING OTOMATIS...")
    
    page.listen.start()
    
    try:
        # Buka halaman
        page.get('https://www.visionplus.id/webclient/?pageId=4030')
        
        # Simulasi scroll otomatis agar semua strip (MotoGP, dll) terpancing keluar
        for _ in range(10):
            page.scroll.down(1500)
            time.sleep(2) # Beri jeda agar API sempat nembak
            
        print("[*] Menganalisis paket data...")
        count = 0
        
        # Ambil paket yang sudah tertangkap di buffer
        for res in page.listen.steps(count=100, timeout=10):
            try:
                body = res.response.body
                if isinstance(body, (dict, list)):
                    count += 1
                    
                    # Logika penamaan: Prioritaskan ID Strip (angka)
                    url_part = res.url.split('/')[-1].split('?')[0]
                    
                    if 'strips' in res.url:
                        filename = f"{output_dir}/DETAIL_STRIP_{url_part}.json"
                    else:
                        filename = f"{output_dir}/paket_{count:03d}_{url_part[:20]}.json"
                    
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(body, f, indent=4)
                    
                    print(f"    [SAVED] {filename}")
            except:
                continue

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        page.listen.stop()
        page.quit()
        print(f"\n[+] Sukses menyimpan {count} file.")

if __name__ == "__main__":
    scrap_vision_auto()
