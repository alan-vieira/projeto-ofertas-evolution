"""
Sistema de cache simples para produtos extraídos.

Evita re-scraping do mesmo produto dentro de um período configurável,
economizando tempo e reduzindo risco de bloqueio.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from src.core.models import Product

logger = logging.getLogger(__name__)

CACHE_FILE = "cache/products.json"
DEFAULT_TTL_HOURS = 24


class Cache:
    """Cache baseado em arquivo JSON com TTL."""
    
    def __init__(self, ttl_hours: int = DEFAULT_TTL_HOURS):
        """
        Inicializa cache.
        
        Args:
            ttl_hours: Tempo de vida do cache em horas
        """
        self.ttl_hours = ttl_hours
        self.cache_file = Path(CACHE_FILE)
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Garante que o diretório do cache exista."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_cache(self) -> dict:
        """Carrega cache do arquivo."""
        if not self.cache_file.exists():
            return {}
        
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"⚠️ Erro ao carregar cache: {e}")
            return {}
    
    def _save_cache(self, data: dict):
        """Salva cache no arquivo."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.warning(f"⚠️ Erro ao salvar cache: {e}")
    
    def get(self, url: str) -> Optional[Product]:
        """
        Obtém produto do cache se válido.
        
        Args:
            url: URL do produto
        
        Returns:
            Product se encontrado e válido, None caso contrário
        """
        cache = self._load_cache()
        entry = cache.get(url)
        
        if not entry:
            return None
        
        # Validar TTL
        try:
            cached_at = datetime.fromisoformat(entry["cached_at"])
            if datetime.now() - cached_at < timedelta(hours=self.ttl_hours):
                logger.debug(f"♻️ Cache hit: {url}")
                return Product.from_dict(entry["product"])
            else:
                logger.debug(f" Cache expirado: {url}")
                # Remover entrada expirada
                del cache[url]
                self._save_cache(cache)
        except (KeyError, ValueError) as e:
            logger.warning(f"⚠️ Erro ao validar cache: {e}")
        
        return None
    
    def set(self, url: str, product: Product):
        """
        Salva produto no cache.
        
        Args:
            url: URL do produto
            product: Objeto Product a ser cacheado
        """
        try:
            cache = self._load_cache()
            cache[url] = {
                "product": product.to_dict(),
                "cached_at": datetime.now().isoformat()
            }
            self._save_cache(cache)
            logger.debug(f"💾 Cache saved: {url}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao salvar no cache: {e}")
    
    def clear(self):
        """Limpa todo o cache."""
        if self.cache_file.exists():
            self.cache_file.unlink()
            logger.info("🗑️ Cache limpo")
    
    def cleanup_expired(self) -> int:
        """
        Remove entradas expiradas do cache.
        
        Returns:
            Número de entradas removidas
        """
        cache = self._load_cache()
        initial_count = len(cache)
        
        expired_urls = []
        for url, entry in cache.items():
            try:
                cached_at = datetime.fromisoformat(entry["cached_at"])
                if datetime.now() - cached_at >= timedelta(hours=self.ttl_hours):
                    expired_urls.append(url)
            except (KeyError, ValueError):
                expired_urls.append(url)
        
        for url in expired_urls:
            del cache[url]
        
        self._save_cache(cache)
        removed = initial_count - len(cache)
        
        if removed > 0:
            logger.info(f"🧹 {removed} entradas expiradas removidas do cache")
        
        return removed


# Instância global para uso conveniente
_cache_instance: Optional[Cache] = None


def get_cache(ttl_hours: int = DEFAULT_TTL_HOURS) -> Cache:
    """Obtém instância singleton do cache."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = Cache(ttl_hours)
    return _cache_instance


# Funções convenience para uso direto
def get_cached(url: str) -> Optional[Product]:
    """Obtém produto do cache."""
    return get_cache().get(url)


def set_cache(url: str, product: Product):
    """Salva produto no cache."""
    get_cache().set(url, product)
