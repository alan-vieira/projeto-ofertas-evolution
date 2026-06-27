"""
Envia ofertas via Evolution API.

Modos de operação:
  1. Cache (padrão): Lê ofertas extraídas pelo main.py
  2. Arquivo: Lê posts formatados no padrão ofertas.txt (caption\nimage_url\n\n)

Uso:
  python send_only.py                      # Lê do cache
  python send_only.py --input arquivo.txt  # Lê do arquivo especificado
"""

import sys
import time
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

from src.core.config_loader import Config
from src.core.formatter import format_offer, normalize_price_string
from src.cache import get_cache
from src.image_processor import process_image_to_base64

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)
logger = logging.getLogger(__name__)


def parse_post_file(filepath: str) -> list[dict]:
    """
    Parse de arquivo no formato padronizado: caption\nimage_url\n\n
    
    Returns:
        list[dict]: Lista de {caption, image_url}
    """
    path = Path(filepath)
    if not path.exists():
        logger.error(f"❌ Arquivo não encontrado: {filepath}")
        return []
    
    content = path.read_text(encoding="utf-8")
    # Separar por duplo newline (padrão do formato)
    blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
    
    posts = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 2:
            continue
        
        # Última linha = image_url, resto = caption
        image_url = lines[-1].strip()
        caption = "\n".join(lines[:-1]).strip()
        
        if caption and image_url.startswith("http"):
            posts.append({"caption": caption, "image_url": image_url})
    
    logger.debug(f"📋 {len(posts)} posts parseados de {filepath}")
    return posts


def send_offers(
    offers: list[dict],
    config: Config,
    source_label: str = "ofertas"
) -> int:
    """
    Envia lista de ofertas via Evolution API com processamento opcional de imagem.
    
    Args:
        offers: Lista de {caption, image_url} ou {product} do cache
        config: Configurações do projeto
        source_label: Label para logs ("cache" ou nome do arquivo)
    
    Returns:
        int: Número de envios bem-sucedidos
    """
    group_jid = config.group_jid
    if not group_jid:
        logger.error("❌ Configure WHATSAPP_GROUP_JID no .env")
        return 0
    
    # Configurações de mídia
    media_cfg = config.media or {}
    process_images = media_cfg.get("process_images", False)
    target_size = tuple(media_cfg.get("target_size", [1080, 1080]))
    quality = media_cfg.get("quality", 95)
    
    logger.info(f"🖼️ Processamento: {'ATIVADO' if process_images else 'DESATIVADO'}")
    if process_images:
        logger.info(f"📐 Target: {target_size[0]}x{target_size[1]} | Quality: {quality}%")
    
    # Configurações Evolution API
    api_key = config.evolution.get("api_key", "").strip()
    instance = config.evolution.get("instance_name", "VendaBot")
    base_url = config.evolution.get("api_url", "http://localhost:8080").rstrip("/")
    headers = {"apikey": api_key}
    delay = config.whatsapp.get("delay_between_offers_sec", 10)
    
    # Verificar conexão
    try:
        resp = requests.get(
            f"{base_url}/instance/connectionState/{instance}",
            headers=headers,
            timeout=10
        )
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")
        data = resp.json()
        state = (data.get("instance") or {}).get("state")
        if state != "open":
            logger.error(f"❌ Instância não conectada. Estado: {state}")
            logger.error("🔗 Escaneie QR Code em http://localhost:8080")
            return 0
        logger.info("✅ Instância Evolution conectada")
    except Exception as e:
        logger.error(f"❌ Falha ao verificar conexão: {e}")
        return 0
    
    # Enviar cada oferta
    sent_count = 0
    for idx, offer in enumerate(offers, 1):
        try:
            # Extrair dados (suporta formato cache ou arquivo)
            if "product" in offer:
                # Formato cache: offer = {product: Product}
                from src.core.models import Product
                product = Product.from_dict(offer["product"])
                caption = format_offer(product, include_image_url=False)
                image_url = product.image_url
                title_display = product.title[:35]
                price_display = normalize_price_string(product.price_discounted)
            else:
                # Formato arquivo: offer = {caption, image_url}
                caption = offer["caption"]
                image_url = offer["image_url"]
                # Extrair título da primeira linha do caption (entre *)
                import re
                title_match = re.match(r'\*(.+?)\*', caption)
                title_display = title_match.group(1)[:35] if title_match else "Oferta"
                price_display = "N/A"
            
            # 🔥 PROCESSAMENTO DE IMAGEM
            media_payload = image_url
            mimetype = "image/jpeg"
            
            if process_images and image_url.startswith("http"):
                logger.info(f"⏳ Processando imagem: {title_display}...")
                processed = process_image_to_base64(image_url, target_size, quality)
                if processed:
                    media_payload = processed
                    mimetype = "image/jpeg"
                    logger.debug(f"✅ Imagem processada: {len(processed)//1024}KB base64")
                else:
                    logger.warning(f"⚠️ Falha ao processar. Usando URL original.")
            
            # Montar payload
            if media_payload.startswith("data:image"):
                # Base64: precisa de fileName na Evolution v2
                payload = {
                    "number": group_jid,
                    "mediatype": "image",
                    "mimetype": mimetype,
                    "media": media_payload,
                    "fileName": "oferta.jpg",
                    "caption": caption,
                    "delay": 1200,
                    "linkPreview": False
                }
                endpoint = f"{base_url}/message/sendMedia/{instance}"
            else:
                # URL direta
                payload = {
                    "number": group_jid,
                    "mediatype": "image",
                    "mimetype": mimetype,
                    "media": media_payload,
                    "caption": caption,
                    "delay": 1200,
                    "linkPreview": False
                }
                endpoint = f"{base_url}/message/sendMedia/{instance}"
            
            # Enviar
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            
            if resp.status_code in [200, 201]:
                sent_count += 1
                logger.info(f"📤 [{idx}/{len(offers)}] {title_display}... | {price_display}")
            else:
                logger.warning(f"⚠️ Falha [{idx}]: {resp.status_code} - {resp.text[:150]}")
            
            # Rate limiting
            if idx < len(offers):
                time.sleep(delay)
                
        except Exception as e:
            logger.exception(f"❌ Erro ao enviar oferta {idx}: {e}")
            continue
    
    logger.info(f"🎉 Envio concluído: {sent_count}/{len(offers)} {source_label} enviadas")
    return sent_count


def main():
    """Ponto de entrada com suporte a argumentos."""
    load_dotenv()
    config = Config()
    
    # Parse de argumentos
    input_file = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ("--input", "-i") and i + 1 < len(args):
            input_file = args[i + 1]
            i += 2
        else:
            i += 1
    
    # Carregar ofertas
    if input_file:
        # Modo arquivo: ler posts formatados
        logger.info(f"📂 Lendo ofertas de: {input_file}")
        offers = parse_post_file(input_file)
        source_label = f"posts de {Path(input_file).name}"
    else:
        # Modo cache: ler ofertas extraídas
        logger.info("📂 Lendo ofertas do cache")
        cache = get_cache()
        cached_items = cache._load_cache()
        offers = [{"product": entry["product"]} for entry in cached_items.values()]
        source_label = "ofertas do cache"
    
    if not offers:
        logger.warning("⚠️ Nenhuma oferta para enviar")
        return
    
    logger.info(f"📦 {len(offers)} {source_label} para envio")
    logger.info(f"🔌 Enviando para {config.group_jid} via VendaBot\n")
    
    # Enviar
    sent = send_offers(offers, config, source_label=source_label)
    
    # Resumo
    print(f"\n🎉 Conclusão: {sent}/{len(offers)} enviadas!")


if __name__ == "__main__":
    main()
