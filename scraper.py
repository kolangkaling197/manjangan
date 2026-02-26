import os
import json
import time
import re
import uuid
import logging
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta, timezone

# --- KONFIGURASI ---
FIREBASE_URL = os.getenv("FIREBASE_URL")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET")
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"
FIXED_CATEGORY_ID = "EVENT1"

# Setup Timezone Jakarta
tz_jkt = timezone(timedelta(hours=7))

# --- SETUP LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def get_detailed_info(driver, match_page_url):
    try:
        driver.set_page_load_timeout(35)
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
            # Set timezone ke objek datetime
            dt_obj = dt_obj.replace(tzinfo=tz_jkt)
            return int(dt_obj.timestamp() * 1000), f"{tgl_bln} | {jam}"
    except: pass
    return int(time.time() * 1000), "LIVE"

def get_live_stream_link(driver):
    stream_url = "Not Found"
    try:
        time.sleep(12) 
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
    except: pass
    return stream_url

def jalankan_scraper():
    logging.info("=== START SCRAPER (REST API MODE) ===")

    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.page_load_strategy = 'eager'
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        logging.critical(f"Gagal Driver: {e}")
        return

    hasil = []

    try:
        driver.get(TARGET_URL)
        logging.info("Membuka Halaman Utama...")
        time.sleep(10)

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

        for item in temp_list:
            try:
                lines = [l.strip() for l in item['teks'].split('\n') if l.strip()]
                clean_lines = []
                for l in lines:
                    is_time_score = re.match(r'^\d{2}:\d{2}$', l) or (l.isdigit() and len(l) == 1) or "'" in l or "+" in l
                    if not is_time_score and len(l) > 1:
                        clean_lines.append(l)

                if len(clean_lines) >= 3:
                    liga, t1, t2 = clean_lines[0], clean_lines[1], clean_lines[2]
                else: continue

                img_list = item.get('imgs', [])
                l_t1, l_t2 = (img_list[1], img_list[2]) if len(img_list) >= 3 else (img_list[0], img_list[1]) if len(img_list) == 2 else ("", "")

                start_ms, ts_display = get_detailed_info(driver, item['url'])
                stream_url = get_live_stream_link(driver)

                hasil.append({
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
                logging.info(f"[√] Captured: {t1} vs {t2}")

            except: continue

    finally:
        driver.quit()

    if hasil:
        # Kirim ke Firebase sesuai format yang diminta
        fb_url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        payload = {
            "category_name": "EVENT15", 
            "order": 1, 
            "channels": {uuid.uuid4().hex: x for x in hasil}
        }
        
        try:
            response = requests.put(fb_url, json=payload, timeout=30)
            if response.status_code == 200:
                print(f"[√] SELESAI! {len(hasil)} match diproses dan dikirim.")
            else:
                print(f"[X] Gagal kirim ke Firebase: {response.text}")
        except Exception as e:
            print(f"[X] Error Request: {e}")

if __name__ == "__main__":
    jalankan_scraper()
