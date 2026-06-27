"""Factory pattern para extratores de marketplace."""
import logging
from typing import Optional, Callable, Dict

logger = logging.getLogger(__name__)
EXTRACTORS: Dict[str, Callable] = {}

def register_extractor(store: str, func: Callable):
    EXTRACTORS[store] = func
    logger.debug(f"✅ Extrator registrado: {store}")

def get_extractor(store: str) -> Optional[Callable]:
    extractor = EXTRACTORS.get(store)
    if not extractor:
        logger.error(f"❌ Extrator não encontrado para: {store}")
        logger.info(f"📋 Extratores disponíveis: {list(EXTRACTORS.keys())}")
    return extractor

def list_extractors() -> list:
    return list(EXTRACTORS.keys())

# ============================================================================
# IMPORTS RELATIVOS (corrigido)
# ============================================================================
try:
    from .magalu import extrair_dados_produto_magalu
    register_extractor("magalu", extrair_dados_produto_magalu)
except ImportError as e:
    logger.warning(f"⚠️ Falha ao importar Magalu: {e}")

try:
    from .mercadolivre import extrair_dados_produto_mercadolivre
    register_extractor("mercado_livre", extrair_dados_produto_mercadolivre)
except ImportError as e:
    logger.warning(f"⚠️ Falha ao importar Mercado Livre: {e}")
    