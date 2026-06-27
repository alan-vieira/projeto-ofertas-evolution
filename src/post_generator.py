"""
Geração de posts formatados a partir de ofertas brutas copiadas manualmente.

Orquestra a etapa intermediária do pipeline manual:
  1. Segmentação por URLs de imagem
  2. Detecção de origem (Amazon vs Shopee)
  3. Parsing estruturado → Product
  4. Formatação via formatter.format_offer

✅ Saída padronizada: idêntica ao ofertas.txt do main.py
   Formato: caption \n image_url \n\n

Uso: python -m src.post_generator
"""

import logging
from pathlib import Path
from typing import Optional, List, Tuple

from src.core.formatter import format_offer
from src.core.models import Product
from src.parsers.amazon_parser import parse_amazon_offer_block
from src.parsers.shopee_parser import parse_shopee_offer_block

logger = logging.getLogger(__name__)


def split_into_blocks_by_image(content: str) -> list[str]:
    """Segmenta texto bruto em blocos usando URLs de imagem como delimitadores."""
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    blocks = []
    current_block = []

    for line in lines:
        current_block.append(line)
        # Detecta se é URL de imagem (delimitador de fim de bloco)
        if any(line.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
            blocks.append("\n".join(current_block))
            current_block = []

    # Bloco residual sem imagem no final
    if current_block:
        blocks.append("\n".join(current_block))
    
    return blocks


def detect_and_parse_block(block_text: str) -> Optional[Product]:
    """Detecta origem e delega ao parser correto."""
    lines = [line.strip() for line in block_text.splitlines() if line.strip()]
    product_link = None
    
    # Prioridade: penúltima linha (padrão observado) ou primeira linha com http
    if len(lines) >= 2:
        candidate = lines[-2]
        if candidate.startswith("http"):
            product_link = candidate
    
    if not product_link:
        for line in lines:
            if line.startswith("http"):
                product_link = line
                break

    if not product_link:
        logger.warning("⚠️ Nenhum link de produto encontrado no bloco.")
        return None

    link_lower = product_link.lower()
    if "amzn.to" in link_lower or "amazon.com" in link_lower:
        logger.debug("🔍 Detectado: AMAZON")
        return parse_amazon_offer_block(block_text)
    elif "shopee.com.br" in link_lower or "shope.ee" in link_lower:
        logger.debug("🔍 Detectado: SHOPEE")
        return parse_shopee_offer_block(block_text)
    
    logger.warning("⚠️ Loja não identificada. Usando fallback Amazon.")
    return parse_amazon_offer_block(block_text)


def _format_post_for_file(product: Product) -> str:
    """
    Formata um Product no mesmo padrão do salvar_posts() do main.py.
    
    Formato de saída:
        caption (sem URL da imagem)
        image_url
        [linha vazia]
    
    Returns:
        str: Bloco formatado pronto para escrita em arquivo
    """
    caption = format_offer(product, include_image_url=False)
    return f"{caption}\n{product.image_url}\n\n"


def generate_posts_from_raw_input(
    input_file: str = "config/ofertas_brutas.txt",
    output_file: str = "posts_manuais.txt"
) -> int:
    """
    Processa arquivo bruto e gera posts formatados no padrão ofertas.txt.
    
    Returns:
        int: Número de posts válidos gerados
    """
    input_path = Path(input_file)
    if not input_path.exists():
        logger.error(f"❌ Arquivo não encontrado: {input_file}")
        return 0

    content = input_path.read_text(encoding="utf-8")
    blocks = split_into_blocks_by_image(content)
    
    if not blocks:
        logger.warning("⚠️ Nenhum bloco identificado. Verifique o formato do arquivo.")
        return 0

    logger.info(f"📦 {len(blocks)} blocos identificados. Processando...")
    
    # Armazenar tuplas (caption, image_url) para formato padronizado
    post_entries: List[Tuple[str, str]] = []
    parsed_count = 0

    for i, block in enumerate(blocks, 1):
        try:
            product = detect_and_parse_block(block)
            if product and product.is_valid():
                # ✅ Usar função auxiliar para garantir formato consistente
                post_entries.append(_format_post_for_file(product))
                parsed_count += 1
                logger.debug(f"✅ Bloco {i}: {product.title[:40]}...")
            else:
                logger.warning(f"⚠️ Bloco {i} ignorado (parsing falhou ou dados inválidos)")
        except Exception as e:
            logger.exception(f"❌ Erro ao processar bloco {i}: {e}")

    # ✅ Escreve APENAS UMA VEZ ao final, no formato padronizado
    if post_entries:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Join das entradas já formatadas (cada uma termina com \n\n)
        output_path.write_text("".join(post_entries), encoding="utf-8")
        logger.info(f"✅ {parsed_count}/{len(blocks)} posts salvos em {output_file}")
        logger.debug(f"📄 Formato: caption \\n image_url \\n\\n (idêntico a ofertas.txt)")
    else:
        logger.warning("⚠️ Nenhum post válido gerado.")

    return parsed_count


def main():
    """Ponto de entrada para execução autônoma."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S"
    )
    generate_posts_from_raw_input()


if __name__ == "__main__":
    main()
