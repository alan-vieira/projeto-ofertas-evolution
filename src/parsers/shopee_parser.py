"""
Parser para blocos de texto copiados manualmente da Shopee.
✅ Lógica ajustada para o formato real dos seus dados:
   - Dois preços: primeiro = promocional, segundo = original
   - Desconto no formato: -75%
   - Cupom genérico: "Cupons de loja"
"""
import re
import logging
from src.core.models import Product
from src.core.formatter import normalize_price_string

logger = logging.getLogger(__name__)

def _extract_prices_shopee(full_text: str) -> tuple[str | None, str]:
    """
    Extrai preços no formato específico da Shopee.
    ✅ CORREÇÃO: Ignora números seguidos de unidades de medida (1,60m, 200g, etc.)
    """
    # ✅ Regex com NEGATIVE LOOKAHEAD para excluir unidades de medida
    # (?!\s*[mck]g?[²³]?\b) ignora: 1,60m, 200g, 1,5kg, 10cm², etc.
    # (?!\s*[x×]\s*\d) ignora dimensões: 1,60x80cm, 100×200
    price_pattern = (
        r'R?\$?\s*([\d.]+,\d{2})'
        r'(?!\s*[mck]g?[²³]?\b)'           # ignora 1,60m, 200g, 1,5kg
        r'(?!\s*[x×]\s*\d)'                # ignora 1,60x80
        r'(?!\s*(?:pol|″|′|l|ml|un|und)\b)' # ignora 32pol, 500ml, 1un
    )
    
    matches = re.findall(price_pattern, full_text)
    
    if not matches:
        return None, None
    
    # Converter para float para comparação numérica
    def to_float(price_str: str) -> float:
        return float(price_str.replace(".", "").replace(",", "."))
    
    # ✅ FILTRO DE PLAUSIBILIDADE: ignora preços < R$10 (improvável para produtos reais)
    valid_matches = [m for m in matches if to_float(m) >= 10.00]
    
    if not valid_matches:
        # Fallback: se todos foram filtrados, usa os originais (pode ser produto muito barato)
        logger.warning(f"⚠️ Todos os preços filtrados por plausibilidade: {matches}")
        valid_matches = matches
    
    # Criar lista de tuplas (texto_original, valor_float)
    prices = [(m, to_float(m)) for m in valid_matches]
    
    if len(prices) == 1:
        # Só um preço: é o promocional
        return None, f"R${prices[0][0]}"
    
    # Shopee: primeiro preço listado = promocional, segundo = original
    # Mas vamos validar pelo valor para garantir
    prices_sorted = sorted(prices, key=lambda x: x[1])
    
    preco_promocional = f"R${prices_sorted[0][0]}"  # Menor valor
    preco_original = f"R${prices_sorted[-1][0]}"     # Maior valor
    
    # Se forem iguais, retornar só um
    if preco_original == preco_promocional:
        return None, preco_promocional
    
    return preco_original, preco_promocional


def parse_shopee_offer_block(text: str) -> Product | None:
    """
    Parse de bloco de texto manual da Shopee.
    ✅ Correção: títulos que começam com números agora são aceitos.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None

    full_text = "\n".join(lines)
    
    # =========================================================================
    # 1. TÍTULO: Primeira linha longa que não é preço, link, desconto ou cupom
    # =========================================================================
    titulo = None
    for line in lines:
        # Ignorar apenas padrões específicos, não qualquer linha que comece com número
        if (len(line) > 20 and 
            not line.startswith("http") and 
            not re.match(r'^-\s*\d+%', line) and  # Ignora: -75%, - 26%
            not re.match(r'^R?\$?\s*[\d.]+,\d{2}$', line) and  # Ignora: R$1.234,56 (preço exato)
            not re.match(r'^[\d.]+,\d{2}$', line) and  # Ignora: 123,45 (preço sem R$)
            not re.match(r'^cupom', line, re.IGNORECASE) and  # Ignora: Cupom: XYZ
            not re.match(r'^cupons?\s+de\s+loja', line, re.IGNORECASE)):  # Ignora: Cupons de loja
            titulo = line.strip().upper()
            break
    
    if not titulo:
        return None

    # =========================================================================
    # 2. PREÇOS: Lógica específica para Shopee
    # =========================================================================
    preco_original, preco_promocional = _extract_prices_shopee(full_text)
    
    if not preco_promocional:
        return None  # Preço é obrigatório

    # =========================================================================
    # 3. DESCONTO: Suporta -75%, 75% OFF, 75% de desconto
    # =========================================================================
    desconto = None
    
    match_disc_neg = re.search(r'-\s*(\d{1,3})\s*%', full_text)
    match_disc_text = re.search(r'(\d{1,3})\s*%\s*(?:OFF|de\s+desconto)', full_text, re.IGNORECASE)
    
    if match_disc_neg:
        desconto = f"{match_disc_neg.group(1)}% de desconto"
    elif match_disc_text:
        desconto = f"{match_disc_text.group(1)}% de desconto"

    # =========================================================================
    # 4. PIX
    # =========================================================================
    has_pix = bool(re.search(r'no\s+pix|à\s+vista\s+no\s+pix', full_text, re.IGNORECASE))

    # =========================================================================
    # 5. CUPOM
    # =========================================================================
    coupon = None
    coupon_discount = None
    
    if re.search(r'cupons?\s+de\s+loja', full_text, re.IGNORECASE):
        coupon = "Cupom de loja"
    else:
        match_coupon = re.search(r'(?:Cupom|cupom|CUPOM|Use)\s*[:\s]+([A-Z0-9\-]+)', full_text)
        if match_coupon:
            coupon = match_coupon.group(1)
            match_cupom_disc = re.search(
                rf'{re.escape(coupon)}.*?(\d+%\s*OFF|\d+%\s+de\s+desconto)', 
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
            elif "shopee.com.br" in line or "shope.ee" in line:
                if not affiliate_link:
                    affiliate_link = line.strip()
    
    if not affiliate_link:
        for line in lines:
            if line.startswith("http") and ("shopee.com.br" in line or "shope.ee" in line):
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
        store="shopee"
    )
