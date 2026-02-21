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
    """Pembersihan nama tim dari skor dan teks sampah."""
    if not name: return "TBA"
    trash = ["CƯỢC", "XEM", "LIVE", "TRỰC", "TỶ LỆ", "KÈO", "CLICK", "VS", "ngy", "Sắp diễn ra"]
    for word in trash:
        name = re.sub(rf'\b{word}\b', '', name, flags=re.IGNORECASE)
    # Hapus angka skor tapi jaga label U23/U17
    name = re.sub(r'(?<![uU])\b\d+\b(?!\d)', '', name)
    name = re.sub(r"[^a-zA-Z0-9\s.()]", "", name)
    return " ".join(name.split())

def get_live_stream_link_enhanced(driver, match_url, match_name):
    """Membuka halaman detail, membersihkan iklan, dan menangkap m3u8 melalui logs."""
    print(f"    [>] PROSES STREAM: {match_name}")
    try:
        driver.get(match_url)
        time.sleep(7)

        # 1. Bersihkan Iklan Overlay yang menghalangi player
        driver.execute_script("""
            var ads = document.querySelectorAll('[id*="ads"], [class*="ads"], [style*="z-index: 9999"], .sh-overlay, .modal');
            ads.forEach(ad => ad.remove());
        """)

        # 2. Pindah ke iframe player jika ada
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for i, frame in enumerate(iframes):
            src = frame.get_attribute("src") or ""
            if any(x in src for x in ["bitmovin", "player", "stream", "embed"]):
                driver.switch_to.frame(frame)
                print(f"    [>] Berpindah ke iframe #{i}")
                break

        # 3. Klik area video untuk memancing m3u8 keluar di network traffic
        try:
            video_el = driver.find_elements(By.XPATH, "//video | //div[@id='player'] | //div[contains(@class, 'play')]")
            if video_el:
                driver.execute_script("arguments[0].click();", video_el[0])
        except: pass

        print("    [>] Menunggu traffic network (15 detik)...")
        time.sleep(15)
        
        driver.switch_to.default_content()
        
        # 4. Tangkap dari Performance Logs
        logs = driver.get_log('performance')
        for entry in logs:
            msg = entry.get('message', '')
            if '.m3u8' in msg:
                # Regex untuk mengekstrak URL m3u8 dari pesan log json
                url_match = re.search(r'"url":"(https://.*?\.m3u8.*?)"', msg)
                if url_match:
                    stream_url = url_match.group(1).replace('\\/', '/')
                    if "ads" not in stream_url.lower():
                        print(f"    [√] LOG FOUND: m3u8 Captured!")
                        return stream_url
    except Exception as e:
        print(f"    [!] Error stream capture: {e}")
    return "Not Found"

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
        print("[*] Menunggu halaman utama stabil...")
        time.sleep(15)

        # Deep Scroll untuk memicu Lazy Load konten di halaman utama
        for _ in range(12):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)

        cards = driver.find_elements(By.XPATH, "//a[contains(@href,'truc-tiep')]")
        raw_list = []
        seen_urls = set()

        for card in cards:
            url = card.get_attribute("href")
            teks = card.text.strip()
            if url and url not in seen_urls and len(teks) > 10:
                # Mengambil logo tim dari kartu di halaman utama sebagai fallback
                imgs = [img.get_attribute("src") or img.get_attribute("data-src") for img in card.find_elements(By.TAG_NAME, "img")]
                raw_list.append({"url": url, "text": teks, "imgs": imgs})
                seen_urls.add(url)

        print(f"[*] Berhasil menarik {len(raw_list)} daftar pertandingan.")

        for item in raw_list:
            try:
                # Cek apakah pertandingan sedang Live berdasarkan label teks
                is_live_label = "Live" in item["text"]
                lines = [l.strip() for l in item["text"].split("\n") if l.strip()]
                
                # Filter menit/skor untuk mendapatkan nama liga dan tim secara bersih
                clean_lines = []
                for l in lines:
                    if re.match(r"^\d+('\+?\d*)?$", l): continue 
                    if l.isdigit() and len(l) <= 2: continue 
                    clean_lines.append(l)

                if len(clean_lines) < 3: continue
                liga, home_raw, away_raw = clean_lines[0], clean_lines[1], clean_lines[2]
                
                home = clean_team_name(home_raw)
                away = clean_team_name(away_raw)
                stream_url = "Not Found"
                status = "upcoming"

                # LOGIKA HYBRID: Hanya buka detail jika LIVE untuk menangkap stream
                if is_live_label:
                    stream_url = get_live_stream_link_enhanced(driver, item["url"], f"{home} vs {away}")
                    status = "live" if stream_url != "Not Found" else "upcoming"
                    driver.get(TARGET_URL) # Kembali ke menu utama untuk memproses item selanjutnya
                    time.sleep(3)
                else:
                    status = "upcoming"

                # Deteksi Jam pertandingan dari teks kartu (Format: HH:mm DD/MM)
                jam_match = re.search(r"(\d{2}:\d{2})\s+(\d{2}/\d{2})", item["text"])
                if jam_match:
                    dt_str = f"{jam_match.group(1)} {jam_match.group(2)}/2026"
                    start_ts = int(datetime.strptime(dt_str, "%H:%M %d/%m/%Y").replace(tzinfo=tz_jkt).timestamp() * 1000)
                else:
                    start_ts = int(time.time() * 1000)

                hasil.append({
                    "channelName": f"[{liga}] {home} vs {away}",
                    "team1Name": home, "team1Logo": item["imgs"][0] if len(item["imgs"]) > 0 else "",
                    "team2Name": away, "team2Logo": item["imgs"][1] if len(item["imgs"]) > 1 else "",
                    "status": status,
                    "startTime": start_ts,
                    "endTime": start_ts + 7200000,
                    "streamUrl": stream_url,
                    "contentType": "event_pertandingan",
                    "playerType": "internal_with_headers",
                    "referer": "https://bunchatv.net/"
                })
                print(f"    [{status.upper()}] {home} vs {away}")
            except Exception as e:
                print(f"    [!] Gagal memproses {item['url']}: {e}")
                continue

    finally:
        driver.quit()

    if hasil:
        # Kirim ke Firebase menggunakan metode PUT (overwrite kategori EVENT1)
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
