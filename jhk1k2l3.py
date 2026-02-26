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

def save_debug_screenshot(driver, name="debug"):
    """Simpan screenshot untuk debugging"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        driver.save_screenshot(filename)
        logging.info(f"📸 Screenshot saved: {filename}")
        return filename
    except Exception as e:
        logging.error(f"Gagal save screenshot: {e}")
        return None

def save_debug_html(driver, name="debug"):
    """Simpan HTML page source"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logging.info(f"📄 HTML saved: {filename}")
        return filename
    except Exception as e:
        logging.error(f"Gagal save HTML: {e}")
        return None

# --- CHROME SETUP UNTUK GITHUB ACTIONS ---

# --- 2. FUNGSI PEMBANTU ---

def setup_chrome_for_github_actions():
    """Setup Chrome dengan stealth maksimal untuk GitHub Actions"""
    chrome_ver = get_chrome_main_version()
    logging.info(f"Detected Chrome version: {chrome_ver}")
    
    options = uc.ChromeOptions()
    
    # 🎯 STEALTH OPTIONS (KRITIS!)
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # 🎯 ANTI-DETEKSI HEADLESS (TAMBAHAN BARU!)
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=IsolateOrigins,site-per-process')
    options.add_argument('--disable-site-isolation-trials')
    options.add_argument('--disable-features=BlockInsecurePrivateNetworkRequests')
    
    # 🎯 MIMIC REAL BROWSER (TAMBAHAN BARU!)
    options.add_argument('--lang=id-ID,id')
    options.add_argument('--timezone=Asia/Jakarta')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-infobars')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-running-insecure-content')
    
    # 🎯 USER AGENT REALISTIS (UPDATE!)
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0')
    
    # 🎯 PREFERS (TAMBAHAN BARU!)
    options.add_experimental_option('prefs', {
        'profile.default_content_setting_values.notifications': 2,
        'profile.default_content_settings.popups': 0,
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
    })
    
    # Performance logging
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    # 🎯 UC SPECIFIC OPTIONS
    options.add_argument('--password-store=basic')
    options.add_argument('--enable-automation')
    options.add_argument('--remote-debugging-port=9222')
    
    # Create driver dengan retry
    driver = None
    max_retries = 3
    
    for i in range(max_retries):
        try:
            logging.info(f"Creating driver (attempt {i+1}/{max_retries})...")
            
            # 🎯 GUNAKAN DRIVER DARI PATH SPESIFIK (lebih stabil)
            driver = uc.Chrome(
                options=options,
                version_main=chrome_ver,
                driver_executable_path=None,  # Auto download
                use_subprocess=True  # 🎯 KRITIS untuk GitHub Actions
            )
            
            # 🎯 EXECUTE CDP UNTUK BYPASS DETEKSI (TAMBAHAN BARU!)
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    window.chrome = { runtime: {} };
                '''
            })
            
            logging.info("✅ Driver created successfully")
            return driver
            
        except Exception as e:
            logging.error(f"❌ Failed: {e}")
            if i < max_retries - 1:
                time.sleep(10)
    
    raise Exception("Failed to initialize driver")

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
        # ❌ HAPUS: driver.set_page_load_strategy('eager')
        
        # Gunakan timeout saat get
        driver.set_page_load_timeout(30)
        driver.get(match_page_url)
        
        # Tunggu title load
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
    
    # Fallback
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
    max_attempts = 3
    stream_url = "Not Found"
    
    for attempt in range(1, max_attempts + 1):
        try:
            logging.info(f"    [ATTEMPT {attempt}] Mencari link m3u8...")
            
            # Reset ke main content
            driver.switch_to.default_content()
            
            # 🎯 TUNGGU PAGE LOAD LEBIH LAMA (UPDATE!)
            time.sleep(5)  # Tunggu initial load
            
            # Clear overlays
            driver.execute_script("""
                document.querySelectorAll('.modal, .popup, .sh-overlay, [class*="ads"], [id*="ads"], iframe[src*="ads"]').forEach(el => {
                    el.style.display = 'none';
                    el.remove();
                });
            """)
            
            # 🎯 SCROLL PELAN-PELAN UNTUK TRIGGER LAZY LOAD (UPDATE!)
            for scroll in [300, 600, 900]:
                driver.execute_script(f"window.scrollTo(0, {scroll});")
                time.sleep(2)
            
            # 🎯 TUNGGU IFRAME DENGAN DELAY YANG LEBIH LAMA (UPDATE!)
            try:
                # Tunggu sampai 20 detik
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                )
                logging.info(f"    ✅ Iframe detected!")
            except TimeoutException:
                logging.warning(f"    ⚠️ Timeout waiting for iframe")
                
                # 🎯 SAVE DEBUG (TAMBAHAN BARU!)
                save_debug_screenshot(driver, f"no_iframe_attempt_{attempt}")
                
                if attempt < max_attempts:
                    driver.refresh()
                    time.sleep(8)
                    continue
                else:
                    return "Not Found"

            # Cari iframe
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            logging.info(f"    Ditemukan {len(iframes)} iframe")
            
            # 🎯 PRINT SEMUA IFRAME SRC UNTUK DEBUG (TAMBAHAN BARU!)
            for idx, iframe in enumerate(iframes):
                src = iframe.get_attribute("src") or "no-src"
                logging.info(f"      Iframe {idx}: {src[:80]}...")
            
            # Pilih iframe
            target_iframe = None
            priority_keywords = ['player', 'stream', 'embed', 'bitmovin', 'cdn', 'video', 'live']
            
            for iframe in iframes:
                src = iframe.get_attribute("src") or ""
                if any(kw in src.lower() for kw in priority_keywords):
                    target_iframe = iframe
                    logging.info(f"    [PRIORITY] Selected: {src[:60]}...")
                    break
            
            # Fallback ke iframe pertama yang visible
            if not target_iframe:
                for iframe in iframes:
                    try:
                        if iframe.is_displayed():
                            target_iframe = iframe
                            logging.info("    [FALLBACK] Using first visible iframe")
                            break
                    except:
                        continue
            
            if target_iframe:
                # Switch ke iframe
                driver.switch_to.frame(target_iframe)
                
                # 🎯 TUNGGU IFRAME LOAD (TAMBAHAN BARU!)
                time.sleep(5)
                
                # Trigger play
                driver.execute_script("""
                    // Play video
                    var videos = document.querySelectorAll('video');
                    videos.forEach(function(v) {
                        v.play().catch(e => console.log('Autoplay blocked'));
                        v.muted = true;
                    });
                    
                    // Click play button
                    var playBtns = document.querySelectorAll('button, [class*="play"], [id*="play"]');
                    playBtns.forEach(function(btn) {
                        if(btn.offsetParent !== null) btn.click();
                    });
                """)
                
                # 🎯 POLLING LOGS (dari kode sebelumnya)
                logging.info("    [POLLING] Monitoring network logs...")
                stream_url = extract_m3u8_from_logs(driver, timeout=25)
                
                if stream_url:
                    return stream_url
            
            # Retry
            if attempt < max_attempts:
                logging.info("    [RETRY] Refreshing...")
                driver.refresh()
                time.sleep(8)
                
        except Exception as e:
            logging.error(f"    [ERROR] Attempt {attempt}: {e}")
            save_debug_screenshot(driver, f"error_attempt_{attempt}")
            try:
                driver.refresh()
                time.sleep(8)
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


