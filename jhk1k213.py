from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os

output_dir = 'debug_json'
clean_dir = 'debug_json_clean'
os.makedirs(output_dir, exist_ok=True)
os.makedirs(clean_dir, exist_ok=True)

# 6 STRIP PENTING
STRIP_IDS = [13752, 15752, 18894, 18918, 18973, 18974]

def scrap_vision_github_actions():
    co = ChromiumOptions()
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--window-size=1920,1080')
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    print("--- MODE DIRECT FETCH 6 STRIP PENTING (FIXED) ---")
    
    try:
        # Buka halaman dulu agar session terbentuk
        page.get('https://www.visionplus.id/webclient/?pageId=4030')
        page.wait.doc_loaded(timeout=15)
        
        print("[*] Mulai fetch langsung 6 strip API...")
        
        for strip_id in STRIP_IDS:
            api_url = f"https://www.visionplus.id/elements/strips/{strip_id}?target=WEB"
            print(f"[+] Fetching strip {strip_id} → {api_url}")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Referer": "https://www.visionplus.id/webclient/?pageId=4030",
                "IRIS-APP-VERSION": "11.4.13(0)_prd",
                "IRIS-DEVICE-TYPE": "WINDOWS/CHROME",
                "IRIS-DEVICE-CLASS": "PC",
                "IRIS-DEVICE-REGION": "Indonesia",
                "IRIS-APP-MODE": "Guest",
                "IRIS-DEVICE-STATUS": "INACTIVE",
                "IRIS-HW-DEVICE-ID": "99ce7946-c6b0-4449-8dd2-fce01f1b0560",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
            }
            
            # METHOD YANG BENAR DI DRISSIONPAGE
            response = page.request.get(api_url, headers=headers)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    clean_filename = f"{clean_dir}/clean_strip_{strip_id}.json"
                    
                    with open(clean_filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    
                    content_count = sum(1 for item in data if isinstance(item, dict) and item.get("cellType") == "CONTENT") if isinstance(data, list) else 0
                    
                    print(f"   ✅ BERHASIL! clean_strip_{strip_id}.json → {content_count} event")
                except Exception as e:
                    print(f"   ❌ Gagal parse JSON strip {strip_id}: {e}")
            else:
                print(f"   ❌ Gagal fetch strip {strip_id} (status {response.status_code})")
                print(f"   Response: {response.text[:300]}...")
        
        print(f"\n[+] SELESAI! Semua 6 strip sudah diproses.")
        print(f"[+] File disimpan di folder '{clean_dir}'")
        
    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        page.quit()
        print("[*] Browser ditutup.")

if __name__ == "__main__":
    scrap_vision_github_actions()
