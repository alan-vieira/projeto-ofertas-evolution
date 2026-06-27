"""
Script principal do pipeline de extração e envio de ofertas.

Migrado para Evolution API:
- Extração: Playwright (Magalu, Mercado Livre) - MANTIDO
- Envio: Evolution API via HTTP REST - NOVO

@author: Alan Silva Vieira
@version: 2.1.1
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config_loader import Config
from src.core.formatter import format_offer
from src.core.models import Product
from src.evolution_sender import EvolutionSender
from src.cache import get_cached, set_cache
from src.extractors import get_extractor, list_extractors

logger = logging.getLogger(__name__)


def carregar_links(links_file: str) -> List[str]:
    """
    Carrega lista de URLs de afiliado.
    
    Args:
        links_file: Caminho para arquivo com links
    
    Returns:
        Lista de URLs válidas
    """
    links = []
    path = Path(links_file)
    
    if not path.exists():
        logger.error(f"❌ Arquivo de links não encontrado: {links_file}")
        return links
    
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            url = line.strip()
            if url and not url.startswith("#"):
                links.append(url)
            else:
                logger.debug(f"⏭️ Ignorando linha {line_num}: '{line[:30]}...'")
    
    logger.info(f"🔗 {len(links)} links carregados de {links_file}")
    return links


def identificar_loja(url: str) -> Optional[str]:
    """
    Identifica a store baseada na URL do afiliado.
    
    Args:
        url: URL do produto
    
    Returns:
        Nome da store ou None se não identificada
    """
    if any(domain in url for domain in ["meli.la/", "mercadolivre.com.br/sec/", "mercadolivre.com/sec/"]):
        return "mercado_livre"
    if "divulgador.magalu.com" in url or "https://magazineluiza.onelink.me/" in url:
        return "magalu"
    if "amzn.to/" in url or "amazon.com" in url:
        return "amazon"
    if "shopee." in url:
        return "shopee"
    return None


def processar_link(url: str, config: Config) -> Optional[Product]:
    """
    Extrai produto de uma URL, usando cache se disponível.
    
    Args:
        url: URL do produto
        config: Objeto de configuração
    
    Returns:
        Product se extraído com sucesso, None caso contrário
    """
    # 1. Tentar cache primeiro
    cached = get_cached(url)
    if cached:
        logger.info(f"♻️ Cache hit: {url[:60]}...")
        return cached
    
    # 2. Identificar store
    store = identificar_loja(url)
    if not store:
        logger.warning(f"⚠️ Loja não identificada: {url}")
        return None
    
    # 3. Obter extrator
    extractor = get_extractor(store)
    if not extractor:
        logger.error(f"❌ Extrator não registrado para '{store}'")
        logger.info(f"📋 Extratores disponíveis: {list_extractors()}")
        return None
    
    # 4. Extrair com retry para erros transitórios
    logger.info(f"📦 Extraindo [{store}]: {url[:60]}...")
    
    try:
        # Importa o wrapper com retry (só para Mercado Livre por enquanto)
        if store == "mercado_livre":
            from src.extractors.mercadolivre import extrair_com_retry, extrair_dados_produto_mercadolivre
            product = extrair_com_retry(
                url=url,
                config=config,
                extractor_func=extrair_dados_produto_mercadolivre,
                max_retries=2
            )
        else:
            # Outras lojas usam o fluxo padrão
            product = extractor(url_afiliado=url, close_browser=False)
            
    except Exception as e:
        logger.exception(f"❌ Erro ao extrair: {e}")
        return None
    
    # ✅ CORREÇÃO CRÍTICA: Verificar se product é None ANTES de usar
    if product is None:
        logger.warning(f"❌ Falha na extração: {url}")
        return None
    
    # 5. Salvar no cache (só se product for válido)
    try:
        set_cache(url, product)
    except Exception as e:
        logger.warning(f"⚠️ Falha ao salvar no cache: {e}")
    
    # 6. Validar produto
    if not product.is_valid():
        logger.warning(f"⚠️ Produto inválido: {product.title}")
        return None
    
    logger.info(f"✅ Extraído: {product.title[:50]}...")
    return product


def salvar_posts(posts: List[Optional[Product]], output_file: str) -> int:
    """
    Salva ofertas formatadas no arquivo de saída.
    
    Args:
        posts: Lista de produtos (pode conter None)
        output_file: Caminho do arquivo de saída
    
    Returns:
        Número de posts salvos
    """
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    count = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for product in posts:
            # ✅ Verificação de segurança: pular None
            if product and product.is_valid():
                # Formato compatível com read_offers_from_file
                caption = format_offer(product, include_image_url=False)
                f.write(caption + "\n")
                f.write(product.image_url + "\n\n")
                count += 1
    
    logger.info(f"✅ {count} posts salvos em {output_file}")
    return count


def enviar_para_whatsapp_evolution(posts: List[Optional[Product]], config: Config) -> int:
    """Envia ofertas via Evolution API com processamento de imagem."""
    
    group_jid = config.group_jid
    if not group_jid:
        logger.error("❌ Configure 'whatsapp.group_jid'")
        return 0
    
    # Configurações de mídia
    media_cfg = config.media or {}
    process_images = media_cfg.get("process_images", False)
    target_size = tuple(media_cfg.get("target_size", [1080, 1080]))
    quality = media_cfg.get("quality", 95)
    
    logger.info(f"🖼️ Processamento: {'ATIVADO' if process_images else 'DESATIVADO'}")
    
    sender = EvolutionSender(
        api_url=config.evolution.get("api_url", "http://localhost:8080"),
        instance_name=config.evolution.get("instance_name", "VendaBot"),
        api_key=config.evolution.get("api_key"),
        delay_seconds=config.whatsapp.get("delay_between_offers_sec", 10),
        timeout=config.evolution.get("timeout_seconds", 60),
        max_retries=config.evolution.get("max_retries", 3)
    )
    
    if not sender.check_connection():
        logger.error("❌ Instância não conectada")
        return 0
    
    # Filtrar apenas posts válidos (exclui None e inválidos)
    valid_posts = [p for p in posts if p and p.is_valid()]
    if not valid_posts:
        logger.warning("⚠️ Nenhum post válido para envio")
        return 0
    
    logger.info(f"📲 Iniciando envio de {len(valid_posts)} ofertas...")
    
    sent_count = 0
    for idx, product in enumerate(valid_posts, 1):
        try:
            caption = format_offer(product, include_image_url=False, max_caption_length=1024)
            
            # 🔥 PROCESSAR IMAGEM
            media_payload = product.image_url
            mimetype = getattr(product, 'mimetype', 'image/jpeg')
            
            if process_images and product.image_url:
                logger.info(f"⏳ Processando: {product.title[:35]}...")
                try:
                    from src.image_processor import process_image_to_base64
                    processed = process_image_to_base64(product.image_url, target_size, quality)
                    if processed:
                        media_payload = processed
                        mimetype = "image/jpeg"
                    else:
                        logger.warning("⚠️ Falha no processamento. Usando URL original.")
                except ImportError:
                    logger.warning("⚠️ Módulo image_processor não encontrado. Usando URL original.")
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao processar imagem: {e}")
            
            # Enviar
            success = sender.send_media(
                number=group_jid,
                media_url=media_payload,
                caption=caption,
                mimetype=mimetype,
                link_preview=False
            )
            
            if success:
                sent_count += 1
                logger.info(f"📤 [{idx}/{len(valid_posts)}] Enviado: {product.title[:40]}...")
            else:
                logger.warning(f"⚠️ Falha [{idx}]: {product.title[:40]}...")
            
            if idx < len(valid_posts):
                time.sleep(config.whatsapp.get("delay_between_offers_sec", 10))
                
        except Exception as e:
            logger.exception(f"❌ Erro no envio {idx}: {e}")
            continue
    
    logger.info(f"🎉 Envio concluído: {sent_count}/{len(valid_posts)}")
    return sent_count


def main() -> None:
    """Pipeline principal: extração → formatação → envio."""
    
    # Habilita debug mode do extrator ML via variável de ambiente
    if os.getenv("ML_DEBUG", "false").lower() == "true":
        logger.warning("🐛 ML_DEBUG ativado: screenshots e HTML serão salvos em logs/")
    
    print(f"\n{'='*70}")
    print(f"🚀 PIPELINE DE OFERTAS - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    # Carregar configuração
    config = Config()
    
    # Validar configurações críticas
    if not config.validate():
        logger.error("❌ Configurações inválidas. Verifique .env e config/settings.json")
        return
    
    # Preparar diretórios
    Path(config.media.get("download_folder", "images")).mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)
    Path("cache").mkdir(parents=True, exist_ok=True)
    
    # Carregar links
    links = carregar_links(config.offers.get("links_file", "config/links.txt"))
    if not links:
        logger.error("❌ Nenhum link encontrado para processar")
        return
    
    # Extrair produtos
    logger.info(f"\n📦 INICIANDO EXTRAÇÃO DE {len(links)} PRODUTOS")
    products: List[Optional[Product]] = []
    
    for i, url in enumerate(links, 1):
        logger.info(f"\n🔗 Processando {i}/{len(links)}")
        product = processar_link(url, config)
        products.append(product)
        
        # Delay entre requests para evitar rate limiting
        if i < len(links):
            time.sleep(3)
    
    # Salvar posts
    output_file = config.offers.get("input_file", "ofertas.txt")
    salvar_posts(products, output_file)
    
    # Após salvar ofertas.txt, processe também o arquivo manual
    if Path("config/ofertas_brutas.txt").exists():
        logger.info("📝 Processando ofertas manuais...")
        try:
            from src.post_generator import generate_posts_from_raw_input
            generate_posts_from_raw_input("config/ofertas_brutas.txt", "posts_manuais.txt")
        except Exception as e:
            logger.warning(f"⚠️ Falha ao processar ofertas manuais: {e}")
    
    # Enviar para WhatsApp
    print(f"\n{'='*70}")
    
    if config.whatsapp.get("auto_send", False):
        # Envio automático (sem perguntar)
        enviados = enviar_para_whatsapp_evolution(products, config)
    else:
        # Envio interativo
        try:
            resposta = input("\n❓ Deseja enviar as ofertas agora? (s/n): ").lower().strip()
            if resposta in ("s", "sim", "y", "yes"):
                enviados = enviar_para_whatsapp_evolution(products, config)
            else:
                logger.info("📤 Envio cancelado pelo usuário. Posts salvos para envio posterior.")
                enviados = 0
        except (KeyboardInterrupt, EOFError):
            logger.info("⚠️ Envio interrompido pelo usuário.")
            enviados = 0
    
    # Resumo final
    print(f"\n{'='*70}")
    print(f"📊 RESUMO:")
    print(f"  • Links processados: {len(links)}")
    print(f"  • Produtos extraídos: {len([p for p in products if p])}")
    print(f"  • Posts salvos: {len([p for p in products if p and p.is_valid()])}")
    print(f"  • Envios realizados: {enviados}")
    print(f"{'='*70}\n")
    
    logger.info("🎉 PIPELINE FINALIZADO!")


if __name__ == "__main__":
    main()