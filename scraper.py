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

# Paksa zona waktu ke WIB (GMT+7)
tz_jkt = timezone(timedelta(hours=7))

def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""

def get_stream_and_league_logo(driver, match_url):
    league_logo = ""
    try:
        driver.get(match_url)
        time.sleep(5)
        driver.execute_script("document.querySelectorAll('.modal,.popup,.fixed,[id*=ads]').forEach(e=>e.remove());")
        
        # Ambil Logo Liga
        logos = driver.find_elements(By.TAG_NAME, "img")
        for img in logos:
            src = get_img_src(img)
            alt = (img.get_attribute("alt") or "").lower()
            if src and ("logo" in alt or "league" in src or "tournament" in src):
                league_logo = src
                break

        # Trigger Iframe Player
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in iframes:
            src = frame.get_attribute("src") or ""
            if any(x in src for x in ["player", "embed", "stream", "live"]):
                driver.switch_to.frame(frame)
                break
        
        time.sleep(10)
        
        # Ambil m3u8 dari log jaringan
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
    # Menggunakan PUT untuk menghapus data lama dan mengganti dengan yang baru
    url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
    payload = {
        "category_name": "EVENT1",
        "order": 15,
        "sourceUrl": TARGET_URL,
        "channels": {uuid.uuid4().hex: item for item in data}
    }
    res = requests.put(url, json=payload, timeout=30)
    if res.status_code == 200:
        print(f"[√] Berhasil! {len(data)} match diperbarui di Firebase.")

def jalankan_scraper():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href,'truc-tiep')]"))
        )

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
                # 1. Ambil Stream & Jam dari Halaman Detail
                stream_url, league_logo = get_stream_and_league_logo(driver, item["url"])
                page_text = driver.page_source
                time_match = re.search(r"(\d{2}:\d{2}).*?(\d{2}/\d{2})", page_text)
                
                # Konversi waktu ke GMT+7 (WIB)
                if time_match:
                    dt_naive = datetime.strptime(f"{time_match.group(1)} {time_match.group(2)}/2026", "%H:%M %d/%m/%Y")
                    dt_aware = dt_naive.replace(tzinfo=tz_jkt) 
                    start_ts = int(dt_aware.timestamp() * 1000)
                else:
                    start_ts = int(datetime.now(tz_jkt).timestamp() * 1000)

                # 2. Smart Parsing Nama (Bola, Tenis, Basket)
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                clean = []
                for l in lines:
                    if re.match(r"^\d+'$", l): continue # Buat menit murni
                    if l.upper() in ["HT", "FT", "LIVE"]: continue
                    if re.match(r"^\d{2}:\d{2}$", l): continue 
                    if re.match(r"^\d{2}/\d{2}$", l): continue
                    clean.append(l)

                if len(clean) >= 3:
                    liga, home, away = clean[0], clean[1], clean[2]
                elif len(clean) == 2:
                    liga, home, away = "Live Event", clean[0], clean[1]
                else:
                    full_txt = " ".join(clean)
                    if " vs " in full_txt:
                        liga = "Live Match"
                        teams = full_txt.split(" vs ")
                        home, away = teams[0].strip(), teams[1].strip()
                    else:
                        continue 

                # Bersihkan angka skor sisa di depan nama
                home = re.sub(r"^\d+\s+", "", home)
                away = re.sub(r"^\d+\s+", "", away)

                hasil.append({
                    "channelName": f"[{liga}] {home} vs {away}",
                    "leagueName": liga,
                    "leagueLogo": league_logo,
                    "team1Name": home,
                    "team1Logo": item["imgs"][0] if len(item["imgs"]) > 0 else "",
                    "team2Name": away,
                    "team2Logo": item["imgs"][1] if len(item["imgs"]) > 1 else "",
                    "contentType": "event_pertandingan",
                    "status": "live" if start_ts <= int(datetime.now(tz_jkt).timestamp()*1000) else "upcoming",
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "referer": "https://bunchatv.net/",
                    "streamUrl": stream_url,
                    "playerType": "internal_with_headers"
                })
                print(f"[OK] {home} vs {away}")
            except: continue
    finally:
        driver.quit()

    if hasil:
        kirim_ke_firebase(hasil)

if __name__ == "__main__":
    jalankan_scraper()
