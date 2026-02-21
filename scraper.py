import os
import requests
import time
import re
import uuid
from datetime import datetime, timezone, timedelta
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# ==============================
# KONFIGURASI
# ==============================
FIREBASE_URL = os.getenv("FIREBASE_URL")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET")
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"
FIXED_CATEGORY_ID = "EVENT1" 
tz_jkt = timezone(timedelta(hours=7))

# 1. Daftar Liga Kasta Tinggi (Filter Liga)
HIGH_LEAGUE_KEYWORDS = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1", 
    "Champions League", "Europa League", "BRI Liga 1", "Liga Indonesia", 
    "Saudi Pro League", "World Cup", "NBA", "J1 League", "K-League", "V-League",
    "A-League", "Eredivisie", "U23", "U20", "U17"
]

TRASH_WORDS = ["Trực tiếp", "Bóng đá", "Xem", "Live", "Bình luận", "Hot", "Full" "TBA", "vs"]

def clean_team_name(name):
    """Membersihkan nama tim dari skor, kata sampah, dan simbol"""
    if not name or name.strip() in ["'", "-", "vs"]: return "TBA"
    
    # Hapus kata sampah dari daftar TRASH_WORDS
    for word in TRASH_WORDS:
        name = re.sub(rf'\b{word}\b', '', name, flags=re.IGNORECASE)
    
    # Hapus angka (skor/menit) tapi jaga label U17/U23
    name = re.sub(r'(?<![uU])\b\d+\b(?!\d)', '', name)
    
    # Hapus simbol aneh
    name = re.sub(r"[^a-zA-Z0-9\s.()]", "", name)
    
    # Trim spasi ganda
    name = " ".join(name.split())
    return name if len(name) > 1 else "TBA"

def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""

def get_match_details(driver, url):
    """Ambil Jam, Logo Tim, dan m3u8 dari halaman detail"""
    data = {"stream": "Not Found", "l_logo": "", "t1_logo": "", "t2_logo": "", "ts": None, "title": ""}
    try:
        driver.get(url)
        time.sleep(7) 
        data["title"] = driver.title 
        
        # Ambil Jam & Tanggal (Penting untuk Status Upcoming)
        page_source = driver.page_source
        time_match = re.search(r"(\d{2}:\d{2}).*?(\d{2}/\d{2})", page_source)
        if time_match:
            try:
                dt_str = f"{time_match.group(1)} {time_match.group(2)}/2026"
                dt_naive = datetime.strptime(dt_str, "%H:%M %d/%m/%Y")
                data["ts"] = int(dt_naive.replace(tzinfo=tz_jkt).timestamp() * 1000)
            except: pass

        # Ambil Logo (Urutan: Liga, Tim1, Tim2)
        img_elements = driver.find_elements(By.TAG_NAME, "img")
        match_logos = []
        for img in img_elements:
            src = get_img_src(img)
            if src and any(x in src.lower() for x in ["logo", "cdn", "team", "flag", "thumb", "attachment"]):
                match_logos.append(src)
        
        if len(match_logos) >= 3:
            data["l_logo"], data["t1_logo"], data["t2_logo"] = match_logos[0], match_logos[1], match_logos[2]
        elif len(match_logos) == 2:
            data["t1_logo"], data["t2_logo"] = match_logos[0], match_logos[1]
            
        # Ambil Link m3u8 (Logika Performance)
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                if ".m3u8" in entry.get("message", ""):
                    m = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', entry.get("message", ""))
                    if m: data["stream"] = m.group(0).replace("\\/", "/"); break
        except: pass
    except: pass
    return data

def jalankan_scraper():
    print(f"===== START FULL SCRAPER: {TARGET_URL} =====")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        time.sleep(10)

        # Deep Scroll (12x) untuk memicu Upcoming/Schedule muncul
        print("Deep Scrolling untuk memicu jadwal mendatang...")
        for _ in range(12):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1.5)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        raw_list = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            if url and url not in seen_urls:
                raw_list.append({"url": url, "text": card.text.strip()})
                seen_urls.add(url)

        print(f"Ditemukan {len(raw_list)} match. Memproses filter & detail...")

        for item in raw_list:
            # 1. Filter Liga Populer
            if not any(k.lower() in item["text"].lower() for k in HIGH_LEAGUE_KEYWORDS):
                continue
            
            detail = get_match_details(driver, item["url"])
            if not detail["ts"]: continue

            # 2. Parsing Nama Tim (Anti-TBA & Pembersihan)
            header_text = detail["title"].split("-")[0].replace("Xem trực tiếp", "")
            if " vs " in header_text.lower():
                parts = re.split(r'\bvs\b', header_text, flags=re.IGNORECASE)
                home, away = clean_team_name(parts[0]), clean_team_name(parts[1])
            else:
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                home = clean_team_name(lines[1]) if len(lines) > 2 else "Team A"
                away = clean_team_name(lines[2]) if len(lines) > 2 else "Team B"

            # 3. Penentu Status (Live / Upcoming)
            now_ts = int(datetime.now(tz_jkt).timestamp() * 1000)
            # Upcoming jika waktu mulai masih lebih dari 10 menit ke depan
            is_upcoming = detail["ts"] > (now_ts + 600000)
            status_text = "upcoming" if is_upcoming else "live"

            hasil.append({
                "channelName": f"{home} vs {away}",
                "team1Name": home, "team1Logo": detail["t1_logo"],
                "team2Name": away, "team2Logo": detail["t2_logo"],
                "leagueLogo": detail["l_logo"],
                "startTime": detail["ts"],
                "endTime": detail["ts"] + 7200000,
                "status": status_text,
                "streamUrl": detail["stream"],
                "contentType": "event_pertandingan",
                "playerType": "internal_with_headers",
                "referer": "https://bunchatv.net/"
            })
            print(f"   [{status_text.upper()}] {home} vs {away}")

    finally:
        driver.quit()

    if hasil:
        # Kirim ke Firebase dengan Order: 1
        payload = {"category_name": "EVENT1", "order": 15, "channels": {uuid.uuid4().hex: x for x in hasil}}
        requests.put(f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}", json=payload)
        print(f"[√] BERHASIL! {len(hasil)} match (Live & Upcoming) terdaftar.")

if __name__ == "__main__":
    jalankan_scraper()
