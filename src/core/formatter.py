"""
Módulo para formatação de ofertas em texto legível para WhatsApp.

Converte objetos Product em mensagens prontas para envio via Evolution API,
incluindo título, preços formatados em BRL, descontos, cupons e links.

Suporte:
- Formatação monetária brasileira (R$ 1.234,56) - SEMPRE com centavos
- Markdown do WhatsApp (*negrito*, `código`)
- Limitação de caracteres para captions
- Inclusão/exclusão de URL da imagem
"""

from decimal import Decimal, InvalidOperation
from typing import Optional
import re

from src.core.models import Product


def normalize_price_string(price_str: str) -> str:
    """
    Normaliza string de preço para formato consistente com centavos.
    
    Ex: "R$1.899" → "R$1.899,00"
    Ex: "R$ 59,9" → "R$59,90"
    Ex: "129,90" → "R$129,90"
    
    Args:
        price_str: String de preço em qualquer formato brasileiro
    
    Returns:
        str: Preço normalizado como "R$X.XXX,XX"
    """
    if not price_str:
        return ""
    
    # Remover "R$" se existir e espaços
    clean = price_str.replace("R$", "").replace(" ", "").strip()
    
    if not clean:
        return "R$0,00"
    
    # Separar parte inteira e decimal
    if "," in clean:
        parts = clean.split(",")
        whole = parts[0].replace(".", "")  # Remover pontos de milhar
        cents = parts[1] if len(parts) > 1 else "00"
    else:
        # Sem vírgula: é valor inteiro
        whole = clean.replace(".", "")
        cents = "00"
    
    # Garantir 2 dígitos nos centavos
    cents = cents.ljust(2, "0")[:2]
    
    # Adicionar pontos de milhar na parte inteira
    if len(whole) > 3:
        # Inverter, agrupar de 3 em 3, adicionar ponto, desfazer
        reversed_whole = whole[::-1]
        grouped = [reversed_whole[i:i+3] for i in range(0, len(reversed_whole), 3)]
        whole = ".".join(g[::-1] for g in grouped[::-1])
    
    return f"R${whole},{cents}"


def format_brl(value: float | Decimal | str | None) -> str:
    """
    Formata valor como moeda brasileira (R$ 1.234,56).
    
    Aceita:
    - Números: 1234.5 → "R$1.234,50"
    - Strings numéricas: "1234.5" → "R$1.234,50"
    - Strings BRL: "R$1.899" → "R$1.899,00"
    - None → ""
    
    Args:
        value: Valor em qualquer formato
    
    Returns:
        str: Valor formatado em BRL ou string vazia se None
    """
    if value is None:
        return ""
    
    # Se já for string formatada em BRL, normalizar
    if isinstance(value, str) and "R$" in value:
        return normalize_price_string(value)
    
    try:
        # Converter para Decimal para precisão
        num = Decimal(str(value))
        # Formatar: R$ 1.234,56
        formatted = f"R$ {num:,.2f}"
        # Converter separadores: 1,234.56 → 1.234,56
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    except (InvalidOperation, ValueError, TypeError):
        # Fallback: tentar normalizar como string
        if isinstance(value, str):
            return normalize_price_string(value)
        return str(value) if value else ""


def format_offer(
    product: Product,
    include_image_url: bool = False,
    max_caption_length: Optional[int] = 1024,
    shorten_links: bool = False,
    emoji_style: str = "default"
) -> str:
    """
    Formata um produto como mensagem para WhatsApp + Evolution API.
    
    A mensagem inclui:
    - Título em negrito
    - Preço original (se houver) e preço com desconto (SEMPRE com centavos)
    - Indicação de pagamento via Pix (se disponível)
    - Percentual de desconto (se aplicável)
    - Cupom promocional (se disponível)
    - Link de afiliado
    - URL da imagem (opcional)
    
    Args:
        product (Product): Objeto com dados da oferta.
        include_image_url (bool): Incluir URL da imagem no caption? 
                                  False = imagem enviada como mídia separada (recomendado)
        max_caption_length (int): Limite de caracteres para o caption.
                                  None = sem limite.
        shorten_links (bool): Aplicar encurtamento nos links (requer serviço externo).
        emoji_style (str): Estilo de emojis ("default", "minimal", "none")
    
    Returns:
        str: Mensagem formatada com markdown do WhatsApp.
    """
    # Selecionar emojis baseado no estilo
    emojis = _get_emojis(emoji_style)
    
    # =========================================================================
    # LINHA DE PREÇO (com normalização de centavos)
    # =========================================================================
    
    # Normalizar preços para garantir formato consistente
    price_original_display = normalize_price_string(product.price_original) if product.price_original else None
    price_discounted_display = normalize_price_string(product.price_discounted)
    
    if product.price_original_value and product.has_discount and price_original_display:
        # Tem desconto: mostrar preço original e novo
        price_line = (
            f"{emojis['money']} De {price_original_display} por apenas "
            f"*{price_discounted_display}*"
        )
    else:
        # Sem desconto ou sem preço original
        price_line = f"{emojis['money']} Por apenas *{price_discounted_display}*"
    
    # Adicionar "no Pix" se disponível
    if product.has_pix:
        price_line += " no Pix"
    
    # =========================================================================
    # TÍTULO + PREÇO
    # =========================================================================
    post = f"*{product.title.strip()}*\n{price_line}"
    
    # =========================================================================
    # DESCONTO
    # =========================================================================
    if product.discount:
        # Limpar texto do desconto
        discount_clean = str(product.discount).strip()
        # Remover "de desconto" se presente
        discount_clean = re.sub(r"\s+de\s+desconto", "", discount_clean, flags=re.IGNORECASE)
        
        # Só incluir se não for 0%
        if discount_clean and discount_clean not in ["0%", "0"]:
            post += f"\n{emojis['chart']} *{discount_clean}*!"
    
    # =========================================================================
    # CUPOM
    # =========================================================================
    if product.coupon:
        coupon_text = f"\n{emojis['ticket']} *Cupom:* `{product.coupon}`"
        if product.coupon_discount:
            coupon_text += f" ({product.coupon_discount})"
        post += coupon_text
        
        # Mostra mensagem extra APENAS se você colocar manualmente no JSON
        if product.coupon_message:
            post += f"\n{product.coupon_message}!"
    
    # =========================================================================
    # CALL-TO-ACTION + LINKS
    # =========================================================================
    post += "\n" + emojis["cta"] + " Garanta já o seu:"
    
    # Link de afiliado (prioritário)
    affiliate_link = product.affiliate_link.strip() if product.affiliate_link else ""
    if affiliate_link:
        # Opcional: encurtar link (implementar conforme seu serviço)
        if shorten_links and hasattr(product, 'short_link'):
            affiliate_link = product.short_link or affiliate_link
        post += f"\n{affiliate_link}"
    
    # Imagem: incluir apenas se explicitamente solicitado
    if include_image_url and product.image_url:
        post += f"\n{product.image_url.strip()}"
    
    # =========================================================================
    # LIMITAR TAMANHO DO CAPTION
    # =========================================================================
    if max_caption_length and len(post) > max_caption_length:
        post = _truncate_caption(post, max_caption_length, affiliate_link)
    
    return post


def _get_emojis(style: str) -> dict:
    """Retorna dicionário de emojis baseado no estilo."""
    styles = {
        "default": {
            "money": "💰",
            "chart": "📉",
            "ticket": "🎟️",
            "cta": "👇",
            "pix": "💳",
        },
        "minimal": {
            "money": "R$",
            "chart": "↓",
            "ticket": "Cupom:",
            "cta": "Link:",
            "pix": "Pix",
        },
        "none": {
            "money": "",
            "chart": "",
            "ticket": "",
            "cta": "",
            "pix": "",
        },
    }
    return styles.get(style, styles["default"])


def _truncate_caption(caption: str, max_length: int, affiliate_link: str) -> str:
    """Trunca caption preservando links no final."""
    link_section = f"\n👇 Garanta já o seu:\n{affiliate_link}"
    reserved = len(link_section) + 50
    available = max_length - reserved
    
    if available < 100:
        available = max_length - len(affiliate_link) - 20
    
    truncated = caption[:available].rsplit("\n", 1)[0]
    return f"{truncated}\n...\n{link_section}"


def format_simple(product: Product) -> str:
    """Formatação simplificada para logs/debug."""
    lines = [
        product.title,
        f"Preço: {normalize_price_string(product.price_discounted)}",
    ]
    
    if product.price_original:
        lines.append(f"De: {normalize_price_string(product.price_original)}")
    
    if product.discount:
        lines.append(f"Desconto: {product.discount}")
    
    if product.has_pix:
        lines.append("Pagamento via Pix: Sim")
    
    if product.coupon:
        lines.append(f"Cupom: {product.coupon}")
    
    lines.append(f"Link: {product.affiliate_link}")
    
    return "\n".join(lines)


def format_html(product: Product) -> str:
    """Formatação em HTML básico para email ou web."""
    price_discounted = normalize_price_string(product.price_discounted)
    price_original = normalize_price_string(product.price_original) if product.price_original else None
    
    html = f"""
    <div class="product-offer">
        <h3>{product.title}</h3>
        <p class="price">
            {f'<span class="old-price">{price_original}</span>' if price_original else ''}
            <span class="discounted-price"><strong>{price_discounted}</strong></span>
            {'<span class="pix">no Pix</span>' if product.has_pix else ''}
        </p>
        {f'<p class="discount">{product.discount}</p>' if product.discount else ''}
        {f'<p class="coupon">Cupom: <code>{product.coupon}</code></p>' if product.coupon else ''}
        <p class="cta"><a href="{product.affiliate_link}">Comprar agora</a></p>
    </div>
    """
    return html.strip()
