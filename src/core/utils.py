"""
Utilitários gerais para o pipeline de ofertas.
"""
import re
from typing import Optional


def calcular_ou_validar_desconto(
    desconto_extruido: Optional[str],
    preco_original: Optional[str],
    preco_desconto: Optional[str]
) -> Optional[str]:
    """
    Valida desconto extraído ou calcula fallback a partir dos preços.
    
    Args:
        desconto_extruido: Desconto no formato "XX% OFF" ou None
        preco_original: Preço original no formato "R$ X,XX" ou None
        preco_desconto: Preço com desconto no formato "R$ X,XX" ou None
    
    Returns:
        str no formato "XX% OFF" se válido, None caso contrário
    """
    # 1. Tenta validar desconto extraído
    if desconto_extruido:
        match = re.search(r"(\d{1,2})%", desconto_extruido)
        if match:
            pct = int(match.group(1))
            if 1 <= pct <= 99:  # valida faixa realista
                return f"{pct}% OFF"
    
    # 2. Fallback: calcula a partir dos preços
    def parse(price: Optional[str]) -> float:
        """Converte string de preço 'R$ 1.234,56' para float 1234.56"""
        if not price:
            return 0.0
        try:
            clean = price.replace("R$", "").replace(".", "").replace(",", ".").strip()
            return float(clean)
        except (ValueError, AttributeError):
            return 0.0
    
    orig = parse(preco_original)
    desc = parse(preco_desconto)
    
    # Calcula porcentagem apenas se os valores forem válidos
    if orig > 0 and 0 < desc < orig:
        pct = round(((orig - desc) / orig) * 100)
        if 1 <= pct <= 99:  # valida faixa realista
            return f"{pct}% OFF"
    
    return None


def formatar_preço_brl(valor: float) -> str:
    """
    Formata float para string no padrão BRL: R$ 1.234,56
    
    Args:
        valor: Valor numérico
    
    Returns:
        String formatada no padrão brasileiro
    """
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_preço_brl(price_str: Optional[str]) -> float:
    """
    Converte string no formato 'R$ 1.234,56' para float 1234.56
    
    Args:
        price_str: String no formato brasileiro ou None
    
    Returns:
        Float representando o valor ou 0.0 se falhar
    """
    if not price_str:
        return 0.0
    try:
        clean = price_str.replace("R$", "").replace(".", "").replace(",", ".").strip()
        return float(clean)
    except (ValueError, AttributeError):
        return 0.0


def sanitize_text(text: str, max_length: int = 200) -> str:
    """
    Limpa e limita texto para uso em captions/logs.
    
    Args:
        text: Texto original
        max_length: Tamanho máximo da string retornada
    
    Returns:
        Texto limpo, sem múltiplos espaços e truncado se necessário
    """
    if not text:
        return ""
    
    # Remove múltiplos espaços e quebras de linha
    cleaned = " ".join(text.split())
    
    # Trunca se necessário
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length-3] + "..."
    
    return cleaned.strip()