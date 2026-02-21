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
TARGET_URL = "https://bunchatv.net/"
FIXED_CATEGORY_ID = "EVENT1" 
tz_jkt = timezone(timedelta(hours=7))

# White-list Liga Kasta Tinggi
HIGH_LEAGUE_KEYWORDS = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1", 
    "Liga Indonesia", "BRI Liga 1", "Saudi Pro League", "Champions League",
    "Europa League", "NBA", "Liga MX", "A-League", "J1 League", "V-League",
    "World Cup", "AFC Champions League", "Eredivisie", "K-League"
]

def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""

def filter_liga_populer(nama_liga):
    """Memastikan hanya liga besar yang masuk ke database"""
    return any(k.lower() in nama_liga.lower() for k in HIGH_LEAGUE_KEYWORDS)

# ==============================
# FUNGSI KIRIM KE FIREBASE
# ==============================
def kirim_ke_firebase(data):
    """Menghapus data lama dan mengganti dengan data baru termasuk parameter order"""
    if not FIREBASE_URL or not FIREBASE_SECRET:
        print("[!] ERROR: Environment Secrets Firebase tidak ditemukan.")
        return

    base_url = FIREBASE_URL.rstrip('/')
    url_fb = f"{base_url}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
    
    # Payload dengan penambahan field order
    payload = {
        "category_name": "EVENT1",
        "order": 15,
        "channels": {uuid.uuid4().hex: x for x in data}
    }

    try:
        # Gunakan PUT untuk me-reset data agar tidak duplikat
        res = requests.put(url_fb, json=payload, timeout=40)
        if res.status_code == 200:
            print(f"[√] BERHASIL! {len(data)} match diperbarui di Firebase dengan Order: 1.")
        else:
            print(f"[!] GAGAL FIREBASE: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[!] ERROR KONEKSI FIREBASE: {e}")

# ==============================
# LOGIKA DETAIL MATCH
# ==============================
def get_stream_details(driver, url):
    stream_url = "Not Found"
    league_logo = ""
    try:
        driver.get(url)
        time.sleep(8) 
        
        logos = driver.find_elements(By.TAG_NAME, "img")
        for img in logos:
            src = get_img_src(img)
            alt = (img.get_attribute("alt") or "").lower()
            if src and ("logo" in alt or "league" in src):
                league_logo = src
                break

        try:
            logs = driver.get_log("performance")
            for entry in logs:
                msg = entry.get("message", "")
                if ".m3u8" in msg:
                    m = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', msg)
                    if m: 
                        stream_url = m.group(0).replace("\\/", "/")
                        break
        except: pass
    except: pass
    return stream_url, league_logo

# ==============================
# MAIN JALANKAN SCRAPER
# ==============================

def clean_team_name(name):
    """
    Bersihkan skor & menit tanpa merusak U17/U18
    """
    if not name:
        return ""

    # Hapus skor 2-1 atau 3 : 0
    name = re.sub(r"\b\d+\s*[-:]\s*\d+\b", "", name)

    # Hapus menit 45' atau 90+2'
    name = re.sub(r"\b\d+\+?\d*'\b", "", name)

    # Hapus angka berdiri sendiri
    # KECUALI angka setelah huruf U
    name = re.sub(r"(?<!U)\b\d+\b", "", name)

    # Rapikan spasi
    name = re.sub(r"\s+", " ", name)

    return name.strip()


def jalankan_scraper():
    print(f"===== SCRAP MAIN PAGE: {TARGET_URL} =====")

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")

    driver = uc.Chrome(options=options)

    hasil = []
    seen_matches = set()

    try:
        driver.get(TARGET_URL)
        time.sleep(6)

        # Scroll supaya semua schedule load
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

                # ===== FILTER LIGA =====
                nama_liga = None
                for line in lines:
                    if filter_liga_populer(line):
                        nama_liga = line
                        break

                if not nama_liga:
                    continue

                # ===== PARSE JAM =====
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

                # ===== PARSE TIM =====
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

                # ===== ANTI DUPLIKAT =====
                key = f"{home.lower()}_{away.lower()}_{start_ts}"
                if key in seen_matches:
                    continue
                seen_matches.add(key)

                # ===== STATUS =====
                now_ts = int(datetime.now(tz_jkt).timestamp() * 1000)
                status_text = "live" if start_ts <= now_ts else "upcoming"

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
                    "streamUrl": "Not Available",
                    "contentType": "event_pertandingan",
                    "playerType": "internal_with_headers",
                    "referer": TARGET_URL
                })

                print(f"[{status_text.upper()}] {home} vs {away}")

            except:
                continue

    finally:
        driver.quit()

    if hasil:
        kirim_ke_firebase(hasil)
    else:
        print("Tidak ada match valid.")
        
if __name__ == "__main__":
    jalankan_scraper()

