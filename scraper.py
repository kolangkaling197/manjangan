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

# Keywords sampah diperketat
TRASH_WORDS = ["Trực tiếp", "Bóng đá", "Xem", "Live", "Hot", "Full", "Bình luận", "ngy", "Japanese", "Australia", "Premier", "League"]

def clean_team_name(name):
    """Pembersihan nama tim agar tidak ada teks liga atau sampah lainnya."""
    if not name: return "TBA"
    for word in TRASH_WORDS:
        name = re.sub(rf'\b{word}\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(?<![uU])\b\d+\b(?!\d)', '', name)
    name = re.sub(r"[^a-zA-Z0-9\s.()]", "", name)
    name = " ".join(name.split())
    return name if len(name) > 1 else "TBA"

def get_match_details(driver, url):
    """Fungsi mendalam untuk ambil Jam, Logo, dan Nama Tim dari elemen scoreboard detail."""
    data = {"stream": "Not Found", "l_logo": "", "t1_logo": "", "t2_logo": "", "ts": None, "t1_name": "", "t2_name": "", "liga": "Match"}
    try:
        driver.get(url)
        time.sleep(8) # Waktu tunggu lebih lama untuk detail
        
        # 1. AMBIL NAMA TIM DARI SCOREBOARD (Anti-TBA)
        try:
            # Mencari elemen nama tim yang biasanya ada di samping logo besar
            team_elements = driver.find_elements(By.CSS_SELECTOR, "h2, .team-name, .name")
            if len(team_elements) >= 2:
                data["t1_name"] = team_elements[0].text.strip()
                data["t2_name"] = team_elements[1].text.strip()
        except: pass

        # 2. AMBIL WAKTU
        time_match = re.search(r"(\d{2}:\d{2}).*?(\d{2}/\d{2})", driver.page_source)
        if time_match:
            dt_str = f"{time_match.group(1)} {time_match.group(2)}/2026"
            data["ts"] = int(datetime.strptime(dt_str, "%H:%M %d/%m/%Y").replace(tzinfo=tz_jkt).timestamp() * 1000)

        # 3. AMBIL LOGO (Logo 1, Logo 2, Logo Liga)
        imgs = [i.get_attribute("src") or i.get_attribute("data-src") for i in driver.find_elements(By.TAG_NAME, "img") if i.get_attribute("src")]
        match_logos = [src for src in imgs if any(x in src.lower() for x in ["logo", "cdn", "team", "flag", "attachment"])]
        if len(match_logos) >= 3:
            data["l_logo"], data["t1_logo"], data["t2_logo"] = match_logos[0], match_logos[1], match_logos[2]

        # 4. AMBIL STREAM
        logs = driver.get_log("performance")
        for entry in logs:
            if ".m3u8" in entry.get("message", ""):
                m = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', entry.get("message", ""))
                if m: data["stream"] = m.group(0).replace("\\/", "/"); break
    except: pass
    return data

def jalankan_scraper():
    print(f"===== START SCRAPER: {TARGET_URL} =====")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        time.sleep(10)

        # SCROLL SANGAT DALAM (15x)
        for _ in range(15):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        raw_list = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            if url and url not in seen_urls:
                # Simpan teks kartu sebagai cadangan
                raw_list.append({"url": url, "text": card.text.strip()})
                seen_urls.add(url)

        print(f"Ditemukan {len(raw_list)} match. Memproses semua...")

        for item in raw_list:
            try:
                detail = get_match_details(driver, item["url"])
                if not detail["ts"]: continue

                # Gunakan nama dari detail, jika kosong baru gunakan teks kartu
                home = clean_team_name(detail["t1_name"]) if detail["t1_name"] else "Team A"
                away = clean_team_name(detail["t2_name"]) if detail["t2_name"] else "Team B"
                
                # Jika detail masih TBA, pecah dari teks kartu (Fallback terakhir)
                if home == "Team A" or away == "Team B":
                    parts = item["text"].split("\n")
                    if len(parts) >= 3:
                        home = clean_team_name(parts[1])
                        away = clean_team_name(parts[2])

                # LOGIKA STATUS: Jika status LIVE tapi link m3u8 TIDAK ADA, paksa jadi UPCOMING
                now_ts = int(datetime.now(tz_jkt).timestamp() * 1000)
                if detail["stream"] == "Not Found" and detail["ts"] > (now_ts - 3600000):
                    status_text = "upcoming"
                elif detail["ts"] > (now_ts + 600000):
                    status_text = "upcoming"
                else:
                    status_text = "live"

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
            except: continue

    finally:
        driver.quit()

    if hasil:
        payload = {"category_name": "EVENT1", "order": 15, "channels": {uuid.uuid4().hex: x for x in hasil}}
        requests.put(f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}", json=payload)
        print(f"[√] BERHASIL! {len(hasil)} match terdaftar.")

if __name__ == "__main__":
    jalankan_scraper()
