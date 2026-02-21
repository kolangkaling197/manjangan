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

# Keywords sampah untuk pembersihan nama tim
TRASH_WORDS = ["Trực tiếp", "Bóng đá", "Xem", "Live", "Hot", "Full", "Bình luận", "ngy", "Sắp diễn ra"]

def clean_team_name(name):
    """Membersihkan nama tim dari skor, kata sampah, dan simbol"""
    if not name: return "TBA"
    for word in TRASH_WORDS:
        name = re.sub(rf'\b{word}\b', '', name, flags=re.IGNORECASE)
    # Hapus angka skor tapi jaga label U23/U17
    name = re.sub(r'(?<![uU])\b\d+\b(?!\d)', '', name)
    name = re.sub(r"[^a-zA-Z0-9\s.()]", "", name)
    name = " ".join(name.split())
    return name if len(name) > 1 else "TBA"

def get_live_stream_only(driver, url):
    """Hanya digunakan untuk pertandingan LIVE: ambil m3u8 dan logo detail"""
    data = {"stream": "Not Found", "t1_logo": "", "t2_logo": ""}
    try:
        driver.get(url)
        time.sleep(8) # Waktu tunggu menangkap traffic network
        
        # Ambil m3u8 dari performance logs
        logs = driver.get_log("performance")
        for entry in logs:
            msg = entry.get("message", "")
            if ".m3u8" in msg:
                m = re.search(r'https://[^\\"]+\.m3u8[^\\"]*', msg)
                if m: 
                    data["stream"] = m.group(0).replace("\\/", "/")
                    break

        # Ambil Logo HD dari elemen scoreboard detail
        img_logos = driver.find_elements(By.CSS_SELECTOR, "div[class*='team_logo'] img, .team-logo img")
        if len(img_logos) >= 2:
            data["t1_logo"] = img_logos[0].get_attribute("src")
            data["t2_logo"] = img_logos[1].get_attribute("src")
    except: pass
    return data

def jalankan_scraper():
    print(f"===== START HYBRID SCRAPER: {TARGET_URL} =====")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    driver = uc.Chrome(options=options, version_main=144)
    hasil = []

    try:
        driver.get(TARGET_URL)
        print("[*] Menunggu halaman utama...")
        time.sleep(10)

        # Deep Scroll untuk memicu semua match muncul di tab 'Tất cả'
        print("[*] Scrolling untuk memicu Lazy Load...")
        for _ in range(12):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)

        # Ambil elemen kartu pertandingan menggunakan selector yang stabil
        match_cards = driver.find_elements(By.XPATH, "//a[contains(@href, 'truc-tiep')]") 
        print(f"[*] Ditemukan {len(match_cards)} potensi pertandingan.")

        # Simpan URL agar tidak memproses ganda saat navigasi back-forth
        card_data_list = []
        for card in match_cards:
            try:
                txt = card.text.strip()
                href = card.get_attribute("href")
                imgs = [i.get_attribute("src") for i in card.find_elements(By.TAG_NAME, "img")]
                if href and len(txt) > 10:
                    card_data_list.append({"url": href, "text": txt, "imgs": imgs})
            except: continue

        for item in card_data_list:
            try:
                is_live_label = "Live" in item["text"]
                
                # Parsing data dasar dari teks kartu
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                if len(lines) < 3: continue
                
                liga = lines[0]
                home_raw = lines[1]
                away_raw = lines[2]
                
                # Deteksi Jam Pertandingan dari kartu
                jam_match = re.search(r"(\d{2}:\d{2})\s+(\d{2}/\d{2})", item["text"])
                if jam_match:
                    dt_str = f"{jam_match.group(1)} {jam_match.group(2)}/2026"
                    start_ts = int(datetime.strptime(dt_str, "%H:%M %d/%m/%Y").replace(tzinfo=tz_jkt).timestamp() * 1000)
                else:
                    start_ts = int(datetime.now(tz_jkt).timestamp() * 1000)

                # Logo default dari halaman utama
                t1_logo = item["imgs"][0] if len(item["imgs"]) > 0 else ""
                t2_logo = item["imgs"][1] if len(item["imgs"]) > 1 else ""

                stream_url = "Not Found"
                status_final = "upcoming"

                # LOGIKA HYBRID:
                if is_live_label:
                    # HANYA BUKA DETAIL JIKA LIVE untuk ambil m3u8
                    detail = get_live_stream_only(driver, item["url"])
                    stream_url = detail["stream"]
                    status_final = "live" if stream_url != "Not Found" else "upcoming"
                    # Update logo jika di detail ada yang lebih valid
                    if detail["t1_logo"]: t1_logo = detail["t1_logo"]
                    if detail["t2_logo"]: t2_logo = detail["t2_logo"]
                    # Kembali ke halaman utama setelah dari detail
                    driver.get(TARGET_URL)
                    time.sleep(3)
                else:
                    # JIKA UPCOMING (Sắp diễn ra): Langsung pakai data kartu (Cepat & Anti-TBA)
                    status_final = "upcoming"

                home = clean_team_name(home_raw)
                away = clean_team_name(away_raw)

                hasil.append({
                    "channelName": f"[{liga}] {home} vs {away}",
                    "team1Name": home, "team1Logo": t1_logo,
                    "team2Name": away, "team2Logo": t2_logo,
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "status": status_final,
                    "streamUrl": stream_url,
                    "contentType": "event_pertandingan",
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/"
                })
                print(f"   [{status_final.upper()}] {home} vs {away}")

            except Exception as e:
                print(f"   [!] Gagal item: {e}")
                continue

    finally:
        driver.quit()

    if hasil:
        # Kirim ke Firebase (PUT untuk overwrite data lama)
        fb_url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        payload = {
            "category_name": "EVENT1",
            "order": 15,
            "channels": {uuid.uuid4().hex: x for x in hasil}
        }
        requests.put(fb_url, json=payload, timeout=30)
        print(f"[√] BERHASIL! {len(hasil)} match (Live & Soon) terdaftar di Firebase.")

if __name__ == "__main__":
    jalankan_scraper()
