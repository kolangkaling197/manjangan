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
TARGET_URL = "https://bunchatv.net/truc-tiep"
FIXED_CATEGORY_ID = "AJ_JKS" 
tz_jkt = timezone(timedelta(hours=7))

# Setup Logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(message)s'
)

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
    """Mengambil startTime dari Title halaman detail."""
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
            dt_obj = datetime.strptime(f"{tgl_bln}/{current_year} {jam}", "%d/%m/%Y %H:%M").replace(tzinfo=tz_jkt)
            start_ms = int(dt_obj.timestamp() * 1000)
            
            hari_id = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
            ts_display = f"{hari_id[dt_obj.weekday()]}, {tgl_bln} | {jam}"
            return start_ms, ts_display
    except: pass
    return int(time.time() * 1000), "LIVE"

def get_live_stream_link(driver):
    """Mencari link m3u8 dengan dukungan Iframe Switching (Logika VS Code)."""
    stream_url = "Not Found"
    try:
        # 1. Bersihkan Overlay
        driver.execute_script("document.querySelectorAll('.modal, .popup, .sh-overlay, [class*=\"ads\"]').forEach(el => el.remove());")

        # 2. Berpindah ke iframe player (Penting agar trafik m3u8 terpicu)
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in iframes:
            src = frame.get_attribute("src") or ""
            if any(x in src for x in ["bitmovin", "player", "stream", "embed", "cdn"]):
                driver.switch_to.frame(frame)
                logging.info("    [INFO] Berhasil switch ke iframe player.")
                break

        logging.info("    [NETWORK] Menunggu trafik m3u8 (20 detik)...")
        time.sleep(20) 

        # 3. Kembali ke konten utama sebelum mengambil log performance
        driver.switch_to.default_content()
        logs = driver.get_log('performance')

        for entry in logs:
            msg = entry.get('message')
            if '.m3u8' in msg:
                url_match = re.search(r'"url":"(https://[^"]+\.m3u8[^"]*)"', msg)
                if url_match:
                    found_url = url_match.group(1).replace('\\/', '/')
                    if "ads" not in found_url.lower():
                        logging.info("    [STREAM] Captured!")
                        return found_url
    except Exception as e:
        logging.error(f"    [ERROR] Stream link: {e}")
    return stream_url

def jalankan_scraper():
    logging.info("=== START SCRAPER (HYBRID VERSION 2026) ===")
    
    chrome_ver = get_chrome_main_version()
    options = uc.ChromeOptions()
    options.page_load_strategy = 'eager'
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1366,768')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    driver = None
    try:
        driver = uc.Chrome(options=options, version_main=chrome_ver)
    except Exception as e:
        logging.critical(f"Gagal memuat Chrome Driver: {e}")
        return

    hasil_akhir = []
    try:
        driver.get(TARGET_URL)
        logging.info("Membuka Halaman Utama...")
        time.sleep(10)

        # Ambil data kasar semua pertandingan
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

        for item in targets:
            try:
                # Parsing Teks (Tim & Liga)
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

                # Ambil Logo
                img_list = item.get('imgs', [])
                l_liga, l_t1, l_t2 = (img_list[0], img_list[1], img_list[2]) if len(img_list) >= 3 else \
                                     ("", img_list[0], img_list[1]) if len(img_list) == 2 else ("", "", "")

                logging.info(f"Proses: {t1} vs {t2}")

                # Masuk Detail
                start_ms, ts_display = get_detailed_info(driver, item['url'])
                stream_url = get_live_stream_link(driver)

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
            except Exception as e:
                logging.warning(f"Gagal memproses item: {e}")

    finally:
        if driver: driver.quit()

    # 3. KIRIM KE FIREBASE
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
