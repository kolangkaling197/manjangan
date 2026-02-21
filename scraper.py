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
# Link utama sesuai permintaan Anda
TARGET_URL = "https://bunchatv.net/"
FIXED_CATEGORY_ID = "EVENT1" 

# Paksa zona waktu ke WIB (GMT+7)
tz_jkt = timezone(timedelta(hours=7))

# Filter Liga Kasta Tinggi
HIGH_LEAGUE_KEYWORDS = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1", 
    "Liga Indonesia", "BRI Liga 1", "Saudi Pro League", "Champions League",
    "Europa League", "World Cup", "AFC Champions League", "Eredivisie", "EFL Cup"
]

def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""

def filter_liga(nama_liga):
    """Memastikan hanya liga besar yang masuk ke Firebase"""
    return any(k.lower() in nama_liga.lower() for k in HIGH_LEAGUE_KEYWORDS)

def get_stream_details(driver, url):
    """Masuk ke detail untuk ambil link m3u8 dan jam presisi"""
    stream_url = "Not Found"
    league_logo = ""
    try:
        driver.get(url)
        time.sleep(5)
        
        # Ambil Logo Liga
        logos = driver.find_elements(By.TAG_NAME, "img")
        for img in logos:
            src = get_img_src(img)
            alt = (img.get_attribute("alt") or "").lower()
            if src and ("logo" in alt or "league" in src):
                league_logo = src
                break

        # Ambil m3u8 dari log performa
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

def jalankan_scraper():
    print(f"\n===== SCRAPING MAIN PAGE: {TARGET_URL} =====\n")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        time.sleep(5)
        
        # Scroll ke bawah agar bagian "Lịch Bình Luận" termuat sepenuhnya
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(3)

        # Cari semua elemen pertandingan (baik Live maupun Schedule)
        # Kita mencari semua tag <a> yang memiliki pola link ke pertandingan
        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        initial_list = []

        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and len(teks) > 10:
                imgs = [get_img_src(i) for i in card.find_elements(By.TAG_NAME, "img")]
                initial_list.append({"url": url, "text": teks, "imgs": imgs})

        # Hapus duplikat URL dari daftar awal
        initial_list = {v['url']: v for v in initial_list}.values()
        print(f"Ditemukan {len(initial_list)} potensi pertandingan. Memproses filter...")

        for item in initial_list:
            try:
                # 1. Cleaning Teks & Filter Liga
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                clean = [l for l in lines if "'" not in l and not re.match(r"^\d+$", l) and ":" not in l]
                
                if len(clean) < 3: continue
                nama_liga = clean[0]

                if not filter_liga(nama_liga): continue

                # 2. Ambil Jam & Stream dari Detail
                stream_url, league_logo = get_stream_details(driver, item["url"])
                page_text = driver.page_source
                time_search = re.search(r"(\d{2}:\d{2}).*?(\d{2}/\d{2})", page_text)
                
                if time_search:
                    dt_str = f"{time_search.group(1)} {time_search.group(2)}/2026"
                    dt_naive = datetime.strptime(dt_str, "%H:%M %d/%m/%Y")
                    dt_aware = dt_naive.replace(tzinfo=tz_jkt) # Fix Offset Jam
                    start_ts = int(dt_aware.timestamp() * 1000)
                else:
                    start_ts = int(datetime.now(tz_jkt).timestamp() * 1000)

                home = re.sub(r"^\d+\s+", "", clean[1])
                away = re.sub(r"^\d+\s+", "", clean[2])

                # 3. Logika Status (Soon/Live)
                now_ts = int(datetime.now(tz_jkt).timestamp() * 1000)
                status = "live" if (start_ts <= now_ts) or (stream_url != "Not Found") else "upcoming"

                hasil.append({
                    "channelName": f"[{nama_liga}] {home} vs {away}",
                    "team1Name": home,
                    "team2Name": away,
                    "team1Logo": item["imgs"][0] if len(item["imgs"]) > 0 else "",
                    "team2Logo": item["imgs"][1] if len(item["imgs"]) > 1 else "",
                    "leagueLogo": league_logo,
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "status": status,
                    "streamUrl": stream_url,
                    "contentType": "event_pertandingan",
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/"
                })
                print(f"[ADD] {status.upper()}: {home} vs {away}")
            except: continue

    finally:
        driver.quit()

    if hasil:
        # Kirim ke Firebase dengan PUT (Overwrite data lama)
        url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        payload = {
            "category_name": "EVENT1",
            "channels": {uuid.uuid4().hex: x for x in hasil}
        }
        requests.put(url, json=payload, timeout=30)
        print(f"Update Selesai: {len(hasil)} match liga besar masuk database.")

if __name__ == "__main__":
    jalankan_scraper()
