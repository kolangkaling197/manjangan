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
FIXED_CATEGORY_ID = "AJ_JKS" 
tz_jkt = timezone(timedelta(hours=7))

# Setup Logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# --- 2. FUNGSI STEALTH & PEMBANTU ---

def get_chrome_main_version():
    try:
        output = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
        version = re.search(r'Chrome (\d+)', output).group(1)
        return int(version)
    except:
        return None

def human_delay(min_s=2, max_s=5):
    """Jeda acak untuk meniru perilaku manusia."""
    time.sleep(random.uniform(min_s, max_s))

def human_scroll(driver):
    """Scroll halaman secara bertahap, bukan instan."""
    total_height = int(driver.execute_script("return document.body.scrollHeight"))
    for i in range(1, total_height, random.randint(400, 700)):
        driver.execute_script(f"window.scrollTo(0, {i});")
        time.sleep(random.uniform(0.3, 0.7))

def get_detailed_info(driver, match_page_url):
    try:
        human_delay(3, 6) # Jeda sebelum klik/buka detail
        driver.get(match_page_url)
        human_scroll(driver) # Simulasi membaca konten
        
        time.sleep(4)
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
            logging.info(f"    [ATTEMPT {attempt}] Mencari link m3u8...")
            driver.switch_to.default_content()
            
            # Simulasi gerakan mouse ke area video
            try:
                action = ActionChains(driver)
                video_area = driver.find_element(By.TAG_NAME, "body")
                action.move_to_element_with_offset(video_area, random.randint(100,200), random.randint(100,200)).perform()
            except: pass

            time.sleep(20) # Tunggu traffic network
            logs = driver.get_log('performance')

            for entry in logs:
                msg = entry.get('message')
                if '.m3u8' in msg:
                    url_match = re.search(r'"url":"(https://[^"]+\.m3u8[^"]*)"', msg)
                    if url_match:
                        found_url = url_match.group(1).replace('\\/', '/')
                        if "ads" not in found_url.lower():
                            logging.info(f"    [SUCCESS] m3u8 ditemukan!")
                            return found_url

            if attempt < max_retries:
                driver.refresh()
                human_delay(5, 8)
        except Exception as e:
            logging.error(f"    [ERROR] Gagal di attempt {attempt}: {e}")
            driver.refresh()

    return "Not Found"

# --- 3. JALANKAN SCRAPER ---

def jalankan_scraper():
    logging.info("=== START SCRAPER (STEALTH MODE 2026) ===")
    
    chrome_ver = get_chrome_main_version()
    options = uc.ChromeOptions()
    
    # Gunakan mode headless baru yang lebih sulit dideteksi
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    # Rotasi User Agent ke yang lebih modern
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    driver = None
    try:
        driver = uc.Chrome(options=options, version_main=chrome_ver)
        
        # Inject script untuk sembunyikan jejak bot
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        driver.get(TARGET_URL)
        logging.info("Membuka Halaman Utama...")
        human_delay(10, 15) # Waktu untuk melewati tantangan bot pasif

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
        # Batasi jumlah proses agar IP tidak dicurigai (Scraping bertahap)
        for item in targets[:10]: 
            try:
                lines = [l.strip() for l in item['teks'].split('\n') if l.strip()]
                trash = ["CƯỢC", "XEM", "LIVE", "TRỰC", "TỶ LỆ", "KÈO", "CLICK", "VS", "-", "PHT", "HT", "FT"]
                
                clean_lines = []
                for l in lines:
                    is_time_score = re.match(r'^\d{2}:\d{2}$', l) or (l.isdigit() and len(l) == 1) or \
                                    "'" in l or "+" in l or l.upper() in ["HT", "FT"]
                    if not is_time_score and not any(tk == l.upper() for tk in trash) and len(l) > 1:
                        clean_lines.append(l)

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
                stream_url = get_live_stream_link(driver)

                # --- FORMAT HASIL AKHIR SESUAI PERMINTAAN ---
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
                
                # Istirahat antar item agar tidak terdeteksi flooding
                human_delay(4, 8)

            except Exception as e:
                logging.warning(f"Gagal memproses item: {e}")

    finally:
        if driver: driver.quit()

    # --- 4. KIRIM KE FIREBASE ---
    if hasil_akhir:
        fb_url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        payload = {
            "category_name": "EVENT LIVE", 
            "order": 1, 
            "channels": {uuid.uuid4().hex: x for x in hasil_akhir}
        }
        try:
            r = requests.put(fb_url, json=payload, timeout=30)
            if r.status_code == 200:
                print(f"[√] SELESAI! {len(hasil_akhir)} match diproses.")
            else:
                print(f"[X] Firebase Error: {r.text}")
        except Exception as e:
            print(f"[X] Gagal mengirim data: {e}")

if __name__ == "__main__":
    jalankan_scraper()
