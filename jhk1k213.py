from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Buat folder untuk hasil scan jika belum ada
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')
    print("[*] Folder debug_json dibuat.", flush=True)

def scrap_vision_deep_sniff():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("--- STARTING VISION+ SNIFFER (MODE GITHUB) ---", flush=True)
    
    page.listen.start() 
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka URL: {url}", flush=True)
        page.get(url)
        
        # Simulasi scroll
        for s in range(5):
            page.scroll.down(2000)
            time.sleep(2)
            print(f"    > Auto-Scroll Step {s+1}/5...", flush=True)

        print("[*] Menganalisis paket network yang masuk...", flush=True)
        
        count = 0
        found_target = False
        start_time = time.time()
        timeout = 120  # Batas waktu maksimal 2 menit agar tidak stuck di GitHub

        for res in page.listen.steps():
            # Proteksi agar tidak stuck selamanya
            if time.time() - start_time > timeout:
                print("[!] Timeout tercapai (120 detik). Menghentikan sniffing.", flush=True)
                break

            try:
                # Log setiap URL yang lewat (agar kamu tahu script tidak mati)
                # print(f"    [Network] {res.url[:70]}...", flush=True)

                if res.response.body is not None:
                    body = res.response.body
                    
                    if isinstance(body, dict):
                        count += 1
                        url_path = res.url.split('/')[-1].split('?')[0]
                        filename = f"debug_json/paket_{count}_{url_path}.json"
                        
                        # Simpan semua paket JSON untuk di-audit
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        # LOG KHUSUS JIKA TARGET 1799 KETEMU
                        if '1799' in res.url or '1799' in str(body):
                            print(f"\n[!!!] TARGET API 1799 DITEMUKAN: {filename}", flush=True)
                            print(f"      URL: {res.url}", flush=True)
                            found_target = True
                            # Optional: break jika hanya ingin ambil 1799 saja
                            # break 

            except Exception as e:
                continue
            
            if count >= 60: # Batasi jumlah file agar repo tidak bengkak
                print("[*] Sudah mencapai limit 60 file. Selesai.", flush=True)
                break

        if not found_target:
            print("\n[-] Scan selesai. Target 1799 tidak tertangkap secara spesifik.", flush=True)
        else:
            print(f"\n[+] Berhasil menangkap total {count} paket JSON.", flush=True)

    except Exception as e:
        print(f"[-] Terjadi kesalahan fatal: {e}", flush=True)
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Browser ditutup. Proses selesai.", flush=True)

if __name__ == "__main__":
    scrap_vision_deep_sniff()
