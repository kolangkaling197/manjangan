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
    """Pembersihan nama tim dari sampah teks dan status waktu."""
    if not name: return "TBA"
    trash = ["CƯỢC", "XEM", "LIVE", "TRỰC", "TỶ LỆ", "KÈO", "CLICK", "VS", "ngy", "Sắp diễn ra", "HT", "FT"]
    for word in trash:
        name = re.sub(rf'\b{word}\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(?<![uU])\b\d+\b(?!\d)', '', name)
    name = re.sub(r"[^a-zA-Z0-9\s.()]", "", name)
    return " ".join(name.split())

def get_stream_and_logos_full(driver, match_url, match_name):
    """Logika interaksi paksa untuk memaksimalkan penangkapan m3u8."""
    print(f"    [>] DEEP CHECK: {match_name}")
    data = {"stream": "Not Found", "t1_logo": "", "t2_logo": ""}
    try:
        driver.get(match_url)
        time.sleep(10) # Tunggu loading awal lebih lama

        # 1. Bersihkan Iklan Overlay secara agresif
        driver.execute_script("""
            var ads = document.querySelectorAll('.modal, .popup, .fixed, [id*="ads"], .sh-overlay');
            ads.forEach(el => el.remove());
        """)

        # 2. Ambil Logo HD
        img_logos = driver.find_elements(By.CSS_SELECTOR, "div[class*='team_logo'] img, .team-logo img")
        if len(img_logos) >= 2:
            data["t1_logo"] = img_logos[0].get_attribute("src")
            data["t2_logo"] = img_logos[1].get_attribute("src")

        # 3. Paksa klik di area player dan pindah iframe
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                src = frame.get_attribute("src") or ""
                if any(x in src for x in ["player", "stream", "embed", "bitmovin"]):
                    driver.switch_to.frame(frame)
                    # Klik elemen video atau tombol play di dalam iframe
                    driver.execute_script("""
                        var v = document.querySelector('video') || document.querySelector('.play-button');
                        if(v) v.click();
                    """)
                    break
        except: pass
        
        print("    [>] Menunggu traffic m3u8 (20 detik)...")
        time.sleep(20) # Waktu krusial untuk menangkap stream
        driver.switch_to.default_content()

        # 4. Tangkap dari Performance Logs
        logs = driver.get_log('performance')
        for entry in logs:
            msg = entry.get('message', '')
            if '.m3u8' in msg:
                url_match = re.search(r'"url":"(https://.*?\.m3u8.*?)"', msg)
                if url_match:
                    data["stream"] = url_match.group(1).replace('\\/', '/')
                    print(f"    [√] m3u8 FOUND!")
                    break
    except: pass
    return data

def jalankan_scraper():
    print(f"===== START FULL CHECK SCRAPER (ALL MATCHES) =====")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        time.sleep(15)

        # Scroll dalam untuk load semua konten
        for _ in range(15):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        raw_list = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            txt = card.text.strip()
            if url and url not in seen_urls and len(txt) > 10:
                raw_list.append({"url": url, "text": txt})
                seen_urls.add(url)

        print(f"[*] Total {len(raw_list)} match ditemukan. Memproses...")

        for item in raw_list:
            try:
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                clean_lines = []
                for l in lines:
                    if l.upper() in ["HT", "FT", "LIVE"] or re.match(r"^\d+('\+?\d*)?$", l): continue
                    if l.isdigit() and len(l) <= 2: continue
                    clean_lines.append(l)

                if len(clean_lines) < 3: continue
                liga, h_raw, a_raw = clean_lines[0], clean_lines[1], clean_lines[2]
                home, away = clean_team_name(h_raw), clean_team_name(a_raw)

                # Jalankan Deep Check ke semua halaman
                detail = get_stream_and_logos_full(driver, item["url"], f"{home} vs {away}")
                
                # Deteksi Waktu
                jam_match = re.search(r"(\d{2}:\d{2})\s+(\d{2}/\d{2})", item["text"])
                start_ts = int(datetime.strptime(f"{jam_match.group(1)} {jam_match.group(2)}/2026", "%H:%M %d/%m/%Y").replace(tzinfo=tz_jkt).timestamp() * 1000) if jam_match else int(time.time() * 1000)

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
        # Kirim ke Firebase
        fb_url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        requests.put(fb_url, json={"category_name": "EVENT15", "order": 1, "channels": {uuid.uuid4().hex: x for x in hasil}}, timeout=30)
        print(f"[√] SELESAI! {len(hasil)} match diproses.")

if __name__ == "__main__":
    jalankan_scraper()
