import re
import time
import random
import logging
from pathlib import Path
from typing import Optional, List
from playwright.sync_api import Error as PlaywrightError, sync_playwright, Browser, Page

# Importação corrigida para evitar conflitos de módulo/função
import playwright_stealth

# Supondo que estes modelos existam no seu projeto
from src.core.models import Product, StoreType

logger = logging.getLogger(__name__)

MAGALU_CONFIG = {
    "timeout_page_load": 60000, 
    "timeout_selector": 20000,
    "headless": False,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "retry_attempts": 3,
    "retry_delay_sec": 5,
    "screenshot_dir": "logs/screenshots",
    "random_delay_range": (1500, 4000),
}

# ============================================================================
# MELHORIAS NOS SELETORES
# ============================================================================
SELECTORS = {
    "title": ['h1[data-testid="heading"]', 'h1.header-product__title', '.product-title', 'h1'],
    "price_new": [
        '[data-testid="price-value"]', 
        '[data-testid="price-current-value"]',
        '.product-price__value',
        'p[data-testid="price-value"]'
    ],
    "price_old": [
        '[data-testid="price-original"]',
        '.product-price__original',
        'span[class*="PriceOriginal"]',
        '.original-price'
    ],
    "pix_check": [
        '[data-testid="price-method"]', 
        '.price-method', 
        'p:has-text("PIX")',
        'span:has-text("no PIX")'
    ],
    "image": [
        'img[data-testid="image"]', 
        'img.showcase-product__image', 
        'img[src*="magazineluiza.com.br/"]',
        '.main-image img'
    ]
}

# ============================================================================
# FUNÇÕES DE APOIO
# ============================================================================

def limpar_monetario(valor: str) -> str:
    if not valor: return ""
    limpo = re.sub(r'[^\d.,]', '', valor).strip()
    if not limpo: return ""
    return f"R${limpo}"

def corrigir_preco_duplicado(valor: str) -> str:
    if not valor: return ""
    precos = re.findall(r'\d+,\d{2}', valor)
    if precos and len(precos) > 1:
        if precos[0] == precos[1]:
            return f"R${precos[0]}"
    return valor

def _setup_stealth_page(page: Page):
    playwright_stealth.stealth_sync(page)
    page.set_extra_http_headers({
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Referer": "https://www.google.com.br/"
    })
    page.set_viewport_size({"width": 1280, "height": 720})

# ============================================================================
# EXTRATOR PRINCIPAL
# ============================================================================

def extrair_dados_produto_magalu(url_afiliado: str, page=None, **kwargs) -> Optional[Product]:
    time.sleep(random.uniform(1, 3))
    logger.info(f"🔎 Analisando link: {url_afiliado}")
    
    p = None
    browser = None
    should_close = False
    
    try:
        # 1. Configuração inicial do navegador
        if page is None:
            p = sync_playwright().start()
            browser = p.chromium.launch(headless=MAGALU_CONFIG["headless"])
            page = browser.new_page()
            _setup_stealth_page(page)
            should_close = True

        # 2. Navegação
        try:
            # Aumentamos o timeout e mudamos para networkidle
            page.goto(url_afiliado, wait_until="load", timeout=MAGALU_CONFIG["timeout_page_load"])
            
            # Aumente o tempo de espera para o redirecionamento do onelink
            page.wait_for_timeout(7000)
            
            # Se o status for 403 ou 404, o Magalu bloqueou o IP ou o link expirou
            if response and response.status >= 400:
                logger.error(f"❌ Erro HTTP {response.status} ao acessar Magalu")
                return None

            # Espera forçada maior para o Onelink resolver
            page.wait_for_timeout(6000) 
            
            # Garante que o corpo da página apareceu
            page.wait_for_selector("body", timeout=10000)
            
            logger.info(f"📍 URL Final: {page.url}")
        except Exception as e:
            logger.error(f"⚠️ Erro ao navegar: {e}")
            return None

        # 3. Extração do Título
        titulo = None
        for sel in SELECTORS["title"]:
            try:
                element = page.wait_for_selector(sel, state="visible", timeout=10000)
                if element:
                    titulo = element.inner_text().strip().upper()
                    break
            except: continue
        
        if not titulo:
            logger.error("❌ Título não encontrado.")
            return None

        # 4. Extração de Preços
        preco_novo_raw = ""
        for sel in SELECTORS["price_new"]:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=3000):
                    preco_novo_raw = loc.inner_text()
                    break
            except: continue
        
        preco_novo = corrigir_preco_duplicado(limpar_monetario(preco_novo_raw))

        preco_antigo_raw = ""
        for sel in SELECTORS["price_old"]:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=2000):
                    preco_antigo_raw = loc.inner_text()
                    break
            except: continue
        preco_antigo = limpar_monetario(preco_antigo_raw)

        # 5. Verificação de PIX
        tem_pix = False
        for sel in SELECTORS["pix_check"]:
            try:
                if page.locator(sel).filter(has_text=re.compile(r"pix", re.I)).count() > 0:
                    tem_pix = True
                    break
            except: continue

        # 6. Imagem
        img_url = ""
        for sel in SELECTORS["image"]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    img_url = loc.get_attribute("src") or ""
                    if "http" in img_url: break
            except: continue
        
        if img_url:
            img_url = img_url.split("?")[0]

        # 7. Construção do Objeto
        dados_final = {
            "title": titulo,
            "price_original": preco_antigo if preco_antigo else None,
            "price_discounted": preco_novo,
            "has_pix": tem_pix,
            "affiliate_link": page.url, 
            "image_url": img_url,
            "store": "magalu"
        }

        return Product(**dados_final)

    except Exception as e:
        logger.error(f"❌ Falha crítica: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        # 8. Fechamento de recursos
        if should_close:
            try:
                if browser: browser.close()
                if p: p.stop()
            except: pass