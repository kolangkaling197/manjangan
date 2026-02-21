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

def clean_team_name(name):
    """Pembersihan nama tim agar bersih dari teks sampah."""
    if not name: return "TBA"
    trash = ["Trực tiếp", "Bóng đá", "Xem", "Live", "Sắp diễn ra", "ngy"]
    for word in trash:
        name = re.sub(rf'\b{word}\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(?<![uU])\b\d+\b(?!\d)', '', name)
    name = re.sub(r"[^a-zA-Z0-9\s.()]", "", name)
    return " ".join(name.split())

def get_stream_and_league_logo(driver, match_url, liga):
    """Ambil stream link dengan durasi tunggu dan paksa interaksi."""
    stream_url = "Not Found"
    league_logo = "https://cdn-icons-png.flaticon.com/512/53/53283.png"
    try:
        driver.get(match_url)
        time.sleep(10) # Menambah waktu tunggu agar player termuat sempurna
        
        # Simulasi klik area player untuk memancing m3u8 muncul di log
        try:
            player_element = driver.find_element(By.CSS_SELECTOR, "div#player, iframe, video")
            driver.execute_script("arguments[0].click();", player_element)
            time.sleep(5)
        except: pass

        # Ambil m3u8 dari performance logs
        logs = driver.get_log("performance")
        for entry in logs:
            msg = entry.get("message", "")
            if ".m3u8" in msg:
                m = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', msg)
                if m: 
                    stream_url = m.group(0).replace("\\/", "/")
                    break
        
        # Cari logo liga
        imgs = driver.find_elements(By.TAG_NAME, "img")
        for img in imgs:
            alt = (img.get_attribute("alt") or "").lower()
            src = img.get_attribute("src") or img.get_attribute("data-src")
            if liga.lower() in alt and src:
                league_logo = src
                break
    except: pass
    return stream_url, league_logo

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

        # Scroll untuk memicu Lazy Load
        for _ in range(12):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        match_list = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and url not in seen_urls and len(teks) > 10:
                imgs = [img.get_attribute("src") or img.get_attribute("data-src") for img in card.find_elements(By.TAG_NAME, "img")]
                match_list.append({"url": url, "text": teks, "imgs": imgs})
                seen_urls.add(url)

        for item in match_list:
            try:
                # 1. CEK LABEL LIVE
                is_live_label = "Live" in item["text"]
                
                # 2. PARSING NAMA TIM
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                clean_lines = []
                for l in lines:
                    if re.match(r"^\d+('\+?\d*)?$", l): continue 
                    if l.isdigit() and len(l) <= 2: continue 
                    clean_lines.append(l)

                if len(clean_lines) < 3: continue
                liga, home, away = clean_lines[0], clean_lines[1], clean_lines[2]
                
                # 3. PROSES STREAM (WAJIB JIKA LIVE)
                stream_url = "Not Found"
                l_logo = "https://cdn-icons-png.flaticon.com/512/53/53283.png"
                status_final = "upcoming"

                if is_live_label:
                    # Ambil link stream secara agresif
                    stream_url, l_logo = get_stream_and_league_logo(driver, item["url"], liga)
                    
                    # LOGIKA VALIDASI: Hanya set LIVE jika link ditemukan
                    if stream_url != "Not Found":
                        status_final = "live"
                    else:
                        # Jika label LIVE tapi link TIDAK ADA, jadikan UPCOMING agar user tidak zonk
                        status_final = "upcoming"
                    
                    driver.get(TARGET_URL)
                    time.sleep(3)
                else:
                    status_final = "upcoming"

                # 4. JAM PERTANDINGAN
                jam_match = re.search(r"(\d{2}:\d{2})\s+(\d{2}/\d{2})", item["text"])
                start_ts = int(datetime.strptime(f"{jam_match.group(1)} {jam_match.group(2)}/2026", "%H:%M %d/%m/%Y").replace(tzinfo=tz_jkt).timestamp() * 1000) if jam_match else int(time.time() * 1000)

                hasil.append({
                    "channelName": f"[{liga}] {clean_team_name(home)} vs {clean_team_name(away)}",
                    "team1Name": clean_team_name(home), "team1Logo": item["imgs"][0] if len(item["imgs"]) > 0 else "",
                    "team2Name": clean_team_name(away), "team2Logo": item["imgs"][1] if len(item["imgs"]) > 1 else "",
                    "leagueLogo": l_logo,
                    "status": status_final,
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "streamUrl": stream_url,
                    "contentType": "event_pertandingan",
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/"
                })
                print(f"   [{status_final.upper()}] {home} vs {away} | Stream: {'OK' if stream_url != 'Not Found' else 'MISSING'}")
            except: continue

    finally:
        driver.quit()

    if hasil:
        # Kirim ke Firebase sesuai permintaan Anda
        fb_url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        payload = {
            "category_name": "EVENT1",
            "order": 1,
            "channels": {uuid.uuid4().hex: x for x in hasil}
        }
        requests.put(fb_url, json=payload, timeout=30)
        print(f"[√] BERHASIL! {len(hasil)} match terdaftar di Firebase.")

if __name__ == "__main__":
    jalankan_scraper()
