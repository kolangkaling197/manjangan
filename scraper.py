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

# Filter Liga Kasta Tinggi
HIGH_LEAGUE_KEYWORDS = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1", 
    "Champions League", "Europa League", "BRI Liga 1", "Liga Indonesia", 
    "Saudi Pro League", "World Cup", "NBA", "J1 League", "K-League", "V-League",
    "A-League", "Eredivisie", "U23", "U20", "U17"
]

TRASH_WORDS = ["Trực tiếp", "Bóng đá", "Xem", "Live", "Bình luận", "Hot", "Full"]

def clean_team_name(name):
    """Membersihkan nama tim dari skor, vs, dan teks sampah"""
    if not name or name.strip() in ["'", "-", "vs"]: return "TBA"
    for word in TRASH_WORDS:
        name = re.sub(rf'\b{word}\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\bvs\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(?<![uU])\b\d+\b(?!\d)', '', name) # Jaga U17/U23
    name = re.sub(r"[^a-zA-Z0-9\s.()]", "", name)
    name = " ".join(name.split())
    return name if len(name) > 1 else "TBA"

def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""

def get_match_details(driver, url):
    """Ambil Jam, Stream, Logo Liga, dan Logo Tim dari halaman detail"""
    data = {"stream_url": "Not Found", "league_logo": "", "t1_logo": "", "t2_logo": "", "start_ts": None}
    try:
        driver.get(url)
        time.sleep(7)
        page_text = driver.page_source
        time_match = re.search(r"(\d{2}:\d{2}).*?(\d{2}/\d{2})", page_text)
        if time_match:
            dt_str = f"{time_match.group(1)} {time_match.group(2)}/2026"
            dt_naive = datetime.strptime(dt_str, "%H:%M %d/%m/%Y")
            data["start_ts"] = int(dt_naive.replace(tzinfo=tz_jkt).timestamp() * 1000)

        # Ambil Stream m3u8
        logs = driver.get_log("performance")
        for entry in logs:
            msg = entry.get("message", "")
            if ".m3u8" in msg:
                m = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', msg)
                if m: data["stream_url"] = m.group(0).replace("\\/", "/"); break

        # Scrape Gambar (Logo Liga & Tim)
        imgs = [get_img_src(img) for img in driver.find_elements(By.TAG_NAME, "img") 
                if "logo" in get_img_src(img).lower() or "cdn" in get_img_src(img).lower()]
        if len(imgs) >= 3:
            data["league_logo"], data["t1_logo"], data["t2_logo"] = imgs[0], imgs[1], imgs[2]
    except: pass
    return data

def jalankan_scraper():
    print(f"===== FOCUS MODE: TAB TẤT CẢ =====")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        time.sleep(10)

        # Pastikan kita di tab 'Tất cả' (Biasanya default, tapi kita scroll untuk load semua)
        print("Melakukan Deep Scroll untuk memicu Lazy Load...")
        for _ in range(8): # Scroll lebih banyak agar semua match muncul
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(2)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        raw_matches = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            if url and url not in seen_urls:
                raw_matches.append({"url": url, "text": card.text.strip()})
                seen_urls.add(url)

        print(f"Total {len(raw_matches)} match ditemukan. Memfilter liga besar...")

        for item in raw_matches:
            try:
                # Filter Liga
                if not any(k.lower() in item["text"].lower() for k in HIGH_LEAGUE_KEYWORDS):
                    continue

                detail = get_match_details(driver, item["url"])
                if not detail["start_ts"]: continue

                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                liga = lines[0] if lines else "Match"
                clean_lines = [l for l in lines if l != liga and ":" not in l and "/" not in l]
                
                home = clean_team_name(clean_lines[0]) if len(clean_lines) >= 1 else "Team A"
                away = clean_team_name(clean_lines[1]) if len(clean_lines) >= 2 else "Team B"

                now_ts = int(datetime.now(tz_jkt).timestamp() * 1000)
                status = "live" if (detail["start_ts"] <= now_ts) or (detail["stream_url"] != "Not Found") else "upcoming"

                hasil.append({
                    "channelName": f"[{liga}] {home} vs {away}",
                    "team1Name": home, "team1Logo": detail["t1_logo"],
                    "team2Name": away, "team2Logo": detail["t2_logo"],
                    "leagueLogo": detail["league_logo"],
                    "startTime": detail["start_ts"],
                    "endTime": detail["start_ts"] + 7200000,
                    "status": status,
                    "streamUrl": detail["stream_url"],
                    "contentType": "event_pertandingan",
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/"
                })
                print(f"   [{status.upper()}] {home} vs {away} (Logo OK)")
            except: continue

    finally: driver.quit()

    if hasil:
        payload = {"category_name": "EVENT1", "order": 15, "channels": {uuid.uuid4().hex: x for x in hasil}}
        requests.put(f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}", json=payload)
        print(f"[√] BERHASIL! {len(hasil)} match dari tab 'Tất cả' tayang.")

if __name__ == "__main__":
    jalankan_scraper()
