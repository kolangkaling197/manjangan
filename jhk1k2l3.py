from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

# Buat folder untuk hasil scan jika belum ada
if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_deep_sniff():
    # KONFIGURASI HEADLESS (Penting untuk GitHub Actions)
    co = ChromiumOptions()
    co.headless()  # Menjalankan browser tanpa jendela fisik
    co.set_argument('--no-sandbox')  # Bypass OS security model
    co.set_argument('--disable-gpu')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("--- DEEP SNIFFING VISION+ (MODE OTOMATIS GITHUB) ---")
    
    # Mulai pantau aktivitas network
    page.listen.start() 
    
    try:
        # Buka halaman target
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        page.get(url)
        print(f"[*] Membuka: {url}")
        
        count = 0
        found_data = False
        
        # SIMULASI INTERAKSI (Otomatis gantiin tangan manusia)
        print("[*] Melakukan Auto-Scroll untuk memicu loading data...")
        for s in range(5):
            page.scroll.down(2000) # Scroll ke bawah
            time.sleep(2)          # Tunggu konten render
            print(f"    > Scroll step {s+1}/5")

        # Cek paket yang tertangkap selama 30 detik terakhir
        print("[*] Menganalisis paket network yang tertangkap...")
        
        # Ambil semua paket yang tertangkap di listener
        for res in page.listen.steps():
            try:
                # Filter hanya respon yang memiliki body dan berupa JSON
                if res.response.body is not None:
                    body = res.response.body
                    url_path = res.url.split('/')[-1].split('?')[0]
                    
                    if isinstance(body, dict):
                        count += 1
                        # Ubah baris pembuatan filename di scraper.py kamu menjadi:
                        timestamp = time.strftime("%Y%m%d-%H%M%S")
                        filename = f"debug_json/paket_{timestamp}_{count}_{url_path}.json"
                        
                        # Simpan ke file
                        with open(filename, "w", encoding="utf-8") as f:
                            json.dump(body, f, indent=4)
                        
                        # Cek kata kunci target
                        body_str = str(body).lower()
                        if 'clusters' in body_str or 'originaltitle' in body_str or 'sport' in body_str:
                            print(f"[!!!] DATA BERHARGA DITEMUKAN: {filename}")
                            found_data = True
            except Exception:
                continue
            
            # Limit agar tidak terlalu banyak file (opsional)
            if count > 50: break

        if not found_data:
            print("\n[-] Scan selesai. Tidak ada pola 'clusters' yang spesifik, silakan cek manual di folder 'debug_json'.")
        else:
            print(f"\n[+] Selesai! Berhasil menangkap {count} paket JSON.")

    except Exception as e:
        print(f"[-] Terjadi kesalahan: {e}")
    finally:
        page.listen.stop()
        page.quit()
        print("[*] Browser ditutup.")

if __name__ == "__main__":
    scrap_vision_deep_sniff()
