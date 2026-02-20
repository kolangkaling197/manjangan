import os
import requests
import time
import re
import uuid
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==============================
# KONFIGURASI
# ==============================
# Gunakan Environment Variables atau isi langsung jika testing
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://your-project.firebaseio.com")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET", "your-secret-key")
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"

# Fallback logo jika logo liga tidak ditemukan di halaman
LEAGUE_LOGO_MAP = {
    "Ukrainian Youth Team Championship": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
    "Myanmar Professional League": "https://cdn-icons-png.flaticon.com/512/53/53283.png",
}

# ==============================
# UTIL AMBIL SRC IMAGE (ANTI LAZY LOAD)
# ==============================
def get_img_src(img):
    return (
        img.get_attribute("src")
        or img.get_attribute("data-src")
        or ""
    )

# ==============================
# AMBIL STREAM + LOGO LIGA (HALAMAN DETAIL)
# ==============================
def get_stream_and_league_logo(driver, match_url, liga):
    league_logo = ""
    try:
        driver.get(match_url)
        time.sleep(5)

        # Hapus overlay/ads agar tidak mengganggu performance log
        driver.execute_script("""
            document.querySelectorAll('.modal,.popup,.fixed,[id*=ads]').forEach(e=>e.remove());
        """)

        # Scrape Logo Liga berdasarkan 'alt' text
        logos = driver.find_elements(By.TAG_NAME, "img")
        for img in logos:
            alt = (img.get_attribute("alt") or "").lower()
            src = get_img_src(img)
            if liga.lower() in alt and src:
                league_logo = src
                break

        if not league_logo:
            league_logo = LEAGUE_LOGO_MAP.get(liga, "https://cdn-icons-png.flaticon.com/512/53/53283.png")

        # Cari Iframe Player
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in iframes:
            src = frame.get_attribute("src") or ""
            if any(x in src for x in ["player", "embed", "stream", "live"]):
                driver.switch_to.frame(frame)
                break

        # Tunggu buffer stream
        time.sleep(10)
        
        # Ambil link .m3u8 dari log jaringan
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

        # Fallback: Cari di HTML mentah
        html = driver.page_source
        m = re.search(r"https://[^\s\"']+\.m3u8[^\s\"']*", html)
        if m:
            return m.group(0), league_logo

    except Exception as e:
        print(f"   [!] Gagal ambil detail: {e}")

    return "Not Found", league_logo

# ==============================
# KIRIM KE FIREBASE
# ==============================
def kirim_ke_firebase(data):
    if not FIREBASE_URL or not FIREBASE_SECRET:
        print("[!] Konfigurasi Firebase tidak lengkap!")
        return

    now = int(time.time() * 1000)
    category_key = "-EVENT_" + str(now)

    payload = {
        category_key: {
            "category_name": "EVENT1",
            "order": 15,
            "sourceUrl": TARGET_URL,
            "channels": {}
        }
    }

    for item in data:
        if item["streamUrl"] == "Not Found":
            continue
        channel_key = uuid.uuid4().hex
        payload[category_key]["channels"][channel_key] = item

    url = f"{FIREBASE_URL}/playlist.json?auth={FIREBASE_SECRET}"
    print(f"Updating Firebase: {url}")
    
    res = requests.patch(url, json=payload, timeout=25)
    
    if res.status_code == 200:
        print("[√] Berhasil kirim data ke Firebase")
    else:
        print(f"[!] Gagal kirim: {res.status_code}")

# ==============================
# MAIN SCRAPER
# ==============================
def jalankan_scraper():
    print("\n===== SCRAPER BUNCHATV STARTING =====\n")

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        
        # Tunggu sampai link pertandingan muncul
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href,'truc-tiep')]"))
        )

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        match_list = []

        # List match sementara
        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and len(teks) > 10:
                imgs = [get_img_src(img) for img in card.find_elements(By.TAG_NAME, "img")]
                match_list.append({"url": url, "text": teks, "imgs": imgs})

        print(f"Menemukan {len(match_list)} potensi pertandingan.\n")

        for item in match_list:
            try:
                # Parsing Teks Card
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                clean_lines = []
                jam_mulai_str = ""

                for l in lines:
                    # Deteksi Jam (HH:mm)
                    if re.match(r"^\d{2}:\d{2}$", l):
                        jam_mulai_str = l
                        continue
                    
                    # Bersihkan Menit Pertandingan & Skor
                    if re.match(r"^\d+('\+?\d*)?$", l) or (l.isdigit() and len(l) <= 2):
                        continue

                    clean_lines.append(l)

                if len(clean_lines) < 3: continue

                liga = clean_lines[0]
                home = clean_lines[1]
                away = clean_lines[2]

                # Konversi Waktu ke Unix Timestamp (milidetik)
                now_dt = datetime.now()
                if jam_mulai_str:
                    # Gabung tanggal hari ini + jam dari web
                    start_dt = datetime.strptime(f"{now_dt.strftime('%Y-%m-%d')} {jam_mulai_str}", "%Y-%m-%d %H:%M")
                    start_ts = int(start_dt.timestamp() * 1000)
                else:
                    start_ts = int(time.time() * 1000)

                # Ambil Link Stream (M3U8)
                stream_url, league_logo = get_stream_and_league_logo(driver, item["url"], liga)

                # Siapkan Payload JSON (Key sinkron dengan Channel.java Anda)
                match_data = {
                    "channelName": f"[{liga}] {home} vs {away}",
                    "leagueName": liga,
                    "leagueLogo": league_logo,
                    "team1Name": home,
                    "team1Logo": item["imgs"][0] if len(item["imgs"]) > 0 else "",
                    "team2Name": away,
                    "team2Logo": item["imgs"][1] if len(item["imgs"]) > 1 else "",
                    "contentType": "event_pertandingan",
                    "description": "LIVE",
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/",
                    "userAgent": "Mozilla/5.0",
                    "status": "live" if start_ts <= (time.time() * 1000) else "upcoming",
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000, # +2 Jam
                    "order": start_ts,
                    "streamUrl": stream_url
                }
                
                hasil.append(match_data)
                print(f"[OK] {jam_mulai_str or 'Live'} - {home} vs {away}")

            except Exception as e:
                print(f"[!] Gagal proses match: {e}")

    finally:
        driver.quit()

    if hasil:
        kirim_ke_firebase(hasil)
    else:
        print("[!] Tidak ada data untuk dikirim.")

if __name__ == "__main__":
    jalankan_scraper()
