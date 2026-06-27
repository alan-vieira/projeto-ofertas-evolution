"""
Extrator de produtos do Mercado Livre.
Utiliza Playwright para acessar páginas de ofertas com links de afiliado, clicar
no botão 'Ir para produto' (quando presente) e extrair dados como título,
preços, desconto, Pix, cupom e URL da imagem.

✅ Cupom: captura APENAS automáticos ("Você economiza"), ignora condicionais
✅ Seletores com fallback + tratamento robusto de erros
✅ Anti-detecção: user-agent, headers, scripts de mascaramento
✅ Resolução de short URLs (meli.la → produto.mercadolivre.com.br)
✅ Código limpo, tipado e pronto para produção

@author: Alan Silva Vieira
@version: 2.1.1
"""
import re
import time
import random
import logging
import os
from pathlib import Path
from typing import Optional, Tuple
from playwright.sync_api import sync_playwright, Browser, Page, Error as PlaywrightError
from src.core.models import Product, StoreType
from src.core.utils import calcular_ou_validar_desconto

logger = logging.getLogger(__name__)

ML_CONFIG = {
    "timeout_page_load": 30000,
    "timeout_selector": 20000,
    "timeout_button": 15000,
    "timeout_networkidle": 25000,
    "headless": True,
    "screenshot_dir": "logs/screenshots",
    "max_retries": 2,
    "retry_base_delay": 2.0,
}


def _ensure_screenshot_dir() -> None:
    """Garante que o diretório de screenshots exista."""
    Path(ML_CONFIG["screenshot_dir"]).mkdir(parents=True, exist_ok=True)


def _take_screenshot(page: Page, url: str, suffix: str = "erro") -> None:
    """Tira screenshot para debug em caso de falha."""
    _ensure_screenshot_dir()
    safe_name = re.sub(r"[^\w\-]", "_", url)[:50]
    timestamp = int(time.time())
    path = f"{ML_CONFIG['screenshot_dir']}/{suffix}_{safe_name}_{timestamp}.png"
    try:
        page.screenshot(path=path, full_page=True, timeout=10000)
        logger.debug(f"📸 Screenshot salvo: {path}")
    except Exception as e:
        logger.warning(f"⚠️ Falha ao salvar screenshot: {e}")


def resolve_short_url(short_url: str, timeout: int = 15) -> str:
    """
    Resolve redirecionamentos de URLs curtos (meli.la, mlb.la, etc.)
    Usa GET com stream=True para forçar redirect sem baixar conteúdo.
    """
    import requests
    from urllib.parse import urlparse
    
    try:
        # GET com stream=True força o redirect sem baixar o corpo da página
        response = requests.get(
            short_url.strip(),
            allow_redirects=True,
            timeout=timeout,
            stream=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            }
        )
        final_url = response.url
        response.close()  # Fecha a conexão stream para liberar recursos
        
        # Validação: só aceita URLs do domínio mercadolivre
        parsed = urlparse(final_url)
        if "mercadolivre" in parsed.netloc.lower():
            logger.debug(f"🔗 Short URL resolvida: {short_url[:40]}... → {final_url[:70]}...")
            return final_url
        
        logger.warning(f"⚠️ URL resolvida não parece ser do ML: {final_url}")
        return short_url  # fallback seguro
        
    except Exception as e:
        logger.warning(f"⚠️ Falha ao resolver short URL {short_url}: {e}")
        return short_url  # tenta com a original mesmo assim


def _is_page_blocked(page: Page) -> bool:
    """Verifica se a página foi bloqueada por proteções anti-bot."""
    try:
        content = page.content()[:1000].lower()
        blocked_indicators = [
            "cloudflare", "challenge", "captcha", "acesso negado", 
            "verificação de segurança", "just a moment", "ddos-guard",
            "verificando se você é humano"
        ]
        return any(indicator in content for indicator in blocked_indicators)
    except:
        return False


def _parse_money_amount(locator) -> Optional[str]:
    """
    Extrai e formata R$ X,YY a partir de fraction + cents spans.
    Retorna: "R$ 130,49" ou None se não encontrar.
    """
    if locator.count() == 0:
        return None
    
    frac_el = locator.locator("span.andes-money-amount__fraction").first
    cent_el = locator.locator("span.andes-money-amount__cents").first
    
    fraction = frac_el.inner_text().strip() if frac_el.count() > 0 else "0"
    cents = cent_el.inner_text().strip() if cent_el.count() > 0 else "00"
    
    # Normaliza centavos para 2 dígitos
    if len(cents) == 1:
        cents += "0"
    elif len(cents) > 2:
        cents = cents[:2]
        
    return f"R$ {fraction},{cents}"


def _extrair_cupom(page: Page) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrai informações de cupom APENAS se for automático (sem condições).
    
    Regras:
    ✅ "Você economiza R$ X,XX" → captura
    ❌ "compra superior a R$ X" → ignora (condicional)
    ❌ Sem "Você economiza" → ignora
    
    Returns:
        tuple: (porcentagem_desconto, valor_economizado) ou (None, None)
    """
    try:
        cupom_section = page.locator("text='Cupom'").first
        if cupom_section.count() == 0:
            logger.debug("ℹ️ Sem cupom disponível")
            return None, None
        
        # Pegar texto completo da seção de cupom (subindo 2 níveis no DOM)
        parent = cupom_section.locator("..").locator("..")
        texto_cupom = parent.inner_text().strip()
        logger.debug(f"🎫 Texto do cupom: {texto_cupom[:120]}...")
        
        # === FILTRO CRÍTICO: Apenas cupons automáticos ===
        termos_condicionais = ["superior", "mínimo", "mínima", "a partir", "acima de", "gastando"]
        if any(termo in texto_cupom.lower() for termo in termos_condicionais):
            logger.debug("❌ Cupom condicional detectado (ignorado)")
            return None, None
        
        if "você economiza" not in texto_cupom.lower():
            logger.debug("❌ Cupom sem 'Você economiza' (ignorado)")
            return None, None
        
        # Extrair porcentagem (ex: "18% OFF")
        match_pct = re.search(r"(\d{1,3})%\s*OFF", texto_cupom, re.IGNORECASE)
        if not match_pct:
            logger.debug("⚠️ Não encontrou porcentagem no cupom")
            return None, None
        
        porcentagem = f"{match_pct.group(1)}% OFF"
        
        # Extrair valor economizado (ex: "R$ 26,10")
        match_valor = re.search(r"R\$\s*([\d.]+,\d{2})", texto_cupom)
        valor_economia = f"R${match_valor.group(1)}" if match_valor else None
        
        logger.debug(f"✅ Cupom automático: {porcentagem} | Economia: {valor_economia}")
        return porcentagem, valor_economia
        
    except Exception as e:
        logger.debug(f"⚠️ Erro ao extrair cupom (ignorado): {e}")
        return None, None


def _extrair_titulo_com_fallback(page: Page, timeout: int = 20000) -> Optional[str]:
    """
    Extrai título do produto com múltiplos seletores de fallback.
    Retorna título em CAIXA ALTA ou None se não encontrar.
    """
    title_selectors = [
        "h1.ui-pdp-title",
        "h1.andes-title__title",
        "[data-testid='PDP_TITLE']",
        "h1.ui-pdp-subtitle",
        "h1.ui-pdp-header__title",
        "h1"
    ]
    
    for selector in title_selectors:
        try:
            element = page.wait_for_selector(selector, timeout=timeout//len(title_selectors), state="visible")
            if element:
                titulo = element.inner_text().strip().upper()
                if titulo and len(titulo) > 10 and len(titulo) < 200:  # valida conteúdo
                    logger.debug(f"✅ Título encontrado com selector: {selector}")
                    return titulo
        except PlaywrightError:
            continue  # tenta próximo selector
    
    # Fallback extremo: busca qualquer h1 com texto significativo
    try:
        titulo = page.locator("h1").first.inner_text(timeout=3000).strip().upper()
        if titulo and 10 < len(titulo) < 200:
            logger.debug("✅ Título encontrado com fallback genérico")
            return titulo
    except:
        pass
    
    return None


def _extract_with_logic(page: Page, url_original: str) -> Optional[Product]:
    """Lógica de extração com tratamento robusto para todos os cenários."""
    
    # ✅ Resolve short URL ANTES de navegar
    url_final = resolve_short_url(url_original)
    
    try:
        # Navega para URL resolvida
        page.goto(url_final, timeout=ML_CONFIG["timeout_page_load"], wait_until="domcontentloaded")
        
        # ✅ CORREÇÃO: Page não tem atributo 'status' - loga apenas a URL final
        logger.debug(f"🔗 URL final: {page.url}")
        
        # Verifica bloqueios comuns
        if _is_page_blocked(page):
            logger.error("🚫 Página bloqueada por proteção anti-bot")
            _take_screenshot(page, url_original, "blocked")
            return None
            
        # Debug mode: salva HTML e screenshot se variável de ambiente estiver ativa
        if os.getenv("ML_DEBUG", "false").lower() == "true":
            debug_path = f"debug_ml_{int(time.time())}.html"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(page.content())
            _take_screenshot(page, url_original, "debug_full")
            logger.debug(f"🐛 Debug mode: HTML salvo em {debug_path}")
            
    except PlaywrightError as e:
        logger.error(f"❌ Falha ao carregar página: {e}")
        _take_screenshot(page, url_original, "load_failed")
        return None

    # ========================================================================
    # Botão 'Ir para produto' (redirecionamento de afiliado)
    # ========================================================================
    selector_botao = 'a.poly-component__link--action-link:has-text("Ir para produto")'
    try:
        botao = page.wait_for_selector(selector_botao, timeout=ML_CONFIG["timeout_button"], state="visible")
        if botao:
            logger.debug("✅ Botão 'Ir para produto' encontrado. Clicando...")
            botao.click()
            # Aguardar redirecionamento com timeout mais flexível
            page.wait_for_load_state("networkidle", timeout=ML_CONFIG["timeout_networkidle"])
            # Re-verifica bloqueio após redirect
            if _is_page_blocked(page):
                logger.error("🚫 Página bloqueada após redirect do afiliado")
                _take_screenshot(page, url_original, "blocked_redirect")
                return None
    except PlaywrightError:
        logger.warning("⚠️ Botão não encontrado ou timeout. Tentando extrair na página atual...")

    # ========================================================================
    # Extrair título com fallbacks
    # ========================================================================
    titulo = _extrair_titulo_com_fallback(page, timeout=ML_CONFIG["timeout_selector"])
    if not titulo:
        logger.warning("❌ Título não encontrado em nenhum selector.")
        _take_screenshot(page, url_original, "title_missing")
        # Continua tentando extrair outros campos (opcional)
    
    try:
        # --------------------------------------------------------------------
        # 2. PREÇO ANTIGO (opcional - strikethrough)
        # --------------------------------------------------------------------
        preco_antigo = _parse_money_amount(page.locator("s.andes-money-amount"))

        # --------------------------------------------------------------------
        # 3. PREÇO NOVO (obrigatório)
        # --------------------------------------------------------------------
        price_container = page.locator("div.ui-pdp-price__second-line").first
        preco_novo = _parse_money_amount(price_container)

        # Fallback: Regex se spans não carregarem corretamente
        if not preco_novo and price_container.count() > 0:
            try:
                price_text = price_container.inner_text().strip()
                match = re.search(r'R\$\s*([\d.]+,\d{2})', price_text)
                if match:
                    preco_novo = f"R$ {match.group(1)}"
            except:
                pass

        if not preco_novo:
            logger.error("❌ Preço novo não encontrado na página.")
            _take_screenshot(page, url_original, "price_missing")
            return None

        # --------------------------------------------------------------------
        # 4. DESCONTO e PIX
        # --------------------------------------------------------------------
        tem_pix = False
        desconto_bruto = None  # renomeado para evitar conflito
        
        if price_container.count() > 0:
            try:
                texto = price_container.inner_text().strip().lower()
                
                if "no pix" in texto or "à vista no pix" in texto:
                    tem_pix = True
                
                # Regex mais restritivo: (?<!\d) exige que não haja dígito antes
                match_desc = re.search(r'(?<!\d)(\d{1,2})%\s*(?:off|de desconto)', texto, re.IGNORECASE)
                if match_desc:
                    desconto_bruto = f"{match_desc.group(1)}% OFF"
                    
            except Exception as e:
                logger.debug(f"⚠️ Erro ao extrair desconto do texto: {e}")

        # ✅ Valida ou calcula desconto com fallback
        desconto = calcular_ou_validar_desconto(desconto_bruto, preco_antigo, preco_novo)

        # --------------------------------------------------------------------
        # 5. CUPOM (APENAS AUTOMÁTICOS)
        # --------------------------------------------------------------------
        cupom_pct, cupom_valor = _extrair_cupom(page)

        # --------------------------------------------------------------------
        # 6. IMAGEM PRINCIPAL
        # --------------------------------------------------------------------
        img_selectors = [
            "img.ui-pdp-image.ui-pdp-gallery__figure__image",
            "img.ui-pdp-gallery__figure__image",
            "img[data-testid='product-image']",
            "img"
        ]
        image_url = ""
        for selector in img_selectors:
            img_el = page.locator(selector).first
            if img_el.count() > 0:
                image_url = img_el.get_attribute("data-zoom") or img_el.get_attribute("src") or ""
                if image_url and "http" in image_url:
                    break

        # --------------------------------------------------------------------
        # VALIDAÇÃO FINAL
        # --------------------------------------------------------------------
        if not titulo:
            logger.warning("❌ Título ausente. Abortando extração.")
            return None

        logger.info(f"✅ Extração concluída: {titulo[:50]}...")

        # --------------------------------------------------------------------
        # RETORNO DO PRODUCT
        # --------------------------------------------------------------------
        return Product(
            title=titulo,
            price_original=preco_antigo,
            price_discounted=preco_novo,
            discount=desconto,
            has_pix=tem_pix,
            coupon=cupom_pct,
            coupon_discount=cupom_valor,
            affiliate_link=url_original.strip(),  # mantém URL original do afiliado
            image_url=image_url,
            store=StoreType.MERCADO_LIVRE if hasattr(StoreType, "MERCADO_LIVRE") else "mercado_livre",
        )

    except PlaywrightError as e:
        logger.error(f"❌ Erro ao extrair dados do DOM: {e}")
        _take_screenshot(page, url_original, "dom_error")
        return None
    except Exception as e:
        logger.exception(f"❌ Erro inesperado durante extração: {e}")
        _take_screenshot(page, url_original, "unexpected_error")
        return None


def extrair_dados_produto_mercadolivre(
    url_afiliado: str,
    browser: Optional[Browser] = None,
    page: Optional[Page] = None,
    close_browser: bool = True
) -> Optional[Product]:
    """
    Extrai dados estruturados de um produto do Mercado Livre.
    
    Args:
        url_afiliado: URL com parâmetros de afiliado.
        browser: Browser existente para reuso (opcional).
        page: Page existente para reuso (opcional).
        close_browser: Se True, fecha browser/page ao final (padrão).
    
    Returns:
        Product | None: Objeto populado ou None em falha crítica.
    """
    logger.info(f"🔗 Processando Mercado Livre: {url_afiliado}")
    
    own_browser = browser is None
    own_page = page is None

    try:
        if own_browser:
            # Modo isolado: cria e fecha próprio browser
            with sync_playwright() as p:
                # Launch com args anti-detecção
                browser = p.chromium.launch(
                    headless=ML_CONFIG["headless"],
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--disable-gpu",
                        "--window-size=1920,1080",
                    ]
                )
                
                # Context com fingerprinting humanizado
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale="pt-BR",
                    timezone_id="America/Sao_Paulo",
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Cache-Control": "max-age=0",
                    },
                    bypass_csp=True,  # Útil para debug; remova em produção se causar problemas
                )
                
                # Script para mascarar automação
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
                    window.chrome = { runtime: {} };
                """)
                
                page = context.new_page()
                result = _extract_with_logic(page, url_afiliado)
                
                if close_browser:
                    context.close()
                    browser.close()
                return result
        else:
            # Modo reuso: usa browser/page fornecidos (otimização para pipeline)
            return _extract_with_logic(page, url_afiliado)

    except PlaywrightError as e:
        logger.error(f"❌ Erro crítico no Playwright: {e}")
        if page and own_page:
            _take_screenshot(page, url_afiliado, "critical_error")
        return None
    except Exception as e:
        logger.exception(f"❌ Erro inesperado no gerenciador: {e}")
        return None


def extrair_com_retry(url: str, config: dict, extractor_func, max_retries: int = None) -> Optional[Product]:
    """
    Wrapper com retry exponencial para extrações transitórias.
    
    Args:
        url: URL do produto
        config: Configurações do pipeline
        extractor_func: Função extratora a ser chamada
        max_retries: Número máximo de tentativas (usa config se None)
    
    Returns:
        Product | None
    """
    retries = max_retries if max_retries is not None else ML_CONFIG["max_retries"]
    last_error = None
    
    for attempt in range(retries + 1):
        try:
            return extractor_func(url_afiliado=url, close_browser=False)
        except Exception as e:
            last_error = e
            # Retry apenas em erros transitórios
            if any(term in str(e) for term in ["Timeout", "Locator", "network", "navigation"]):
                if attempt < retries:
                    # Backoff exponencial com jitter
                    delay = (ML_CONFIG["retry_base_delay"] ** attempt) + random.uniform(0, 1)
                    logger.warning(f"⚠️ Tentativa {attempt+1}/{retries+1} falhou. Aguardando {delay:.1f}s...")
                    time.sleep(delay)
                    continue
            # Erro não recuperável ou última tentativa
            break
    
    logger.error(f"❌ Todas as {retries+1} tentativas falharam para {url}: {last_error}")
    return None