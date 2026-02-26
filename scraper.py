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

# --- 1. KONFIGURASI & ENVIRONMENT ---
FIREBASE_URL = os.getenv("FIREBASE_URL")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET")
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"
FIXED_CATEGORY_ID = "EVENT1"

# Setup Timezone Jakarta (WIB)
tz_jkt = timezone(timedelta(hours=7))

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

# --- 2. FUNGSI PEMBANTU (HELPERS) ---

def get_chrome_main_version():
    """Mendeteksi versi Chrome yang terinstal di sistem GitHub Runner."""
    try:
        output = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
        version = re.search(r'Chrome (\d+)', output).group(1)
        logging.info(f"Sistem menggunakan Google Chrome versi: {version}")
        return int(version)
    except Exception as e:
        logging.warning(f"Gagal deteksi versi Chrome: {e}. Menggunakan mode auto.")
        return None

def get_detailed_info(driver, match_page_url):
    """Mengambil jam tayang dari judul halaman detail."""
    try:
        driver.set_page_load_timeout(25)
        try:
            driver.get(match_page_url)
        except:
            driver.execute_script("window.stop();")
        
        time.sleep(3)
        page_title = driver.title 
        # Mencari format HH:mm dan DD/MM
        match = re.search(r'(\d{2}:\d{2}).*?(\d{2}/\d{2})', page_title)
        
        if match:
            jam, tgl_bln = match.group(1), match.group(2)
            current_year = datetime.now(tz_jkt).year
            dt_obj = datetime.strptime(f"{tgl_bln}/{current_year} {jam}", "%d/%m/%Y %H:%M")
            dt_obj = dt_obj.replace(tzinfo=tz_jkt)
            return int(dt_obj.timestamp() * 1000), f"{tgl_bln} | {jam}"
    except:
        pass
    return int(time.time() * 1000), "LIVE"

def get_live_stream_link(driver):
    """Mencari link m3u8 dari trafik network browser."""
    stream_url = "Not Found"
    try:
        # Menunggu buffer network
        time.sleep(10) 
        logs = driver.get_log('performance')
        for entry in logs:
            msg = entry.get('message')
            if '.m3u8' in msg:
                url_match = re.search(r'"url":"(https://[^"]+\.m3u8[^"]*)"', msg)
                if url_match:
                    found_url = url_match.group(1).replace('\\/', '/')
                    if "ads" not in found_url.lower():
                        stream_url = found_url
                        break
    except:
        pass
    return stream_url

# --- 3. CORE SCRAPER ---

def jalankan_scraper():
    logging.info("=== MEMULAI AUTO SCRAPER ===")
    
    chrome_version = get_chrome_main_version()
    
    options = uc.ChromeOptions()
    options.add_argument('--headless') # Wajib di GitHub Actions
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    driver = None
    try:
        driver = uc.Chrome(options=options, version_main=chrome_version)
    except Exception as e:
        logging.critical(f"CRITICAL: Driver gagal dimuat: {e}")
        return

    hasil_scraped = []

    try:
        logging.info(f"Membuka target: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(8)

        # Mencari semua link pertandingan
        cards = driver.find_elements(By.XPATH, "//a[contains(@href, 'truc-tiep')]")
        raw_data = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and url not in seen_urls and len(teks) > 10:
                imgs = [img.get_attribute("src") for img in card.find_elements(By.TAG_NAME, "img")]
                raw_data.append({"teks": teks, "url": url, "imgs": imgs})
                seen_urls.add(url)

        logging.info(f"Ditemukan {len(raw_data)} potensi pertandingan.")

        for item in raw_data:
            try:
                # Parsing Teks (Nama Tim & Liga)
                lines = [l.strip() for l in item['teks'].split('\n') if l.strip()]
                clean_lines = []
                for l in lines:
                    # Abaikan angka skor tunggal atau jam menit di baris teks
                    if not re.match(r'^\d{2}:\d{2}$', l) and not (l.isdigit() and len(l) == 1):
                        if len(l) > 1: clean_lines.append(l)

                if len(clean_lines) >= 3:
                    liga, t1, t2 = clean_lines[0], clean_lines[1], clean_lines[2]
                elif len(clean_lines) == 2:
                    liga, t1, t2 = "Football Match", clean_lines[0], clean_lines[1]
                else:
                    continue

                # Ambil Logo
                img_list = item.get('imgs', [])
                l_t1 = img_list[1] if len(img_list) >= 3 else img_list[0] if len(img_list) >= 1 else ""
                l_t2 = img_list[2] if len(img_list) >= 3 else img_list[1] if len(img_list) >= 2 else ""

                logging.info(f"Proses: {t1} vs {t2}")
                
                # Masuk ke halaman detail
                start_ms, ts_display = get_detailed_info(driver, item['url'])
                stream_url = get_live_stream_link(driver)

                # Masukkan ke list sesuai format permintaan
                hasil_scraped.append({
                    "channelName": f"{t1} vs {t2}",
                    "categoryName": liga,
                    "team1Name": t1,
                    "team2Name": t2,
                    "team1Logo": l_t1,
                    "team2Logo": l_t2,
                    "streamUrl": stream_url,
                    "startTime": start_ms,
                    "status": "LIVE",
                    "description": ts_display
                })

            except Exception as e:
                logging.error(f"Gagal memproses satu item: {e}")
                continue

    finally:
        if driver:
            driver.quit()

    # --- 4. KIRIM KE FIREBASE ---
    if hasil_scraped:
        endpoint = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        payload = {
            "category_name": "LIVE FOOTBALL", 
            "order": 1, 
            "channels": {uuid.uuid4().hex[:8]: x for x in hasil_scraped}
        }
        
        try:
            resp = requests.put(endpoint, json=payload, timeout=30)
            if resp.status_code == 200:
                logging.info(f"BERHASIL! {len(hasil_scraped)} data terupdate di Firebase.")
            else:
                logging.error(f"Firebase Error: {resp.text}")
        except Exception as e:
            logging.error(f"Gagal koneksi Firebase: {e}")
    else:
        logging.warning("Tidak ada data yang berhasil di-scrape.")

if __name__ == "__main__":
    jalankan_scraper()
