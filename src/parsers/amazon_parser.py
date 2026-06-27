"""
Parser para blocos de texto copiados manualmente da Amazon Brasil.
✅ Suporta formatos variados: "De R$", "-XX%", "Cupom: XYZ", etc.
"""
import re
from src.core.models import Product
from src.core.formatter import normalize_price_string


def _extract_prices_amazon(full_text: str) -> tuple[str | None, str]:
    """
    Extrai preços no formato da Amazon.
    
    Padrões suportados:
        De R$ 349,00     ← Original (opcional)
        R$ 229,00        ← Promocional (obrigatório)
        -26%             ← Desconto alternativo
    
    Returns:
        tuple: (preco_original, preco_promocional)
    """
    price_pattern = r'R?\$?\s*([\d.]+,\d{2})'
    matches = re.findall(price_pattern, full_text)
    
    if not matches:
        return None, None
    
    def to_float(price_str: str) -> float:
        return float(price_str.replace(".", "").replace(",", "."))
    
    prices = [(m, to_float(m)) for m in matches]
    
    if len(prices) == 1:
        return None, f"R${prices[0][0]}"
    
    # Ordenar por valor: menor=promo, maior=original
    prices_sorted = sorted(prices, key=lambda x: x[1])
    preco_promocional = f"R${prices_sorted[0][0]}"
    preco_original = f"R${prices_sorted[-1][0]}"
    
    if preco_original == preco_promocional:
        return None, preco_promocional
    
    return preco_original, preco_promocional


def parse_amazon_offer_block(text: str) -> Product | None:
    """
    Parse de bloco de texto manual da Amazon.
    
    Formato suportado:
        Título do Produto
        De R$ 349,00          ← Opcional
        R$ 229,00             ← Promocional
        34% de desconto       ← Ou: -26%
        Cupom: FIRE10         ← Opcional
        https://amzn.to/...   ← Link afiliado
        https://...jpg        ← Imagem
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None

    full_text = "\n".join(lines)
    
    # =========================================================================
    # 1. TÍTULO
    # =========================================================================
    titulo = None
    for line in lines:
        if (len(line) > 20 and 
            not line.startswith("http") and 
            not re.match(r'^-\s*\d+%', line) and  # Ignora: -26%
            not re.match(r'^R?\$?\s*[\d.]+,\d{2}$', line) and  # Ignora: R$1.234,56
            not re.match(r'^[\d.]+,\d{2}$', line) and  # Ignora: 123,45
            not re.match(r'^cupom', line, re.IGNORECASE) and
            not re.match(r'^coupon', line, re.IGNORECASE)):
            titulo = line.strip().upper()
            break
    
    if not titulo:
        return None

    # =========================================================================
    # 2. PREÇOS
    # =========================================================================
    preco_original, preco_promocional = _extract_prices_amazon(full_text)
    if not preco_promocional:
        return None

    # =========================================================================
    # 3. DESCONTO: Suporta "34% de desconto", "-26%", "34% OFF"
    # =========================================================================
    desconto = None
    
    # Padrão: -26% ou - 26%
    match_disc_neg = re.search(r'-\s*(\d{1,3})\s*%', full_text)
    # Padrão: 34% de desconto ou 34% OFF
    match_disc_text = re.search(r'(\d{1,3})\s*%\s*(?:de\s+desconto|OFF|off)', full_text, re.IGNORECASE)
    
    if match_disc_neg:
        desconto = f"{match_disc_neg.group(1)}% de desconto"
    elif match_disc_text:
        desconto = f"{match_disc_text.group(1)}% de desconto"

    # =========================================================================
    # 4. PIX (Amazon Brasil às vezes menciona)
    # =========================================================================
    has_pix = bool(re.search(r'no\s+pix|à\s+vista\s+no\s+pix', full_text, re.IGNORECASE))

    # =========================================================================
    # 5. CUPOM: "Cupom: XYZ" ou "Aplicar cupom XYZ"
    # =========================================================================
    coupon = None
    coupon_discount = None
    
    match_coupon = re.search(r'(?:Cupom|cupom|CUPOM|Aplicar cupom|aplicar cupom)\s*[:\s]+([A-Z0-9\-]+)', full_text, re.IGNORECASE)
    if match_coupon:
        coupon = match_coupon.group(1)
        # Tentar extrair desconto do cupom
        match_cupom_disc = re.search(
            rf'{re.escape(coupon)}.*?(\d+%\s*(?:OFF|de\s+desconto))', 
            full_text, re.IGNORECASE
        )
        if match_cupom_disc:
            coupon_discount = match_cupom_disc.group(1)

    # =========================================================================
    # 6. LINK E IMAGEM
    # =========================================================================
    affiliate_link = None
    image_url = None
    
    for line in reversed(lines):
        if line.startswith("http"):
            if any(line.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
                if not image_url:
                    image_url = line.split("?")[0].strip()
            elif "amazon.com" in line or "amzn.to" in line:
                if not affiliate_link:
                    affiliate_link = line.strip()
    
    if not affiliate_link:
        for line in lines:
            if line.startswith("http") and ("amazon.com" in line or "amzn.to" in line):
                affiliate_link = line.strip()
                break

    if not affiliate_link:
        return None

    # =========================================================================
    # 7. Montar Product
    # =========================================================================
    return Product(
        title=titulo,
        price_original=normalize_price_string(preco_original) if preco_original else None,
        price_discounted=normalize_price_string(preco_promocional),
        discount=desconto,
        has_pix=has_pix,
        coupon=coupon,
        coupon_discount=coupon_discount,
        affiliate_link=affiliate_link,
        image_url=image_url or "",
        store="amazon"
    )
