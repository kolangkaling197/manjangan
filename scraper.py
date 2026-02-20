import os
import requests
import time
import re
import uuid
import undetected_chromedriver as uc
from datetime import datetime
from selenium.webdriver.common.by import By

# ==============================
# KONFIGURASI
# ==============================

FIREBASE_URL = os.getenv("FIREBASE_URL")
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"

# Mapping logo liga (lebih stabil daripada scraping)
LEAGUE_LOGO_MAP = {
    "Ukrainian Youth Team Championship": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
    "Myanmar Professional League": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
    "National Premier Leagues Victoria": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
    "International Match": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
}

# ==============================
# AMBIL STREAM LINK + LOGO LIGA
# ==============================

def get_stream_and_league_logo(driver, match_url, liga):
    print("   [>] Membuka halaman match")

    try:
        driver.get(match_url)
        time.sleep(5)

        driver.execute_script("""
            document.querySelectorAll('.modal,.popup,.fixed,[id*=ads]').forEach(e=>e.remove());
        """)

        # paksa video play supaya m3u8 muncul
        driver.execute_script("""
            var vids = document.querySelectorAll("video");
            vids.forEach(v => { v.muted=true; v.play().catch(()=>{}); });
        """)

        time.sleep(10)

        # 1️⃣ Ambil dari performance log
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                msg = entry.get("message", "")
                if ".m3u8" in msg:
                    m = re.search(r'"url":"(https://.*?\.m3u8.*?)"', msg)
                    if m:
                        return m.group(1).replace("\\/", "/"), LEAGUE_LOGO_MAP.get(liga, "")
        except:
            pass

        # 2️⃣ Fallback dari HTML
        html = driver.page_source
        m = re.search(r"https://[^\"']+\.m3u8[^\"']*", html)
        if m:
            return m.group(0), LEAGUE_LOGO_MAP.get(liga, "")

    except Exception as e:
        print("   [!] Error ambil stream:", e)

    return "Not Found", LEAGUE_LOGO_MAP.get(liga, "")

# ==============================
# KIRIM KE FIREBASE
# ==============================

def kirim_ke_firebase(data):
    if not FIREBASE_URL:
        print("[!] FIREBASE_URL tidak ditemukan")
        return

    playlist = {}
    now = int(time.time() * 1000)

    for item in data:
        if item["streamUrl"] == "Not Found":
            continue

        key = uuid.uuid4().hex

        playlist[key] = item

    url = f"{FIREBASE_URL}/playlist.json"
    res = requests.put(url, json=playlist, timeout=20)

    if res.status_code == 200:
        print("[√] Data berhasil dikirim ke Firebase")
    else:
        print("[!] Gagal kirim:", res.text)

# ==============================
# SCRAPER UTAMA
# ==============================

def jalankan_scraper():
    print("\n========== START SCRAPER ==========\n")

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = uc.Chrome(
    options=options,
    use_subprocess=True
    )

    hasil = []

    try:
        driver.get(TARGET_URL)
        time.sleep(10)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")

        for card in cards:
            try:
                url = card.get_attribute("href")
                teks = card.text.strip()

                if not url or len(teks) < 10:
                    continue

                imgs = [img.get_attribute("src") for img in card.find_elements(By.TAG_NAME, "img")]

                lines = [l.strip() for l in teks.split("\n") if l.strip()]
                if len(lines) < 2:
                    continue

                liga = lines[0]
                home = lines[1]
                away = lines[2] if len(lines) > 2 else ""

                team1_logo = imgs[0] if len(imgs) > 0 else ""
                team2_logo = imgs[1] if len(imgs) > 1 else ""

                stream_url, league_logo = get_stream_and_league_logo(driver, url, liga)

                now = int(time.time() * 1000)

                hasil.append({
                    "channelName": f"[{liga}] {home} vs {away}",
                    "leagueName": liga,
                    "leagueLogo": league_logo,

                    "team1Name": home,
                    "team1Logo": team1_logo,

                    "team2Name": away,
                    "team2Logo": team2_logo,

                    "channelLogo": league_logo,

                    "contentType": "event_pertandingan",
                    "description": "LIVE",
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/",
                    "userAgent": "Mozilla/5.0",

                    "status": "live",
                    "startTime": now,
                    "endTime": now + 7200000,
                    "order": now,

                    "streamUrl": stream_url
                })

                print(f"[OK] {home} vs {away}")

            except Exception as e:
                print("[!] Error proses match:", e)

    except Exception as e:
        print("[!] ERROR UTAMA:", e)

    finally:
        driver.quit()

    if hasil:
        kirim_ke_firebase(hasil)
    else:
        print("[!] Tidak ada data dikirim")

# ==============================

if __name__ == "__main__":
    jalankan_scraper()

