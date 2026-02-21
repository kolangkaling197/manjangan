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
def jalankan_scraper():
    print(f"===== START SCRAPER: {TARGET_URL} =====")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        time.sleep(7)

        # Scroll dalam untuk memicu lazy load jadwal (Schedule/Soon)
        for _ in range(4):
            driver.execute_script("window.scrollBy(0, 1500);")
            time.sleep(2)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        raw_matches = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            if url and url not in seen_urls:
                teks = card.text.strip()
                if len(teks) > 5:
                    imgs = [get_img_src(i) for i in card.find_elements(By.TAG_NAME, "img")]
                    raw_matches.append({"url": url, "text": teks, "imgs": imgs})
                    seen_urls.add(url)

        print(f"Ditemukan {len(raw_matches)} potensi match. Memproses detail...")

        for item in raw_matches:
            try:
                # 1. Parsing Teks & Filter Liga Populer
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                
                nama_liga = "Live Match"
                for line in lines:
                    if filter_liga_populer(line):
                        nama_liga = line
                        break
                
                # Jika liga tidak masuk daftar kasta tinggi, lewati
                if nama_liga == "Live Match" and len(raw_matches) > 15:
                    continue

                # 2. Ambil Jam & Stream dari halaman detail
                stream_url, league_logo = get_stream_details(driver, item["url"])
                page_text = driver.page_source
                time_search = re.search(r"(\d{2}:\d{2}).*?(\d{2}/\d{2})", page_text)
                
                if time_search:
                    dt_str = f"{time_search.group(1)} {time_search.group(2)}/2026"
                    dt_naive = datetime.strptime(dt_str, "%H:%M %d/%m/%Y")
                    dt_aware = dt_naive.replace(tzinfo=tz_jkt) # Fix GMT+7
                    start_ts = int(dt_aware.timestamp() * 1000)
                else:
                    start_ts = int(datetime.now(tz_jkt).timestamp() * 1000)

                # 3. Cleaning Nama Tim
                clean = [l for l in lines if l != nama_liga and ":" not in l and "/" not in l and "'" not in l and not l.isdigit()]
                home = re.sub(r"^\d+\s+|\s+\d+$", "", clean[0]) if len(clean) >= 1 else "Team A"
                away = re.sub(r"^\d+\s+|\s+\d+$", "", clean[1]) if len(clean) >= 2 else "Team B"

                # 4. Logika Status (Live / Upcoming/Soon)
                now_ts = int(datetime.now(tz_jkt).timestamp() * 1000)
                is_live = (start_ts <= now_ts) or (stream_url != "Not Found")
                status_text = "live" if is_live else "upcoming"

                hasil.append({
                    "channelName": f"[{nama_liga}] {home} vs {away}",
                    "team1Name": home, "team2Name": away,
                    "team1Logo": item["imgs"][0] if len(item["imgs"]) > 0 else "",
                    "team2Logo": item["imgs"][1] if len(item["imgs"]) > 1 else "",
                    "leagueLogo": league_logo,
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "status": status_text, # Status 'upcoming' tampil sebagai Soon
                    "streamUrl": stream_url,
                    "contentType": "event_pertandingan",
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/"
                })
                print(f"   [{status_text.upper()}] {home} vs {away}")
            except: continue
    finally:
        driver.quit()

    if hasil:
        kirim_ke_firebase(hasil) # Memastikan pengiriman data di akhir
    else:
        print("[!] Tidak ada data yang lolos filter.")

if __name__ == "__main__":
    jalankan_scraper()
