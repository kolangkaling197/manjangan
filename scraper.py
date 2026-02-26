import os
import json
import time
import re
import uuid
import logging
import requests
import subprocess
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta, timezone

# --- 1. KONFIGURASI ---
FIREBASE_URL = os.getenv("FIREBASE_URL")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET")
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"
FIXED_CATEGORY_ID = "EVENT1" 
tz_jkt = timezone(timedelta(hours=7))

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- 2. FUNGSI PEMBANTU ---

def get_chrome_main_version():
    """Mendeteksi versi Chrome di runner GitHub agar tidak mismatch."""
    try:
        output = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
        version = re.search(r'Chrome (\d+)', output).group(1)
        return int(version)
    except:
        return None

def get_detailed_info(driver, match_page_url):
    """Logika pengambilan startTime dari Title halaman detail (Script Awal)."""
    try:
        driver.set_page_load_timeout(30)
        try:
            driver.get(match_page_url)
        except:
            driver.execute_script("window.stop();")
        
        time.sleep(4)
        page_title = driver.title 
        match = re.search(r'(\d{2}:\d{2}).*?(\d{2}/\d{2})', page_title)
        
        if match:
            jam, tgl_bln = match.group(1), match.group(2)
            current_year = datetime.now(tz_jkt).year
            dt_obj = datetime.strptime(f"{tgl_bln}/{current_year} {jam}", "%d/%m/%Y %H:%M")
            dt_obj = dt_obj.replace(tzinfo=tz_jkt)
            start_ms = int(dt_obj.timestamp() * 1000)
            
            # Format display hari (Script Awal)
            hari_id = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
            ts_display = f"{hari_id[dt_obj.weekday()]}, {tgl_bln} | {jam}"
            return start_ms, ts_display
    except: pass
    return int(time.time() * 1000), "LIVE"

def get_live_stream_link(driver):
    """Logika pencarian m3u8 yang dioptimasi untuk GitHub Actions."""
    stream_url = "Not Found"
    try:
        # 1. Simulasi Interaksi: Scroll agar player terpicu (Lazy Load)
        driver.execute_script("window.scrollTo(0, 400);")
        time.sleep(2)
        
        # 2. Hapus Overlay Iklan yang mungkin menghalangi player di mode headless
        driver.execute_script("""
            document.querySelectorAll('.modal, .popup, .sh-overlay, [class*="ads"]').forEach(el => el.remove());
        """)

        # 3. Tunggu lebih lama (GitHub network lebih lambat merespon stream)
        logging.info("    [NETWORK] Menunggu trafik stream (20 detik)...")
        time.sleep(20) 

        # 4. Ambil logs performance
        logs = driver.get_log('performance')
        for entry in logs:
            msg = entry.get('message')
            if '.m3u8' in msg:
                # Regex diperkuat untuk menangkap URL m3u8 yang bersih
                url_match = re.search(r'"url":"(https://[^"]+\.m3u8[^"]*)"', msg)
                if url_match:
                    found_url = url_match.group(1).replace('\\/', '/')
                    # Filter link iklan/ads
                    if "ads" not in found_url.lower() and "telemetry" not in found_url.lower():
                        logging.info("    [STREAM] Berhasil ditangkap!")
                        stream_url = found_url
                        break
    except Exception as e:
        logging.error(f"    [ERROR] Gagal menangkap stream: {e}")
    return stream_url
    
def jalankan_scraper():
    logging.info("=== MEMULAI AUTO SCRAPER (VERSION 2026) ===")
    
    # Ambil versi chrome secara dinamis
    chrome_ver = get_chrome_main_version()

    # 1. DEFINISIKAN variabel options
    options = uc.ChromeOptions() 
    
    # 2. Tambahkan argumen (Headless & Penyamaran)
    options.add_argument('--headless') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    # Aktifkan logging network untuk menangkap m3u8
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    # 3. Inisialisasi Driver
    driver = None
    try:
        driver = uc.Chrome(options=options, version_main=chrome_ver)
    except Exception as e:
        logging.critical(f"Gagal memuat driver Chrome: {e}")
        return

    hasil = []

    try:
        logging.info(f"Membuka Target: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(10) # Tunggu halaman utama render sempurna

        # ... (lanjutkan dengan logika pencarian card pertandingan kamu)
        cards = driver.find_elements(By.XPATH, "//a[contains(@href, 'truc-tiep')]")
        temp_list = []
        seen_urls = set()

        # Ambil data kasar
        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and url not in seen_urls and len(teks) > 10:
                imgs = [img.get_attribute("src") for img in card.find_elements(By.TAG_NAME, "img")]
                temp_list.append({"teks": teks, "url": url, "imgs": imgs})
                seen_urls.add(url)

        logging.info(f"Ditemukan {len(temp_list)} card pertandingan.")

        for item in temp_list:
            try:
                # --- LOGIKA PEMBERSIHAN (DARI SCRIPT AWAL ANDA) ---
                lines = [l.strip() for l in item['teks'].split('\n') if l.strip()]
                trash = ["CƯỢC", "XEM", "LIVE", "TRỰC", "TỶ LỆ", "KÈO", "CLICK", "VS", "-", "PHT", "HT", "FT"]
                
                clean_lines, scores = [], []
                for l in lines:
                    # Deteksi waktu/skor: HH:MM, angka tunggal, menit ('), atau HT/FT
                    is_time_score = re.match(r'^\d{2}:\d{2}$', l) or (l.isdigit() and len(l) == 1) or \
                                   "'" in l or "+" in l or l.upper() in ["HT", "FT"]
                    
                    if l.isdigit() and len(l) == 1:
                        scores.append(l)
                    elif not is_time_score and not any(tk == l.upper() for tk in trash) and len(l) > 1:
                        clean_lines.append(l)

                # Penentuan Liga dan Tim
                if len(clean_lines) >= 3:
                    liga, t1, t2 = clean_lines[0], clean_lines[1], clean_lines[2]
                elif len(clean_lines) == 2:
                    liga, t1, t2 = "International Match", clean_lines[0], clean_lines[1]
                else: continue

                # Logo Mapping (Script Awal)
                img_list = item.get('imgs', [])
                l_liga, l_t1, l_t2 = (img_list[0], img_list[1], img_list[2]) if len(img_list) >= 3 else \
                                     ("", img_list[0], img_list[1]) if len(img_list) == 2 else ("", "", "")

                logging.info(f"Proses: {t1} vs {t2}")

                # Ambil detail (m3u8 & time)
                start_ms, ts_display = get_detailed_info(driver, item['url'])
                stream_url = get_live_stream_link(driver)

                durasi_ms = 2 * 60 * 60 * 1000 
                end_ms = start_ms + durasi_ms

                # Format Objek (Channel.java Compatible)
                hasil.append({
                    "channelName": f"{t1} vs {t2}",
                    "ligaName": liga,
                    "team1Name": t1,
                    "team2Name": t2,
                    "team1Logo": l_t1,
                    "team2Logo": l_t2,
                    "logoligaUrl": l_liga,
                    "streamUrl": stream_url,
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "status": "LIVE",
                    "contentType": "event_pertandingan",
                    "description": ts_display
                })

            except: continue

    finally:
        driver.quit()

    # --- 4. PENGIRIMAN KE FIREBASE (SESUAI PERMINTAAN) ---
    if hasil:
        fb_url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        
        # Payload dengan UUID unik untuk tiap channel
        payload = {
            "category_name": "EVENT15", 
            "order": 1, 
            "channels": {uuid.uuid4().hex: x for x in hasil}
        }
        
        try:
            r = requests.put(fb_url, json=payload, timeout=30)
            if r.status_code == 200:
                print(f"[√] SELESAI! {len(hasil)} match diproses.")
            else:
                print(f"[X] Firebase Error: {r.text}")
        except Exception as e:
            print(f"[X] Gagal mengirim data: {e}")

if __name__ == "__main__":
    jalankan_scraper()



