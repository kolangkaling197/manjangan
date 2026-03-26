from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os
import time

if not os.path.exists('debug_json'):
    os.makedirs('debug_json')

def scrap_vision_stealth():
    co = ChromiumOptions()
    # PENTING: Gunakan headless('new') atau trik stealth
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    # Hilangkan jejak webdriver
    co.set_argument('--disable-blink-features=AutomationControlled')
    
    # Gunakan User Agent yang sangat spesifik (Windows Chrome)
    co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

    page = ChromiumPage(co)
    print("--- SUPER STEALTH SNIFFING VISION+ ---", flush=True)
    
    # Kita dengarkan secara spesifik endpoint API-nya
    page.listen.start('program') 
    
    try:
        url = 'https://www.visionplus.id/webclient/?pageId=4030'
        print(f"[*] Membuka: {url}", flush=True)
        
        # Buka halaman
        page.get(url)
        
        # Trik 1: Tunggu halaman benar-benar load (cari elemen judul/konten)
        # Jika dalam 20 detik elemen tidak muncul, berarti diblokir
        if page.wait.ele_displayed('tag:img', timeout=20):
            print("[+] Halaman terbuka dan gambar terdeteksi.", flush=True)
        else:
            print("[!] Peringatan: Halaman mungkin kosong (Bot Check).", flush=True)

        all_nodes = []

        # Trik 2: Gerakan Scroll yang lebih manusiawi (bervariasi)
        for i in range(8):
            # Scroll sedikit demi sedikit agar API terpancing
            page.scroll.to_see('tag:footer') # Scroll ke paling bawah pelan-pelan
            print(f"[*] Monitoring data... Step {i+1}/8", flush=True)
            time.sleep(5) # Beri napas lebih lama untuk server

            # Tangkap paket yang lewat
            for res in page.listen.steps(count=10, timeout=2):
                try:
                    if res.response.body and isinstance(res.response.body, dict):
                        data = res.response.body
                        # Cek berbagai kemungkinan struktur data Vision+
                        nodes = data.get('nodes', [])
                        if not nodes and 'clusters' in data:
                            for c in data['clusters']:
                                nodes.extend(c.get('nodes', []))
                        
                        if nodes:
                            all_nodes.extend(nodes)
                            print(f"    [+] Dapat {len(nodes)} event dari {res.url[:40]}...", flush=True)
                except:
                    continue

        if all_nodes:
            # Hapus Duplikat
            unique_nodes = {n['id']: n for n in all_nodes if 'id' in n}.values()
            
            with open("debug_json/paket_21_1799.json", "w", encoding="utf-8") as f:
                json.dump({"nodes": list(unique_nodes)}, f, indent=4)
            
            print(f"\n[OK] BERHASIL! Total {len(unique_nodes)} event disimpan.", flush=True)
        else:
            # Trik 3: Jika gagal, ambil screenshot untuk debugging di Artifacts
            page.get_screenshot(path='debug_json/error_screenshot.png')
            print("[-] Gagal total. Screenshot disimpan di debug_json/error_screenshot.png", flush=True)

    except Exception as e:
        print(f"[-] Error: {e}", flush=True)
    finally:
        page.listen.stop()
        page.quit()

if __name__ == "__main__":
    scrap_vision_stealth()
