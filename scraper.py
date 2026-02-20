import os
import requests
import time
import re
import uuid
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==============================
# KONFIGURASI
# ==============================

FIREBASE_URL = os.getenv("FIREBASE_URL")
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"

LEAGUE_LOGO_MAP = {
    "Ukrainian Youth Team Championship": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
    "Myanmar Professional League": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
    "National Premier Leagues Victoria": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
    "International Match": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
}

# ==============================
# AMBIL STREAM LINK
# ==============================

def get_stream_and_league_logo(driver, match_url, liga):

    league_logo = LEAGUE_LOGO_MAP.get(liga, "")

    try:
        driver.get(match_url)
        time.sleep(5)

        driver.execute_script("""
            document.querySelectorAll('.modal,.popup,.fixed,[id*=ads]').forEach(e=>e.remove());
        """)

        # Masuk iframe jika ada
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in iframes:
            src = frame.get_attribute("src") or ""
            if any(x in src for x in ["player", "embed", "stream", "live"]):
                driver.switch_to.frame(frame)
                break

        # Paksa play
        driver.execute_script("""
            var vids = document.querySelectorAll("video");
            vids.forEach(v => { v.muted = true; v.play().catch(()=>{}); });
        """)

        time.sleep(10)
        driver.switch_to.default_content()

        # Ambil dari performance log
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                msg = entry.get("message", "")
                if ".m3u8" in msg:
                    m = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', msg)
                    if m:
                        return m.group(0).replace("\\/", "/"), league_logo
        except:
            pass

        # Fallback HTML
        html = driver.page_source
        m = re.search(r"https://[^\s\"']+\.m3u8[^\s\"']*", html)
        if m:
            return m.group(0), league_logo

    except Exception as e:
        print("   [!] Error stream:", e)

    return "Not Found", league_logo


# ==============================
# KIRIM FIREBASE
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
        print("[√] Data berhasil dikirim")
    else:
        print("[!] Gagal kirim:", res.text)


# ==============================
# SCRAPER UTAMA
# ==============================

def jalankan_scraper():

    print("\n===== START SCRAPER =====\n")

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = uc.Chrome(
        options=options,
        version_main=144,
        use_subprocess=True
    )

    hasil = []

    try:
        driver.get(TARGET_URL)

        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//a[contains(@href,'truc-tiep')]")
            )
        )

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")

        # SIMPAN URL SAJA (ANTI STALE)
        match_list = []

        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()

            if url and len(teks) > 10:
                imgs = [img.get_attribute("src") for img in card.find_elements(By.TAG_NAME, "img")]
                match_list.append({
                    "url": url,
                    "text": teks,
                    "imgs": imgs
                })

        print(f"Total match ditemukan: {len(match_list)}")

        # Loop pakai data statis
        for item in match_list:
            try:
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                if len(lines) < 2:
                    continue

                liga = lines[0]
                home = lines[1]
                away = lines[2] if len(lines) > 2 else ""

                team1_logo = item["imgs"][0] if len(item["imgs"]) > 0 else ""
                team2_logo = item["imgs"][1] if len(item["imgs"]) > 1 else ""

                stream_url, league_logo = get_stream_and_league_logo(
                    driver,
                    item["url"],
                    liga
                )

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
                print("[!] Error match:", e)

    except Exception as e:
        print("[!] ERROR UTAMA:", e)

    finally:
        driver.quit()

    if hasil:
        kirim_ke_firebase(hasil)
    else:
        print("[!] Tidak ada data")


if __name__ == "__main__":
    jalankan_scraper()
