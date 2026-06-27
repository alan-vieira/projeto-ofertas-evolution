# test_import.py
try:
    from playwright.sync_api import sync_playwright
    print("✅ Playwright importado com sucesso!")
    
    # Testar browser
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        print("✅ Chromium inicializado!")
        browser.close()
        
except ImportError as e:
    print(f"❌ Erro de import: {e}")
except Exception as e:
    print(f"❌ Erro ao iniciar browser: {e}")
