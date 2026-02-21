import os
import requests
import time
import re
import uuid
from datetime import datetime, timezone, timedelta
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==============================
# KONFIGURASI
# ==============================
FIREBASE_URL = os.getenv("FIREBASE_URL")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET")
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"
FIXED_CATEGORY_ID = "EVENT1" 
tz_jkt = timezone(timedelta(hours=7))

LEAGUE_LOGO_MAP = {
    "International Match": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
    "Club Friendly": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
}

# ==============================
# UTIL AMBIL SRC IMAGE
# ==============================
def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""

# ==============================
# AMBIL STREAM + LOGO LIGA (HANYA UNTUK LIVE)
# ==============================
def get_stream_and_league_logo(driver, match_url, liga):
    league_logo = ""
    stream_url = "Not Found"
    try:
        driver.get(match_url)
        time.sleep(7)

        # Bersihkan Iklan
        driver.execute_script("document.querySelectorAll('.modal,.popup,.fixed,[id*=ads]').forEach(e=>e.remove());")

        # Scrape Logo Liga
        logos = driver.find_elements(By.TAG_NAME, "img")
        for img in logos:
            alt = (img.get_attribute("alt") or "").lower()
            src = get_img_src(img)
            if liga.lower() in alt and src:
                league_logo = src
                break
        
        if not league_logo:
            league_logo = LEAGUE_LOGO_MAP.get(liga, "https://cdn-icons-png.flaticon.com/512/53/53283.png")

        # Capture m3u8 via Performance Logs
        logs = driver.get_log("performance")
        for entry in logs:
            msg = entry.get("message", "")
            if ".m3u8" in msg:
                m = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', msg)
                if m: 
                    stream_url = m.group(0).replace("\\/", "/")
                    break
    except: pass
    return stream_url, league_logo

# ==============================
# FIREBASE INTEGRATION
# ==============================
def kirim_ke_firebase(data):
    if not FIREBASE_URL or not FIREBASE_SECRET:
        print("[!] FIREBASE CONFIG MISSING")
        return

    now = int(time.time() * 1000)
    category_key = "-EVENT_" + str(now)
    payload = {
        category_key: {
            "category_name": "EVENT1",
            "order": 15,
            "channels": {uuid.uuid4().hex: item for item in data}
        }
    }

    url = f"{FIREBASE_URL}/playlist.json?auth={FIREBASE_SECRET}"
    res = requests.patch(url, json=payload, timeout=20)
    if res.status_code == 200:
        print(f"[√] BERHASIL! {len(data)} match terdaftar di Firebase.")

# ==============================
# SCRAPER UTAMA (HYBRID LOGIC)
# ==============================
def jalankan_scraper():
    print(f"===== START HYBRID SCRAPER: {TARGET_URL} =====")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        time.sleep(10)

        # Scroll untuk memicu Lazy Load
        for _ in range(12):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        match_list = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and url not in seen_urls and len(teks) > 10:
                imgs = [get_img_src(img) for img in card.find_elements(By.TAG_NAME, "img")]
                match_list.append({"url": url, "text": teks, "imgs": imgs})
                seen_urls.add(url)

        print(f"Ditemukan {len(match_list)} match. Memproses...")

        for item in match_list:
            try:
                # 1. Parsing Baris & Bersihkan Menit/Skor
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                clean_lines = []
                for l in lines:
                    if re.match(r"^\d+('\+?\d*)?$", l): continue # Skip Menit
                    if l.isdigit() and len(l) <= 2: continue # Skip Skor
                    clean_lines.append(l)

                if len(clean_lines) < 3: continue
                liga, home, away = clean_lines[0], clean_lines[1], clean_lines[2]
                
                # 2. Ambil Jam & Logo Default dari Card
                is_live = "Live" in item["text"]
                t1_logo = item["imgs"][0] if len(item["imgs"]) > 0 else ""
                t2_logo = item["imgs"][1] if len(item["imgs"]) > 1 else ""
                
                jam_match = re.search(r"(\d{2}:\d{2})\s+(\d{2}/\d{2})", item["text"])
                start_ts = int(datetime.strptime(f"{jam_match.group(1)} {jam_match.group(2)}/2026", "%H:%M %d/%m/%Y").replace(tzinfo=tz_jkt).timestamp() * 1000) if jam_match else int(time.time() * 1000)

                # 3. LOGIKA HYBRID
                stream_url, l_logo = "Not Found", ""
                status = "upcoming"

                if is_live:
                    # BUKA DETAIL HANYA JIKA LIVE
                    stream_url, l_logo = get_stream_and_league_logo(driver, item["url"], liga)
                    status = "live" if stream_url != "Not Found" else "upcoming"
                    driver.get(TARGET_URL) # Kembali ke menu utama
                    time.sleep(3)
                else:
                    # JIKA UPCOMING: Ambil data instan tanpa klik
                    l_logo = LEAGUE_LOGO_MAP.get(liga, "https://cdn-icons-png.flaticon.com/512/53/53283.png")

                hasil.append({
                    "channelName": f"[{liga}] {home} vs {away}",
                    "leagueName": liga,
                    "leagueLogo": l_logo,
                    "team1Name": home, "team1Logo": t1_logo,
                    "team2Name": away, "team2Logo": t2_logo,
                    "status": status,
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "streamUrl": stream_url,
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/",
                    "contentType": "event_pertandingan"
                })
                print(f"   [{status.upper()}] {home} vs {away}")

            except: continue
    finally:
        driver.quit()

    if hasil: kirim_ke_firebase(hasil)

if __name__ == "__main__":
    jalankan_scraper()
