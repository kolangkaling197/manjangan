import os
import json
import time
import re
import uuid
import logging
import requests
import subprocess
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta, timezone
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# --- 1. KONFIGURASI ---
FIREBASE_URL = os.getenv("FIREBASE_URL")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET")
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"
# URL Cadangan dari GitHub jika m3u8 tidak terdeteksi di browser
FALLBACK_M3U_URL = "https://raw.githubusercontent.com/t23-02/bongda/refs/heads/main/bongda.m3u"
FIXED_CATEGORY_ID = "AJ_JKS" 
tz_jkt = timezone(timedelta(hours=7))

# Setup Logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# --- 2. FUNGSI STEALTH & FALLBACK ---

def get_chrome_main_version():
    try:
        output = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
        version = re.search(r'Chrome (\d+)', output).group(1)
        return int(version)
    except:
        return None

def get_fallback_streams():
    """Mengambil database stream cadangan dari GitHub M3U."""
    streams = {}
    try:
        response = requests.get(FALLBACK_M3U_URL, timeout=15)
        if response.status_code == 200:
            content = response.text
            # Ekstrak Nama dan URL m3u8
            matches = re.findall(r'#EXTINF:.*?,(.*?)\n(http.*)', content)
            for name, url in matches:
                streams[name.lower().strip()] = url.strip()
            logging.info(f"Berhasil memuat {len(streams)} link cadangan dari GitHub.")
    except Exception as e:
        logging.error(f"Gagal mengambil fallback: {e}")
    return streams

def find_best_link(t1, t2, raw_url, fallback_db):
    """Logika pemilihan link: Browser -> Fallback GitHub -> Not Found."""
    if raw_url != "Not Found" and len(raw_url) > 10:
        return raw_url
    
    # Cari kecocokan nama tim di database GitHub
    search_key_1 = t1.lower()
    search_key_2 = t2.lower()
    for name_in_db, url_in_db in fallback_db.items():
        if search_key_1 in name_in_db or search_key_2 in name_in_db:
            logging.info(f"    [FALLBACK] Link ditemukan di GitHub untuk {t1} vs {t2}")
            return url_in_db
    return "Not Found"

def human_delay(min_s=3, max_s=7):
    """Meniru jeda waktu manusia."""
    time.sleep(random.uniform(min_s, max_s))

# --- 3. FUNGSI SCRAPER ---

def get_detailed_info(driver, match_page_url):
    try:
        driver.get(match_page_url)
        human_delay(4, 6)
        page_title = driver.title 
        match = re.search(r'(\d{2}:\d{2}).*?(\d{2}/\d{2})', page_title)
        
        if match:
            jam, tgl_bln = match.group(1), match.group(2)
            current_year = datetime.now(tz_jkt).year
            dt_obj = datetime.strptime(f"{tgl_bln}/{current_year} {jam}", "%d/%m/%Y %H:%M").replace(tzinfo=tz_jkt)
            start_ms = int(dt_obj.timestamp() * 1000)
            hari_id = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
            ts_display = f"{hari_id[dt_obj.weekday()]}, {tgl_bln} | {jam}"
            return start_ms, ts_display
    except: pass
    return int(time.time() * 1000), "LIVE"

def get_live_stream_link(driver):
    max_retries = 2
    for attempt in range(1, max_retries + 1):
        try:
            driver.switch_to.default_content()
            # Simulasi pergerakan mouse sebelum menunggu traffic
            action = ActionChains(driver)
            action.move_by_offset(random.randint(0, 100), random.randint(0, 100)).perform()
            
            time.sleep(15) 
            logs = driver.get_log('performance')
            for entry in logs:
                msg = entry.get('message')
                if '.m3u8' in msg:
                    url_match = re.search(r'"url":"(https://[^"]+\.m3u8[^"]*)"', msg)
                    if url_match:
                        found_url = url_match.group(1).replace('\\/', '/')
                        if "ads" not in found_url.lower():
                            return found_url
            driver.refresh()
            human_delay(5, 8)
        except: pass
    return "Not Found"

def jalankan_scraper():
    logging.info("=== START STEALTH SCRAPER (HYBRID 2026) ===")
    fallback_db = get_fallback_streams()
    
    chrome_ver = get_chrome_main_version()
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    driver = None
    try:
        driver = uc.Chrome(options=options, version_main=chrome_ver)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        driver.get(TARGET_URL)
        logging.info("Membuka Halaman Utama...")
        human_delay(10, 15)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href, 'truc-tiep')]")
        targets = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and url not in seen_urls and len(teks) > 10:
                imgs = [img.get_attribute("src") for img in card.find_elements(By.TAG_NAME, "img")]
                targets.append({"teks": teks, "url": url, "imgs": imgs})
                seen_urls.add(url)

        logging.info(f"Ditemukan {len(targets)} pertandingan.")

        hasil_akhir = []
        for item in targets[:12]: # Limit 12 per run agar tidak dicurigai
            try:
                lines = [l.strip() for l in item['teks'].split('\n') if l.strip()]
                trash = ["CƯỢC", "XEM", "LIVE", "TRỰC", "TỶ LỆ", "KÈO", "CLICK", "VS", "-", "PHT", "HT", "FT"]
                clean_lines = [l for l in lines if not any(tk == l.upper() for tk in trash) and len(l) > 1]

                if len(clean_lines) >= 3:
                    liga, t1, t2 = clean_lines[0], clean_lines[1], clean_lines[2]
                elif len(clean_lines) == 2:
                    liga, t1, t2 = "International Match", clean_lines[0], clean_lines[1]
                else: continue

                img_list = item.get('imgs', [])
                l_liga, l_t1, l_t2 = (img_list[0], img_list[1], img_list[2]) if len(img_list) >= 3 else \
                                     ("", img_list[0], img_list[1]) if len(img_list) == 2 else ("", "", "")

                logging.info(f"Proses: {t1} vs {t2}")

                start_ms, ts_display = get_detailed_info(driver, item['url'])
                raw_url = get_live_stream_link(driver)
                
                # Gunakan Fallback GitHub jika browser gagal
                stream_url = find_best_link(t1, t2, raw_url, fallback_db)

                hasil_akhir.append({
                    "channelName": f"{t1} vs {t2}",
                    "ligaName": liga,
                    "team1Name": t1, "team2Name": t2,
                    "team1Logo": l_t1, "team2Logo": l_t2, "logoligaUrl": l_liga,
                    "streamUrl": stream_url,
                    "startTime": start_ms, "endTime": start_ms + 7200000,
                    "status": "LIVE", "contentType": "event_pertandingan",
                    "description": ts_display
                })
                human_delay(5, 10)
            except Exception as e:
                logging.warning(f"Gagal memproses item: {e}")

    finally:
        if driver: driver.quit()

    if hasil_akhir:
        fb_url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        payload = {
            "category_name": "EVENT LIVE", "order": 1, 
            "channels": {uuid.uuid4().hex: x for x in hasil_akhir}
        }
        try:
            r = requests.put(fb_url, json=payload, timeout=30)
            if r.status_code == 200: print(f"[√] SELESAI! {len(hasil_akhir)} match diproses.")
        except Exception as e: print(f"[X] Gagal mengirim data: {e}")

if __name__ == "__main__":
    jalankan_scraper()
