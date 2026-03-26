from DrissionPage import ChromiumPage, ChromiumOptions

def get_api_endpoint():
    co = ChromiumOptions().headless()
    page = ChromiumPage(co)
    
    print("[*] Menunggu API Layout 1799 lewat...")
    page.listen.start()
    page.get('https://www.visionplus.id/webclient/?pageId=4030')

    # Scroll sedikit untuk trigger API
    page.scroll.down(1000)

    for res in page.listen.steps():
        # Cari URL yang mengandung ID 1799
        if '1799' in res.url and 'layout' in res.url:
            print("\n" + "="*50)
            print("FOUND API ENDPOINT!")
            print("="*50)
            print(f"URL: {res.url}")
            print("-" * 50)
            print("HEADERS YANG DIBUTUHKAN (Penting):")
            # Menampilkan Header karena tanpa ini API akan menolak (403 Forbidden)
            for key, value in res.request.headers.items():
                print(f"{key}: {value}")
            print("="*50)
            break

    page.listen.stop()
    page.quit()

if __name__ == "__main__":
    get_api_endpoint()
