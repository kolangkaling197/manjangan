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
TARGET_URL = "https://bunchatv.net/"
FIXED_CATEGORY_ID = "EVENT1" 
tz_jkt = timezone(timedelta(hours=7))

HIGH_LEAGUE_KEYWORDS = [
    "Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1", 
    "Liga Indonesia", "BRI Liga 1", "Saudi Pro League", "Champions League",
    "Europa League", "NBA", "V-League", "K-League", "J1 League", "A-League"
]

def clean_team_name(name):
    """Membersihkan nama tim dari skor, 'vs', dan karakter sampah"""
    if not name: return "TBA"
    # 1. Hapus kata 'vs' (case insensitive)
    name = re.sub(r'\bvs\b', '', name, flags=re.IGNORECASE)
    # 2. Hapus angka skor (misal: 'Team A 1' atau '2 Team B') tapi jaga label usia (U17, U23, dll)
    # Regex ini menghapus angka yang berdiri sendiri atau di ujung, tapi tidak angka yang menempel di huruf 'U'
    name = re.sub(r'(?<![uU])\b\d+\b(?!\d)', '', name)
    # 3. Hapus simbol sisa seperti '-', '(', ')'
    name = name.replace('-', '').replace('(', '').replace(')', '')
    # 4. Hapus spasi ganda
    name = " ".join(name.split())
    return name if name else "TBA"

def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""

def get_match_details(driver, url):
    """Masuk ke detail untuk ambil JAM, m3u8, dan logo liga"""
    data = {"stream_url": "Not Found", "league_logo": "", "start_ts": None}
    try:
        driver.get(url)
        time.sleep(7) 
        
        # 1. Ambil Jam & Tanggal (Sangat Penting untuk Status Live/Upcoming)
        # Mencari pola jam (00:00) dan tanggal (00/00) di seluruh halaman
        page_text = driver.page_source
        time_match = re.search(r"(\d{2}:\d{2}).*?(\d{2}/\d{2})", page_text)
        if time_match:
            try:
                dt_str = f"{time_match.group(1)} {time_match.group(2)}/2026"
                dt_naive = datetime.strptime(dt_str, "%H:%M %d/%m/%Y")
                dt_aware = dt_naive.replace(tzinfo=tz_jkt)
                data["start_ts"] = int(dt_aware.timestamp() * 1000)
            except: pass

        # 2. Ambil m3u8 dari log performa
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                msg = entry.get("message", "")
                if ".m3u8" in msg:
                    m = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', msg)
                    if m: 
                        data["stream_url"] = m.group(0).replace("\\/", "/")
                        break
        except: pass

        # 3. Ambil Logo Liga
        logos = driver.find_elements(By.TAG_NAME, "img")
        for img in logos:
            src = get_img_src(img)
            alt = (img.get_attribute("alt") or "").lower()
            if src and ("logo" in alt or "league" in src):
                data["league_logo"] = src
                break
    except: pass
    return data

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
        driver.execute_script("window.scrollTo(0, 2000);")
        time.sleep(3)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        raw_matches = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            if url and url not in seen_urls:
                raw_matches.append({"url": url, "text": card.text.strip()})
                seen_urls.add(url)

        print(f"Ditemukan {len(raw_matches)} match. Menganalisis waktu & nama...")

        for item in raw_matches:
            try:
                # Ambil info detail (Waktu adalah Prioritas)
                detail = get_match_details(driver, item["url"])
                if not detail["start_ts"]: continue # Skip jika jam tidak ketemu

                # Parsing Teks Card untuk Nama Tim
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                
                # Filter liga
                nama_liga = "Match"
                for line in lines:
                    if any(k.lower() in line.lower() for k in HIGH_LEAGUE_KEYWORDS):
                        nama_liga = line
                        break
                
                # Bersihkan Nama Tim
                clean_lines = [l for l in lines if l != nama_liga and ":" not in l and "/" not in l]
                if len(clean_lines) >= 2:
                    home = clean_team_name(clean_lines[0])
                    away = clean_team_name(clean_lines[1])
                else:
                    # Cek jika formatnya satu baris dengan 'vs'
                    parts = re.split(r'\bvs\b', clean_lines[0], flags=re.IGNORECASE) if clean_lines else []
                    home = clean_team_name(parts[0]) if len(parts) > 0 else "Team A"
                    away = clean_team_name(parts[1]) if len(parts) > 1 else "Team B"

                # Tentukan Status Berdasarkan Waktu Sekarang
                now_ts = int(datetime.now(tz_jkt).timestamp() * 1000)
                is_live = (detail["start_ts"] <= now_ts) or (detail["stream_url"] != "Not Found")
                status_text = "live" if is_live else "upcoming"

                hasil.append({
                    "channelName": f"[{nama_liga}] {home} vs {away}",
                    "team1Name": home, "team2Name": away,
                    "leagueLogo": detail["league_logo"],
                    "startTime": detail["start_ts"],
                    "endTime": detail["start_ts"] + 7200000,
                    "status": status_text,
                    "streamUrl": detail["stream_url"],
                    "contentType": "event_pertandingan",
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/"
                })
                print(f"   [{status_text.upper()}] {home} vs {away} | Jam: {datetime.fromtimestamp(detail['start_ts']/1000, tz_jkt).strftime('%H:%M')}")
            except: continue
    finally:
        driver.quit()

    if hasil:
        # Kirim ke Firebase dengan Order: 1
        payload = {"category_name": "EVENT1", "order": 15, "channels": {uuid.uuid4().hex: x for x in hasil}}
        requests.put(f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}", json=payload)
        print(f"[√] BERHASIL! {len(hasil)} match tayang.")

if __name__ == "__main__":
    jalankan_scraper()
