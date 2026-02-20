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
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://your-project.firebaseio.com")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET", "your-secret-key")
TARGET_URL = "https://bunchatv.net/truc-tiep"

# ID Kategori yang tetap (Agar di Firebase muncul sebagai "EVENT1", bukan -EVENT_xxxx)
FIXED_CATEGORY_ID = "EVENT1" 

def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""

def get_stream_and_league_logo(driver, match_url):
    league_logo = ""
    try:
        driver.get(match_url)
        time.sleep(6) # Ditambah agar lebih stabil
        driver.execute_script("document.querySelectorAll('.modal,.popup,.fixed,[id*=ads]').forEach(e=>e.remove());")

        logos = driver.find_elements(By.TAG_NAME, "img")
        for img in logos:
            src = get_img_src(img)
            alt = (img.get_attribute("alt") or "").lower()
            if src and ("logo" in alt or "league" in src or "tournament" in src):
                league_logo = src
                break

        # Iframe Player
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in iframes:
            src = frame.get_attribute("src") or ""
            if any(x in src for x in ["player", "embed", "stream", "live"]):
                driver.switch_to.frame(frame)
                break
        
        time.sleep(10) # Waktu tunggu m3u8 diperlama agar lebih banyak match tembus
        
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

    except Exception as e:
        print(f"   [!] Error: {e}")
    
    return "Not Found", league_logo

# ==============================
# FIREBASE - FIX: PUT MODE (MENGGANTI BUKAN MENAMBAH)
# ==============================
def kirim_ke_firebase(data):
    if not FIREBASE_URL or not FIREBASE_SECRET: return

    # Struktur kategori yang bersih
    category_payload = {
        "category_name": "EVENT1",
        "order": 1,
        "sourceUrl": TARGET_URL,
        "channels": {} 
    }

    count = 0
    for item in data:
        # PENTING: Jika link Not Found, kita tetap kirim (opsional) atau berikan link dummy
        # Agar jumlah yang terkirim tetap banyak sesuai temuan awal
        channel_key = uuid.uuid4().hex
        category_payload["channels"][channel_key] = item
        count += 1

    # Gunakan .json di akhir URL. Gunakan PUT untuk MENGHAPUS node lama.
    url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"

    print(f"Mengirim {count} pertandingan ke Firebase ID: {FIXED_CATEGORY_ID}")

    try:
        # PUT akan me-replace total node EVENT1
        res = requests.put(url, json=category_payload, timeout=30)
        if res.status_code == 200:
            print(f"[√] Berhasil! Data lama terhapus, data baru terpasang.")
        else:
            print(f"[!] Gagal: {res.status_code}")
    except Exception as e:
        print(f"[!] Error: {e}")

# ==============================
# JALANKAN SCRAPER - FIX: JAM AKURAT
# ==============================

tz_jkt = timezone(timedelta(hours=7))

def jalankan_scraper():
    print("\n===== START SCRAPER (FIXED TIME & NAME) =====\n")

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        # Tunggu hingga elemen card pertandingan muncul
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href,'truc-tiep')]"))
        )

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        initial_matches = []

        # Langkah 1: Kumpulkan data awal dari halaman utama
        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and len(teks) > 10:
                imgs = [get_img_src(img) for img in card.find_elements(By.TAG_NAME, "img")]
                initial_matches.append({"url": url, "text": teks, "imgs": imgs})

        print(f"Ditemukan {len(initial_matches)} match. Mulai proses detail...")

        # Langkah 2: Proses setiap match untuk ambil stream dan jam presisi
        for item in initial_matches:
            try:
                # Ambil Link Stream & Logo Liga
                stream_url, league_logo = get_stream_and_league_logo(driver, item["url"])
                
                # --- FIX LOGIKA JAM (STRATEGI GMT+7) ---
                page_text = driver.page_source
                time_match = re.search(r"(\d{2}:\d{2}).*?(\d{2}/\d{2})", page_text)
                
                # Gunakan tahun 2026 sebagai basis
                tahun_target = 2026 
                
                if time_match:
                    jam_str, tgl_str = time_match.group(1), time_match.group(2)
                    # Buat objek datetime dan paksa ke zona waktu Jakarta (GMT+7)
                    dt_naive = datetime.strptime(f"{jam_str} {tgl_str}/{tahun_target}", "%H:%M %d/%m/%Y")
                    dt_aware = dt_naive.replace(tzinfo=tz_jkt) 
                    start_ts = int(dt_aware.timestamp() * 1000)
                else:
                    # Fallback ke waktu sekarang jika jam tidak ditemukan
                    start_ts = int(datetime.now(tz_jkt).timestamp() * 1000)

                # --- FIX LOGIKA NAMA TIM (FILTER SKOR & MENIT) ---
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                clean_names = []
                for line in lines:
                    # Lewati jika: hanya angka (skor), ada petik (menit seperti 45'), atau HT/FT
                    if re.match(r"^\d+$", line): continue 
                    if "'" in line: continue
                    if line.upper() in ["HT", "FT", "LIVE"]: continue
                    if re.match(r"^\d{2}:\d{2}$", line): continue # Lewati jam di card utama
                    
                    clean_names.append(line)
                
                # Validasi: Minimal harus ada Liga, Tim Home, dan Tim Away
                if len(clean_names) >= 3:
                    liga = clean_names[0]
                    # Hilangkan angka skor yang mungkin menempel di depan nama tim
                    home = re.sub(r"^\d+\s+", "", clean_names[1])
                    away = re.sub(r"^\d+\s+", "", clean_names[2])
                    
                    # Tentukan status berdasarkan waktu sekarang
                    current_ts = int(datetime.now(tz_jkt).timestamp() * 1000)
                    status = "live" if start_ts <= current_ts else "upcoming"

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
                        "endTime": start_ts + 7200000, # Durasi 2 jam
                        "referer": "https://bunchatv.net/",
                        "streamUrl": stream_url,
                        "playerType": "internal_with_headers",
                        "userAgent": "Mozilla/5.0"
                    })
                    print(f"[OK] {home} vs {away} | Jam: {jam_str if time_match else 'Live'}")
                else:
                    print(f"[SKIP] Teks tidak lengkap: {clean_names}")

            except Exception as e:
                print(f"[!] Error detail match: {e}")

    finally:
        driver.quit()

    # Kirim hasil ke Firebase
    if hasil:
        kirim_ke_firebase(hasil)
    else:
        print("[!] Tidak ada data valid untuk dikirim.")

if __name__ == "__main__":
    jalankan_scraper()

