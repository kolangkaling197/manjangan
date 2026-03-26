from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Buat folder untuk hasil scan jika belum ada
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')
    print("[*] Folder 'debug_json' berhasil dibuat.")

def scrap_vision_deep_sniff():
    # KONFIGURASI HEADLESS (Penting untuk GitHub Actions)
    co = ChromiumOptions()
    co.headless()  
    co.set_argument('--no-sandbox')  
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("\n" + "="*50)
    print("--- DEEP SNIFFING VISION+ (FULL LOG MODE) ---")
    print("="*50 + "\n")
    
    # Mulai pantau aktivitas network
    print("[*] Memulai Network Listener...", flush=True)
    page.listen.start() 
    
    try:
        # Buka halaman target
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Menuju URL: {url}", flush=True)
        page.get(url)
        
        # Cek apakah halaman terbuka
        if page.wait.ele_displayed('tag:body', timeout=15):
            print("[+] Halaman Body terdeteksi. Mulai interaksi...", flush=True)
        
        count = 0
        found_data = False
        
        # SIMULASI INTERAKSI
        print("[*] Melakukan Auto-Scroll untuk memancing API...", flush=True)
        for s in range(5):
            page.scroll.down(2000)
            print(f"    > Scroll Step {s+1}/5 dijalankan.", flush=True)
            time.sleep(3) # Beri jeda lebih lama agar API sempat merespon

        # PROSES ANALISIS PAKET
        print("\n[*] Menganalisis paket network yang masuk...", flush=True)
        
        # Menggunakan langkah-langkah yang tertangkap di buffer
        for res in page.listen.steps(count=100, timeout=5):
            try:
                # Log setiap URL yang lewat (Singkat)
                short_url = res.url[:70] + "..." if len(res.url) > 70 else res.url
                
                if res.response.body is not None:
                    body = res.response.body
                    url_path = res.url.split('/')[-1].split('?')[0]
                    if not url_path: url_path = "root_api"
                    
                    if isinstance(body, dict):
                        count += 1
                        filename = f"debug_json/paket_{count}_{url_path}.json"
                        
                        # Simpan ke file
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        # LOG DETAIL KE CONSOLE
                        print(f"    [FILE] #{count} disimpan: {filename}", flush=True)
                        print(f"    [tautan mencurigakan telah dihapus] {short_url}", flush=True)
                        
                        # Cek kata kunci target
                        body_str = str(body).lower()
                        targets = ['clusters', 'nodes', 'originaltitle', 'sport']
                        match = [t for t in targets if t in body_str]
                        
                        if match:
                            print(f"    [!!!] TARGET TERDETEKSI: {match} di {filename}", flush=True)
                            found_data = True
                        print("-" * 30, flush=True)
                else:
                    # Log jika ada request tapi body kosong (misal: 204 atau error)
                    pass

            except Exception as e:
                print(f"    [!] Skip paket karena: {e}", flush=True)
                continue
            
            if count > 80: 
                print("[*] Limit paket tercapai (80), menghentikan sniffing.", flush=True)
                break

        if not found_data:
            print("\n" + "!"*50)
            print("[-] SCAN SELESAI: Tidak ditemukan pola JSON Event yang pas.")
            print("[-] Kemungkinan halaman terdeteksi bot atau API berubah.")
            print("!"*50)
            # Ambil screenshot sebagai bukti terakhir
            page.get_screenshot(path='debug_json/last_seen_error.png')
            print("[*] Screenshot terakhir disimpan: debug_json/last_seen_error.png")
        else:
            print(f"\n[+] BERHASIL: Menangkap {count} paket JSON. Silakan cek folder 'debug_json'.")

    except Exception as e:
        print(f"\n[-] ERROR FATAL: {e}")
    finally:
        print("\n[*] Menutup Session...", flush=True)
        page.listen.stop()
        page.quit()
        print("[*] Selesai.")

if __name__ == "__main__":
    scrap_vision_deep_sniff()
