import os
import re
import time
import uuid
import requests
from datetime import datetime, timezone, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


# ==============================
# KONFIGURASI
# ==============================

FIREBASE_URL = os.getenv("FIREBASE_URL")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET")

TARGET_URL = "https://bunchatv.net/"
FIXED_CATEGORY_ID = "EVENT1"

tz_jkt = timezone(timedelta(hours=7))

HIGH_LEAGUE_KEYWORDS = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1",
    "Liga Indonesia", "BRI Liga 1", "Saudi Pro League",
    "Champions League", "Europa League", "NBA",
    "Liga MX", "A-League", "J1 League",
    "World Cup", "AFC Champions League",
    "Eredivisie", "K-League"
]


# ==============================
# UTIL
# ==============================

def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""


def filter_liga_populer(nama_liga):
    return any(k.lower() in nama_liga.lower() for k in HIGH_LEAGUE_KEYWORDS)


def clean_team_name(name):
    if not name:
        return ""

    name = re.sub(r"\b\d+\s*[-:]\s*\d+\b", "", name)
    name = re.sub(r"\b\d+\+?\d*'\b", "", name)
    name = re.sub(r"(?<!U)\b\d+\b", "", name)
    name = re.sub(r"\s+", " ", name)

    return name.strip()


# ==============================
# FIREBASE
# ==============================

def kirim_ke_firebase(data):
    if not FIREBASE_URL or not FIREBASE_SECRET:
        print("Firebase env tidak ditemukan.")
        return

    base_url = FIREBASE_URL.rstrip("/")
    url_fb = f"{base_url}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"

    payload = {
        "category_name": "EVENT1",
        "order": 15,
        "lastUpdated": int(datetime.now(tz_jkt).timestamp() * 1000),
        "channels": {uuid.uuid4().hex: x for x in data}
    }

    try:
        res = requests.put(url_fb, json=payload, timeout=40)
        if res.status_code == 200:
            print(f"Berhasil update {len(data)} match.")
        else:
            print(f"Gagal Firebase: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Error koneksi Firebase: {e}")


# ==============================
# STREAM CAPTURE
# ==============================

def get_stream_from_detail(driver, url):
    stream_url = ""

    try:
        driver.get(url)
        time.sleep(6)

        logs = driver.get_log("performance")

        for entry in logs:
            message = entry.get("message", "")
            if ".m3u8" in message:
                match = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', message)
                if match:
                    stream_url = match.group(0).replace("\\/", "/")
                    break
    except Exception:
        pass

    return stream_url


# ==============================
# SCRAPER
# ==============================

def jalankan_scraper():
    print(f"===== SCRAP MAIN PAGE: {TARGET_URL} =====")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # FIX SELENIUM 4+
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=options)

    hasil = []
    seen_matches = set()

    try:
        driver.get(TARGET_URL)
        time.sleep(6)

        for _ in range(6):
            driver.execute_script("window.scrollBy(0, 2500);")
            time.sleep(2)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        print(f"Total card ditemukan: {len(cards)}")

        for card in cards:
            try:
                teks = card.text.strip()
                if not teks:
                    continue

                lines = [l.strip() for l in teks.split("\n") if l.strip()]

                nama_liga = None
                for line in lines:
                    if filter_liga_populer(line):
                        nama_liga = line
                        break

                if not nama_liga:
                    continue

                time_match = None
                for l in lines:
                    m = re.search(r"\d{2}:\d{2}", l)
                    if m:
                        time_match = m.group()
                        break

                if time_match:
                    now = datetime.now(tz_jkt)
                    dt_str = f"{time_match} {now.day}/{now.month}/{now.year}"
                    dt_naive = datetime.strptime(dt_str, "%H:%M %d/%m/%Y")
                    dt_aware = dt_naive.replace(tzinfo=tz_jkt)
                    start_ts = int(dt_aware.timestamp() * 1000)
                else:
                    start_ts = int(datetime.now(tz_jkt).timestamp() * 1000)

                team_lines = []

                for l in lines:
                    if l == nama_liga:
                        continue
                    if ":" in l and re.search(r"\d{2}:\d{2}", l):
                        continue

                    cleaned = clean_team_name(l)
                    if cleaned and len(cleaned) > 2:
                        team_lines.append(cleaned)

                if len(team_lines) < 2:
                    continue

                home = team_lines[0]
                away = team_lines[1]

                key = f"{home.lower()}_{away.lower()}_{start_ts}"
                if key in seen_matches:
                    continue
                seen_matches.add(key)

                now_ts = int(datetime.now(tz_jkt).timestamp() * 1000)
                status_text = "live" if start_ts <= now_ts else "upcoming"

                stream_url = "Not Available"

                if status_text == "live":
                    detail_url = card.get_attribute("href")
                    stream_url = get_stream_from_detail(driver, detail_url)

                imgs = [get_img_src(i) for i in card.find_elements(By.TAG_NAME, "img")]

                hasil.append({
                    "channelName": f"[{nama_liga}] {home} vs {away}",
                    "team1Name": home,
                    "team2Name": away,
                    "team1Logo": imgs[0] if len(imgs) > 0 else "",
                    "team2Logo": imgs[1] if len(imgs) > 1 else "",
                    "leagueLogo": "",
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "status": status_text,
                    "streamUrl": stream_url,
                    "contentType": "event_pertandingan",
                    "playerType": "internal_with_headers",
                    "referer": TARGET_URL
                })

                print(f"[{status_text.upper()}] {home} vs {away}")

            except Exception:
                continue

    finally:
        driver.quit()

    if hasil:
        kirim_ke_firebase(hasil)
    else:
        print("Tidak ada match valid.")


if __name__ == "__main__":
    jalankan_scraper()
