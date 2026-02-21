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
    """Pembersihan nama tim dari teks sampah dan status waktu."""
    if not name: return "TBA"
    trash = ["CƯỢC", "XEM", "LIVE", "TRỰC", "TỶ LỆ", "KÈO", "CLICK", "VS", "ngy", "Sắp diễn ra", "HT", "FT"]
    for word in trash:
        name = re.sub(rf'\b{word}\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(?<![uU])\b\d+\b(?!\d)', '', name)
    name = re.sub(r"[^a-zA-Z0-9\s.()]", "", name)
    clean = " ".join(name.split())
    return clean if len(clean) > 1 else "TBA"

def get_stream_and_logos_full(driver, match_url, match_name):
    """Membuka halaman detail untuk SETIAP match guna menangkap data maksimal."""
    print(f"    [>] DEEP CHECK: {match_name}")
    data = {"stream": "Not Found", "t1_logo": "", "t2_logo": ""}
    try:
        driver.get(match_url)
        time.sleep(8) 

        # 1. Bersihkan Iklan Overlay
        driver.execute_script("document.querySelectorAll('.modal, .popup, .fixed, [id*=\"ads\"]').forEach(el => el.remove());")

        # 2. Ambil Logo HD dari Detail
        img_logos = driver.find_elements(By.CSS_SELECTOR, "div[class*='team_logo'] img, .team-logo img")
        if len(img_logos) >= 2:
            data["t1_logo"] = img_logos[0].get_attribute("src")
            data["t2_logo"] = img_logos[1].get_attribute("src")

        # 3. Force Interaction untuk pancing m3u8
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in iframes:
            if any(x in (frame.get_attribute("src") or "") for x in ["player", "stream", "embed"]):
                driver.switch_to.frame(frame)
                try:
                    video = driver.find_element(By.TAG_NAME, "video")
                    driver.execute_script("arguments[0].click();", video)
                except: pass
                break
        
        time.sleep(10)
        driver.switch_to.default_content()

        # 4. Tangkap dari Performance Logs
        logs = driver.get_log('performance')
        for entry in logs:
            msg = entry.get('message', '')
            if '.m3u8' in msg:
                url_match = re.search(r'"url":"(https://.*?\.m3u8.*?)"', msg)
                if url_match:
                    data["stream"] = url_match.group(1).replace('\\/', '/')
                    break
    except: pass
    return data

def jalankan_scraper():
    print(f"===== START FULL CHECK SCRAPER (NO FILTER) =====")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        time.sleep(15)

        # Scroll maksimal untuk memuat semua 177+ jadwal
        for _ in range(15):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        raw_list = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            if url and url not in seen_urls and len(card.text.strip()) > 10:
                raw_list.append({"url": url, "text": card.text.strip()})
                seen_urls.add(url)

        print(f"[*] Total {len(raw_list)} match ditemukan. Memeriksa satu per satu...")

        for item in raw_list:
            try:
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                clean_lines = []
                for l in lines:
                    if l.upper() in ["HT", "FT", "LIVE"] or re.match(r"^\d+('\+?\d*)?$", l): continue
                    if l.isdigit() and len(l) <= 2: continue
                    clean_lines.append(l)

                if len(clean_lines) < 3: continue
                liga, home, away = clean_lines[0], clean_team_name(clean_lines[1]), clean_team_name(clean_lines[2])

                # DEEP CHECK KE SEMUA LINK
                detail = get_stream_and_logos_full(driver, item["url"], f"{home} vs {away}")
                
                # Jam Pertandingan
                jam_match = re.search(r"(\d{2}:\d{2})\s+(\d{2}/\d{2})", item["text"])
                start_ts = int(datetime.strptime(f"{jam_match.group(1)} {jam_match.group(2)}/2026", "%H:%M %d/%m/%Y").replace(tzinfo=tz_jkt).timestamp() * 1000) if jam_match else int(time.time() * 1000)

                # Penentuan Status berdasarkan hasil temuan stream
                status = "live" if detail["stream"] != "Not Found" else "upcoming"

                hasil.append({
                    "channelName": f"[{liga}] {home} vs {away}",
                    "team1Name": home, "team1Logo": detail["t1_logo"] or "https://via.placeholder.com/150",
                    "team2Name": away, "team2Logo": detail["t2_logo"] or "https://via.placeholder.com/150",
                    "status": status,
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "streamUrl": detail["stream"],
                    "contentType": "event_pertandingan",
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/"
                })
                print(f"    [{status.upper()}] {home} vs {away}")
                
                driver.get(TARGET_URL)
                time.sleep(3)
            except: continue

    finally:
        driver.quit()

    if hasil:
        # Update Firebase
        fb_url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        requests.put(fb_url, json={"category_name": "EVENT1", "order": 15, "channels": {uuid.uuid4().hex: x for x in hasil}}, timeout=30)
        print(f"[√] SELESAI! {len(hasil)} match diproses.")

if __name__ == "__main__":
    jalankan_scraper()
