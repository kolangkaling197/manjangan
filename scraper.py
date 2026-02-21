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

def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""

def get_match_details(driver, match_url):
    stream_url = "Not Found"
    league_logo = ""
    try:
        driver.get(match_url)
        time.sleep(5)
        driver.execute_script("document.querySelectorAll('.modal,.popup,.fixed,[id*=ads]').forEach(e=>e.remove());")
        
        # Scrape Logo Liga
        logos = driver.find_elements(By.TAG_NAME, "img")
        for img in logos:
            src = get_img_src(img)
            alt = (img.get_attribute("alt") or "").lower()
            if src and ("logo" in alt or "league" in src or "tournament" in src):
                league_logo = src
                break

        # Ambil link m3u8
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                msg = entry.get("message", "")
                if ".m3u8" in msg:
                    m = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', msg)
                    if m: return m.group(0).replace("\\/", "/"), league_logo
        except: pass

        html = driver.page_source
        m = re.search(r"https://[^\s\"']+\.m3u8[^\s\"']*", html)
        if m: return m.group(0), league_logo
    except: pass
    return "Not Found", league_logo

def kirim_ke_firebase(data):
    url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
    payload = {
        "category_name": "EVENT1",
        "order": 15,
        "sourceUrl": TARGET_URL,
        "channels": {uuid.uuid4().hex: item for item in data}
    }
    requests.put(url, json=payload, timeout=30)

def jalankan_scraper():
    print("\n===== START SCRAPER (DEEP CLEANING MODE) =====\n")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href,'truc-tiep')]")))
        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        
        initial_matches = []
        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and len(teks) > 5:
                imgs = [get_img_src(img) for img in card.find_elements(By.TAG_NAME, "img")]
                initial_matches.append({"url": url, "text": teks, "imgs": imgs})

        print(f"Total match ditemukan: {len(initial_matches)}. Mulai proses...")

        for item in initial_matches:
            try:
                # 1. Ambil Detail & Jam
                stream_url, league_logo = get_match_details(driver, item["url"])
                page_text = driver.page_source
                time_search = re.search(r"(\d{2}:\d{2}).*?(\d{2}/\d{2})", page_text)
                
                if time_search:
                    dt_naive = datetime.strptime(f"{time_search.group(1)} {time_search.group(2)}/2026", "%H:%M %d/%m/%Y")
                    dt_aware = dt_naive.replace(tzinfo=tz_jkt) 
                    start_ts = int(dt_aware.timestamp() * 1000)
                else:
                    start_ts = int(datetime.now(tz_jkt).timestamp() * 1000)

                # 2. LOGIKA PEMBERSIHAN NAMA (Anti-Ngawur)
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                clean = []
                for l in lines:
                    # Buang baris jika: Hanya angka, Ada jam (00:00), Ada tanggal (00/00), Menit (45')
                    if re.match(r"^\d+$", l): continue 
                    if re.match(r"^\d{2}:\d{2}$", l): continue
                    if re.match(r"^\d{2}/\d{2}$", l): continue
                    if "'" in l or l.upper() in ["HT", "FT", "LIVE"]: continue
                    clean.append(l)

                # Identifikasi Home & Away
                if len(clean) >= 3:
                    liga, home, away = clean[0], clean[1], clean[2]
                elif len(clean) == 2:
                    liga, home, away = "Live Event", clean[0], clean[1]
                else:
                    # Jika nama tim masih tercampur "vs", kita pecah manual
                    full_txt = " ".join(clean)
                    if " vs " in full_txt:
                        liga = "Live Match"
                        teams = full_txt.split(" vs ")
                        home, away = teams[0].strip(), teams[1].strip()
                    else: continue 

                # Hapus angka skor yang sering menempel di depan nama tim
                home = re.sub(r"^\d+\s+", "", home)
                away = re.sub(r"^\d+\s+", "", away)

                current_ts = int(datetime.now(tz_jkt).timestamp() * 1000)
                status = "live" if (start_ts <= current_ts) or (stream_url != "Not Found") else "upcoming"

                hasil.append({
                    "channelName": f"[{liga}] {home} vs {away}",
                    "leagueName": liga,
                    "leagueLogo": league_logo,
                    "team1Name": home,
                    "team1Logo": item["imgs"][0] if len(item["imgs"]) > 0 else "",
                    "team2Name": away,
                    "team2Logo": item["imgs"][1] if len(item["imgs"]) > 1 else "",
                    "contentType": "event_pertandingan",
                    "status": status,
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "referer": "https://bunchatv.net/",
                    "streamUrl": stream_url,
                    "playerType": "internal_with_headers"
                })
                print(f"[OK] {home} vs {away} | Jam: {time_search.group(1) if time_search else 'Live'}")
            except: continue
    finally:
        driver.quit()

    if hasil:
        kirim_ke_firebase(hasil)
        print(f"[√] Berhasil! {len(hasil)} match diperbarui.")

if __name__ == "__main__":
    jalankan_scraper()
