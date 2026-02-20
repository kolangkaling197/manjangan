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
# Ganti dengan URL dan Secret Firebase Anda
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://your-project.firebaseio.com")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET", "your-secret-key")
TARGET_URL = "https://bunchatv.net/truc-tiep"

# ID Kategori yang tetap agar tidak membuat kategori baru di Firebase
# Pastikan ID ini sesuai dengan yang dibaca oleh aplikasi Android Anda
FIXED_CATEGORY_ID = "EVENT1" 

# ==============================
# UTIL AMBIL SRC IMAGE
# ==============================
def get_img_src(img):
    return img.get_attribute("src") or img.get_attribute("data-src") or ""

# ==============================
# AMBIL STREAM + LOGO LIGA (HALAMAN DETAIL)
# ==============================
def get_stream_and_league_logo(driver, match_url):
    league_logo = ""
    try:
        driver.get(match_url)
        time.sleep(5)
        
        # Bersihkan overlay iklan
        driver.execute_script("document.querySelectorAll('.modal,.popup,.fixed,[id*=ads]').forEach(e=>e.remove());")

        # Scrape Logo Liga (mencari elemen gambar yang mengandung kata 'logo' atau 'league')
        logos = driver.find_elements(By.TAG_NAME, "img")
        for img in logos:
            src = get_img_src(img)
            alt = (img.get_attribute("alt") or "").lower()
            if "logo" in alt and src:
                league_logo = src
                break

        # Cari Iframe Player untuk mentrigger stream
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in iframes:
            src = frame.get_attribute("src") or ""
            if any(x in src for x in ["player", "embed", "stream", "live"]):
                driver.switch_to.frame(frame)
                break
        
        time.sleep(8) # Tunggu log jaringan muncul
        
        # Ambil .m3u8 dari Performance Logs
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

        # Fallback: Cari di Page Source
        html = driver.page_source
        m = re.search(r"https://[^\s\"']+\.m3u8[^\s\"']*", html)
        if m:
            return m.group(0), league_logo

    except Exception as e:
        print(f"   [!] Error detail match: {e}")
    
    return "Not Found", league_logo

# ==============================
# KIRIM KE FIREBASE (AUTO-REPLACE)
# ==============================
def kirim_ke_firebase(data):
    if not FIREBASE_URL or not FIREBASE_SECRET:
        print("[!] Konfigurasi Firebase tidak lengkap")
        return

    # 1. Gunakan ID tetap, JANGAN pakai timestamp atau UUID untuk kategori
    # Ini akan mencegah terciptanya node baru seperti -EVENT_177160...
    category_key = "EVENT1" 

    # 2. Siapkan struktur kategori
    category_payload = {
        "category_name": "LIVE MATCH",
        "order": 1,
        "sourceUrl": TARGET_URL,
        "channels": {} 
    }

    # 3. Masukkan semua hasil scrap ke dalam node channels
    for item in data:
        if item["streamUrl"] == "Not Found":
            continue
        
        # ID unik hanya untuk setiap pertandingan di dalam kategori
        channel_key = uuid.uuid4().hex
        category_payload["channels"][channel_key] = item

    # 4. TARGET URL: Langsung menuju ke folder kategori EVENT1
    # Menambahkan .json adalah syarat REST API Firebase
    url = f"{FIREBASE_URL}/playlist/{category_key}.json?auth={FIREBASE_SECRET}"

    print(f"Mengupdate Firebase (Menimpa data lama): {category_key}")

    try:
        # PENTING: Gunakan requests.put()
        # PUT akan MENGHAPUS isi EVENT1 yang lama dan MENGGANTINYA dengan yang baru
        res = requests.put(url, json=category_payload, timeout=25)
        
        if res.status_code == 200:
            print(f"[√] Berhasil! Kategori {category_key} telah di-reset dan diperbarui.")
        else:
            print(f"[!] Gagal kirim: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[!] Error koneksi Firebase: {e}")
# ==============================
# MAIN SCRAPER
# ==============================
def jalankan_scraper():
    print("\n===== SCRAPER START (FIXED MODE) =====\n")

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href,'truc-tiep')]"))
        )

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        match_list = []

        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and len(teks) > 10:
                imgs = [get_img_src(img) for img in card.find_elements(By.TAG_NAME, "img")]
                match_list.append({"url": url, "text": teks, "imgs": imgs})

        for item in match_list:
            try:
                # 1. Ambil Stream & Source
                stream_url, league_logo = get_stream_and_league_logo(driver, item["url"])
                
                # 2. Ambil Jam Mulai dari Halaman Detail (FIX REGEX)
                page_text = driver.page_source
                # Mencari pola XX:XX ... XX/XX (Jam dan Tanggal)
                time_match = re.search(r"(\d{2}:\d{2}).*?(\d{2}/\d{2})", page_text)
                
                now_dt = datetime.now()
                if time_match:
                    jam_menit = time_match.group(1) # Contoh: "00:30"
                    tgl_bln = time_match.group(2)   # Contoh: "21/02"
                    try:
                        # Gabungkan jam, tanggal, dan tahun sekarang
                        start_dt = datetime.strptime(f"{jam_menit} {tgl_bln}/{now_dt.year}", "%H:%M %d/%m/%Y")
                        start_ts = int(start_dt.timestamp() * 1000)
                    except:
                        start_ts = int(time.time() * 1000)
                else:
                    start_ts = int(time.time() * 1000)

                # 3. Bersihkan Nama Tim
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                clean_lines = [l for l in lines if not re.match(r"^\d{2}:\d{2}$", l) and not l.isdigit()]
                
                if len(clean_lines) >= 3:
                    liga, home, away = clean_lines[0], clean_lines[1], clean_lines[2]
                else:
                    continue

                hasil.append({
                    "channelName": f"[{liga}] {home} vs {away}",
                    "leagueName": liga,
                    "leagueLogo": league_logo,
                    "team1Name": home,
                    "team1Logo": item["imgs"][0] if len(item["imgs"]) > 0 else "",
                    "team2Name": away,
                    "team2Logo": item["imgs"][1] if len(item["imgs"]) > 1 else "",
                    "contentType": "event_pertandingan",
                    "status": "live" if start_ts <= (time.time()*1000) else "upcoming",
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "referer": "https://bunchatv.net/",
                    "streamUrl": stream_url,
                    "playerType": "internal_with_headers",
                    "userAgent": "Mozilla/5.0"
                })
                print(f"[OK] {home} vs {away} | Waktu: {jam_menit if time_match else 'Live'}")

            except Exception as e:
                print(f"[!] Error match: {e}")

    finally:
        driver.quit()

    if hasil:
        kirim_ke_firebase(hasil)
    else:
        print("[!] Tidak ada data untuk dikirim.")

if __name__ == "__main__":
    jalankan_scraper()

