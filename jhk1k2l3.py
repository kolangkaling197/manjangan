import os
import json
import time
import re
import uuid
import logging
import requests
import subprocess
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta, timezone
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- 1. KONFIGURASI ---
FIREBASE_URL = os.getenv("FIREBASE_URL")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET")
TARGET_URL = "https://bunchatv.net/truc-tiep-bong-da-xoilac-tv"
FIXED_CATEGORY_ID = "AJ_JKS"
tz_jkt = timezone(timedelta(hours=7))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# --- 2. FUNGSI PEMBANTU ---

def get_chrome_main_version():
    try:
        output = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
        version = re.search(r'Chrome (\d+)', output).group(1)
        return int(version)
    except:
        return None

def get_detailed_info(driver, match_page_url):
    """Mengambil startTime dari Title halaman detail."""
    try:
        driver.set_page_load_strategy('eager')
        driver.get(match_page_url)
        
        # Tunggu title load, max 10 detik
        WebDriverWait(driver, 10).until(
            lambda d: d.title != "" and d.title != "about:blank"
        )
        
        page_title = driver.title
        match = re.search(r'(\d{2}:\d{2}).*?(\d{2}/\d{2})', page_title)
        
        if match:
            jam, tgl_bln = match.group(1), match.group(2)
            current_year = datetime.now(tz_jkt).year
            dt_obj = datetime.strptime(f"{tgl_bln}/{current_year} {jam}", "%d/%m/%Y %H:%M").replace(tzinfo=tz_jkt)
            start_ms = int(dt_obj.timestamp() * 1000)
            
            hari_id = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
            ts_display = f"{hari_id[dt_obj.weekday()]}, {tgl_bln} | {jam}"
            return start_ms, ts_display
    except Exception as e:
        logging.warning(f"Gagal ambil detail waktu: {e}")
    
    # Fallback ke waktu sekarang + 1 jam
    fallback_time = datetime.now(tz_jkt) + timedelta(hours=1)
    return int(fallback_time.timestamp() * 1000), "LIVE SOON"

def extract_m3u8_from_logs(driver, timeout=30):
    """
    🔥 FUNGSI BARU: Monitoring log secara aktif sampai m3u8 ditemukan
    """
    start_time = time.time()
    found_urls = set()
    
    while time.time() - start_time < timeout:
        try:
            logs = driver.get_log('performance')
            
            for entry in logs:
                try:
                    msg = json.loads(entry['message'])['message']
                    
                    # Method: Network.responseReceived atau Network.requestWillBeSent
                    if 'Network.responseReceived' in msg.get('method', '') or \
                       'Network.requestWillBeSent' in msg.get('method', ''):
                        
                        params = msg.get('params', {})
                        response = params.get('response', {})
                        request = params.get('request', {})
                        
                        # Cek URL di response atau request
                        url = response.get('url', '') or request.get('url', '')
                        
                        if '.m3u8' in url and 'ads' not in url.lower():
                            # Bersihkan URL
                            clean_url = url.replace('\\/', '/')
                            if clean_url not in found_urls:
                                found_urls.add(clean_url)
                                logging.info(f"    [FOUND] m3u8: {clean_url[:60]}...")
                                return clean_url
                                
                except (json.JSONDecodeError, KeyError):
                    continue
                    
        except Exception as e:
            logging.debug(f"Log read error: {e}")
        
        # Sleep singkat sebelum cek log lagi
        time.sleep(0.5)
    
    return None

def get_live_stream_link(driver):
    """
    🔥 VERSI BARU: Lebih robust dengan polling logs
    """
    max_attempts = 3
    stream_url = "Not Found"
    
    for attempt in range(1, max_attempts + 1):
        try:
            logging.info(f"    [ATTEMPT {attempt}] Mencari link m3u8...")
            
            # Reset ke main content
            driver.switch_to.default_content()
            
            # Clear overlays
            driver.execute_script("""
                document.querySelectorAll('.modal, .popup, .sh-overlay, [class*="ads"], [id*="ads"]').forEach(el => {
                    el.style.display = 'none';
                    el.remove();
                });
            """)
            
            # Scroll untuk trigger lazy load
            driver.execute_script("window.scrollTo(0, 600);")
            time.sleep(2)
            
            # Cari iframe dengan strategi multiple
            iframe_found = False
            target_iframe = None
            
            # Tunggu iframe muncul
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                )
            except TimeoutException:
                logging.warning("Tidak ada iframe yang muncul")
                continue
            
            # List semua iframe
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            logging.info(f"    Ditemukan {len(iframes)} iframe")
            
            # Prioritas iframe berdasarkan src
            priority_keywords = ['player', 'stream', 'embed', 'bitmovin', 'cdn', 'video']
            
            for iframe in iframes:
                src = iframe.get_attribute("src") or ""
                if any(kw in src.lower() for kw in priority_keywords):
                    target_iframe = iframe
                    logging.info(f"    [PRIORITY] Iframe: {src[:50]}...")
                    break
            
            # Jika tidak ada priority, ambil yang pertama yang visible
            if not target_iframe and iframes:
                for iframe in iframes:
                    if iframe.is_displayed():
                        target_iframe = iframe
                        logging.info("    [FALLBACK] Menggunakan iframe visible pertama")
                        break
            
            if target_iframe:
                # Switch ke iframe
                driver.switch_to.frame(target_iframe)
                iframe_found = True
                
                # Trigger play
                driver.execute_script("""
                    var videos = document.querySelectorAll('video');
                    videos.forEach(function(v) {
                        v.play().catch(e => console.log('Autoplay prevented'));
                        v.muted = true;
                    });
                    
                    // Click play button jika ada
                    var playBtn = document.querySelector('.play-button, [class*="play"], button[title*="play" i]');
                    if(playBtn) playBtn.click();
                """)
                
                # 🎯 POLLING LOGS: Cek terus sampai m3u8 muncul (max 25 detik)
                logging.info("    [POLLING] Monitoring network logs...")
                stream_url = extract_m3u8_from_logs(driver, timeout=25)
                
                if stream_url:
                    return stream_url
            
            # Jika gagal, refresh dan coba lagi
            if attempt < max_attempts:
                logging.info("    [RETRY] Refreshing page...")
                driver.refresh()
                time.sleep(5)
            
        except Exception as e:
            logging.error(f"    [ERROR] Attempt {attempt}: {e}")
            try:
                driver.refresh()
                time.sleep(5)
            except:
                pass
    
    return "Not Found"

def jalankan_scraper():
    logging.info("=== START SCRAPER (ROBUST VERSION) ===")
    
    chrome_ver = get_chrome_main_version()
    
    options = uc.ChromeOptions()
    options.page_load_strategy = 'eager'
    options.add_argument('--headless=new')  # Mode headless baru
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=IsolateOrigins,site-per-process')
    
    # User agent terbaru
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36')
    
    # 🔥 PENTING: Log level dan performance logging
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    options.add_argument('--enable-logging')
    options.add_argument('--v=1')

    driver = None
    try:
        logging.info("Inisialisasi Chrome...")
        driver = uc.Chrome(options=options, version_main=chrome_ver)
        driver.set_page_load_timeout(30)
        
    except Exception as e:
        logging.critical(f"Gagal memuat Chrome Driver: {e}")
        return

    hasil_akhir = []
    
    try:
        # Buka halaman utama
        logging.info(f"Membuka {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # Tunggu konten load
        time.sleep(8)
        
        # Scroll untuk load lazy content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(3)

        # Ambil semua card pertandingan
        cards = driver.find_elements(By.XPATH, "//a[contains(@href, 'truc-tiep')]")
        targets = []
        seen_urls = set()

        for card in cards:
            try:
                url = card.get_attribute("href")
                teks = card.text.strip()
                
                if url and url not in seen_urls and len(teks) > 10:
                    imgs = [img.get_attribute("src") for img in card.find_elements(By.TAG_NAME, "img") if img.get_attribute("src")]
                    targets.append({"teks": teks, "url": url, "imgs": imgs})
                    seen_urls.add(url)
            except:
                continue

        logging.info(f"Ditemukan {len(targets)} pertandingan unik")

        # Proses setiap pertandingan
        for idx, item in enumerate(targets, 1):
            try:
                logging.info(f"\n[{idx}/{len(targets)}] Processing...")
                
                # Parsing teks
                lines = [l.strip() for l in item['teks'].split('\n') if l.strip()]
                trash = ["CƯỢC", "XEM", "LIVE", "TRỰC", "TỶ LỆ", "KÈO", "CLICK", "VS", "-", "PHT", "HT", "FT", "TIP"]
                
                clean_lines = []
                for l in lines:
                    is_time_score = re.match(r'^\d{2}:\d{2}$', l) or \
                                   (l.isdigit() and len(l) <= 2) or \
                                   "'" in l or "+" in l or l.upper() in ["HT", "FT", "LIVE"]
                    
                    if not is_time_score and not any(tk in l.upper() for tk in trash) and len(l) > 1:
                        clean_lines.append(l)

                if len(clean_lines) >= 3:
                    liga, t1, t2 = clean_lines[0], clean_lines[1], clean_lines[2]
                elif len(clean_lines) == 2:
                    liga, t1, t2 = "International Match", clean_lines[0], clean_lines[1]
                else:
                    logging.warning(f"    Format teks tidak dikenal: {clean_lines}")
                    continue

                # Ambil logo
                img_list = item.get('imgs', [])
                l_liga = img_list[0] if len(img_list) > 0 else ""
                l_t1 = img_list[1] if len(img_list) > 1 else ""
                l_t2 = img_list[2] if len(img_list) > 2 else ""

                logging.info(f"    Match: {t1} vs {t2} ({liga})")

                # Ambil detail waktu dan stream
                start_ms, ts_display = get_detailed_info(driver, item['url'])
                stream_url = get_live_stream_link(driver)

                hasil_akhir.append({
                    "channelName": f"{t1} vs {t2}",
                    "ligaName": liga,
                    "team1Name": t1,
                    "team2Name": t2,
                    "team1Logo": l_t1,
                    "team2Logo": l_t2,
                    "logoligaUrl": l_liga,
                    "streamUrl": stream_url,
                    "startTime": start_ms,
                    "endTime": start_ms + 7200000,
                    "status": "LIVE",
                    "contentType": "event_pertandingan",
                    "description": ts_display,
                    "scraped_at": datetime.now(tz_jkt).isoformat()
                })
                
                logging.info(f"    Result: {stream_url[:50]}..." if stream_url != "Not Found" else "    Result: Not Found")
                
                # Delay antar match untuk tidak terlalu agresif
                time.sleep(3)
                
            except Exception as e:
                logging.error(f"Gagal proses item {idx}: {e}")
                continue

    except Exception as e:
        logging.critical(f"Error utama: {e}")
        
    finally:
        if driver:
            driver.quit()
            logging.info("Browser ditutup")

    # Kirim ke Firebase
    if hasil_akhir:
        success_count = sum(1 for x in hasil_akhir if x['streamUrl'] != "Not Found")
        logging.info(f"\n=== SUMMARY ===")
        logging.info(f"Total: {len(hasil_akhir)} matches")
        logging.info(f"Success: {success_count} with m3u8")
        logging.info(f"Failed: {len(hasil_akhir) - success_count}")
        
        fb_url = f"{FIREBASE_URL}/playlist/{FIXED_CATEGORY_ID}.json?auth={FIREBASE_SECRET}"
        payload = {
            "category_name": "EVENT LIVE",
            "order": 1,
            "last_updated": datetime.now(tz_jkt).isoformat(),
            "channels": {uuid.uuid4().hex: x for x in hasil_akhir}
        }
        
        try:
            r = requests.put(fb_url, json=payload, timeout=30)
            if r.status_code == 200:
                logging.info(f"[√] Data terkirim ke Firebase")
            else:
                logging.error(f"[X] Firebase error {r.status_code}: {r.text}")
        except Exception as e:
            logging.error(f"[X] Gagal kirim Firebase: {e}")
    else:
        logging.warning("Tidak ada data yang dihasilkan")

if __name__ == "__main__":
    jalankan_scraper()
