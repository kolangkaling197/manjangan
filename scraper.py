import os
import json
import requests
import time
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- KONFIGURASI ---
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"
FOLDER_ASSETS = "data_scraped/logos"
FILE_OUTPUT = "data_scraped/jadwal_bola.json"

def download_logo(url, nama_tim):
    """Mengunduh logo tim dan menyimpannya secara lokal dengan nama yang bersih."""
    if not url or "http" not in url: 
        return "assets/default_logo.png"
        
    if not os.path.exists(FOLDER_ASSETS): 
        os.makedirs(FOLDER_ASSETS)
    
    # Membersihkan nama file dari karakter ilegal
    nama_aman = "".join([c for c in nama_tim if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
    path_file = os.path.join(FOLDER_ASSETS, f"{nama_aman}.png")
    
    if not os.path.exists(path_file):
        try:
            # Menggunakan header agar tidak diblokir saat download gambar
            headers = {'User-Agent': 'Mozilla/5.0'}
            respon = requests.get(url, headers=headers, timeout=10)
            if respon.status_code == 200:
                with open(path_file, 'wb') as f:
                    f.write(respon.content)
                return path_file
        except Exception as e:
            print(f"      [!] Gagal download logo {nama_tim}: {e}")
            return url
    return path_file

def get_live_stream_link(driver, match_page_url, match_name):
    """Mengambil link m3u8 dengan pembersihan iklan dan force interaction."""
    print(f"\n   [>] SEDANG MEMPROSES: {match_name}")
    try:
        driver.get(match_page_url)
        time.sleep(5) # Tunggu halaman muat sebentar

        # Bersihkan Iklan Overlay yang menghalangi player
        driver.execute_script("""
            var ads = document.querySelectorAll('[id*="ads"], [class*="ads"], [style*="z-index: 9999"], .sh-overlay, .modal');
            ads.forEach(ad => ad.remove());
        """)

        # Cari iframe dan pindah ke dalamnya jika ada
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for i, frame in enumerate(iframes):
            src = frame.get_attribute("src") or ""
            if any(x in src for x in ["bitmovin", "player", "stream", "embed"]):
                driver.switch_to.frame(frame)
                print(f"   [>] Berpindah ke iframe #{i}")
                break

        # Klik area video untuk memancing m3u8
        try:
            video_el = driver.find_elements(By.XPATH, "//video | //div[@id='player'] | //div[contains(@class, 'play')]")
            if video_el:
                driver.execute_script("arguments[0].click();", video_el[0])
        except: pass

        print("   [>] Menunggu traffic network (15 detik)...")
        time.sleep(15)
        
        driver.switch_to.default_content()
        logs = driver.get_log('performance')
        
        for entry in logs:
            message = entry.get('message')
            if '.m3u8' in message:
                url_match = re.search(r'"url":"(https://.*?\.m3u8.*?)"', message)
                if url_match:
                    stream_url = url_match.group(1).replace('\\/', '/')
                    if "ads" not in stream_url.lower():
                        print(f"   [√] LOG FOUND: m3u8 Captured!")
                        return stream_url
                    
        print("   [!] LOG: Tidak ditemukan (Mungkin belum Live).")
    except Exception as e:
        print(f"   [!] ERROR: {e}")
    return "Not Found"

def jalankan_scraper():
    print(f"\n{'='*50}\n[*] STARTING XOILAC STREAM SCRAPER\n{'='*50}")
    
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    # options.add_argument('--headless') # Matikan jika ingin debug visual
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    driver = uc.Chrome(options=options)
    hasil_akhir = []

    try:
        driver.get(TARGET_URL)
        print("[*] Menunggu halaman utama stabil...")
        time.sleep(15) 

        # 1. Bersihkan popup beranda
        driver.execute_script("document.querySelectorAll('.modal, .popup, .fixed').forEach(el => el.remove());")

        # 2. Ambil elemen pertandingan
        wait = WebDriverWait(driver, 20)
        cards = driver.find_elements(By.XPATH, "//a[contains(@href, 'truc-tiep')]")
        
        temp_list = []
        seen_urls = set()
        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and url not in seen_urls and len(teks) > 10:
                imgs = [img.get_attribute("src") for img in card.find_elements(By.TAG_NAME, "img")]
                temp_list.append({"teks": teks, "url": url, "imgs": imgs})
                seen_urls.add(url)

        print(f"[*] Berhasil menarik {len(temp_list)} daftar pertandingan.")
        print(f"[*] Memulai pengambilan link .m3u8 per halaman...\n")

        for item in temp_list:
            try:
                # 1. Bersihkan semua baris teks
                lines = [l.strip() for l in item['teks'].split('\n') if l.strip()]
                
                # 2. Filter Baris Secara Agresif
                # Buang kata iklan, kata VS, dan format menit pertandingan
                trash = ["CƯỢC", "XEM", "LIVE", "TRỰC", "TỶ LỆ", "KÈO", "CLICK", "VS", "-", "PHT"]
                clean_lines = []
                scores = []

                for l in lines:
                    # Cek apakah baris adalah menit (contoh: 78', 45+2', 1')
                    is_minute = "'" in l or (l.isdigit() and int(l) > 10) # Asumsi skor tidak mungkin > 10
                    
                    # Jika baris adalah angka murni (skor 0-9)
                    if l.isdigit() and len(l) == 1:
                        scores.append(l)
                    # Jika bukan angka skor, bukan menit, dan bukan sampah
                    elif not is_minute and not any(t in l.upper() for t in trash) and len(l) > 2:
                        clean_lines.append(l)

                # 3. Penentuan Nama Tim, Liga, dan Skor yang Presisi
                if len(clean_lines) >= 3:
                    # Struktur: [Nama Liga, Tim Home, Tim Away]
                    liga = clean_lines[0]
                    home_n = clean_lines[1]
                    away_n = clean_lines[2]
                elif len(clean_lines) == 2:
                    # Jika liga tidak terdeteksi, anggap baris 1 & 2 adalah tim
                    liga = "International Match"
                    home_n = clean_lines[0]
                    away_n = clean_lines[1]
                else:
                    continue 

                # Ambil skor dari list yang sudah dikumpulkan
                score_h = scores[0] if len(scores) > 0 else "0"
                score_a = scores[1] if len(scores) > 1 else "0"

                match_name = f"{home_n} vs {away_n}"

                # 4. Susun Data Final
                data = {
                    "id": len(hasil_akhir) + 1,
                    "liga": liga,
                    "jadwal": "LIVE NOW",
                    "home": {
                        "nama": home_n, 
                        "score": score_h,
                        "logo": item['imgs'][0] if item['imgs'] else ""
                    },
                    "away": {
                        "nama": away_n, 
                        "score": score_away if 'score_away' in locals() else score_a, # Safety check
                        "logo": item['imgs'][1] if len(item['imgs']) > 1 else ""
                    },
                    "link_halaman": item['url'],
                    "stream_url": ""
                }

                # 5. Ekstraksi m3u8
                data['stream_url'] = get_live_stream_link(driver, item['url'], match_name)
                
                hasil_akhir.append(data)
                print(f"   [√] BERHASIL: {home_n} ({score_h}) - ({score_a}) {away_n} [{liga}]")
                print(f"   {'-'*30}")

            except Exception as e:
                print(f"   [!] Gagal memproses item: {e}")
                continue

    except Exception as e:
        print(f"\n[!] ERROR UTAMA: {e}")
    finally:
        driver.quit()

    # 5. Simpan Hasil (Pastikan variabel hasil_akhir tidak kosong)
    if hasil_akhir:
        os.makedirs(os.path.dirname(FILE_OUTPUT), exist_ok=True)
        with open(FILE_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(hasil_akhir, f, indent=4, ensure_ascii=False)
        print(f"\n[SUKSES] {len(hasil_akhir)} data berhasil disimpan di {FILE_OUTPUT}")
    else:
        print("\n[!] Selesai, tapi hasil_akhir kosong. Cek filter trash Anda.")
 

if __name__ == "__main__":

    jalankan_scraper()

