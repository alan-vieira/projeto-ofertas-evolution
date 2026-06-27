"""
Carregador unificado de configurações.

Suporta:
- JSON (config/settings.json)
- Variáveis de ambiente (.env)
- Fallback para valores padrão
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    """
    Configuração centralizada com hierarquia:
    1. Variáveis de ambiente (.env)
    2. Arquivo JSON (config/settings.json)
    3. Valores padrão
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton para evitar recarregamento."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    def _load(self):
        """Carrega configurações de todas as fontes."""
        # 1. Carregar .env
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv(env_file)
            logger.debug("✅ .env carregado")
        else:
            logger.warning("⚠️ Arquivo .env não encontrado")
        
        # 2. Carregar config/settings.json
        config_path = Path("config/settings.json")
        self._config = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            logger.debug(f"✅ config/settings.json carregado")
        else:
            logger.warning("⚠️ config/settings.json não encontrado")
        
        # 3. Configurar logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Configura logging baseado nas configurações."""
        log_cfg = self.get("logging", {})
        level_str = log_cfg.get("level", "INFO").upper()
        level = getattr(logging, level_str, logging.INFO)
        
        # Formato
        log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        date_format = "%d/%m/%Y %H:%M:%S"
        
        # Handlers
        handlers = []
        
        # Console
        if log_cfg.get("console", True):
            handlers.append(logging.StreamHandler())
        
        # Arquivo
        log_file = log_cfg.get("file")
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5*1024*1024,  # 5MB
                backupCount=5,
                encoding="utf-8"
            )
            handlers.append(file_handler)
        
        # Configurar root logger
        logging.basicConfig(
            level=level,
            format=log_format,
            datefmt=date_format,
            handlers=handlers,
            force=True
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém valor de configuração com busca hierárquica.
        
        Args:
            key: Chave hierárquica (ex: "evolution.api_url")
            default: Valor padrão se não encontrado
        
        Returns:
            Valor da configuração ou default
        
        Example:
            >>> config.get("evolution.api_url")
            'http://localhost:8080'
        """
        # 1. Tentar no JSON
        value = self._config
        for part in key.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break
        
        # 2. Fallback para .env (converte key.path → KEY_PATH)
        if value is None:
            env_key = key.upper().replace(".", "_")
            value = os.getenv(env_key)
            
            if value is not None:
                # Converter tipos simples
                if value.lower() in ("true", "false"):
                    return value.lower() == "true"
                try:
                    return int(value)
                except ValueError:
                    try:
                        return float(value)
                    except ValueError:
                        return value
        
        return value if value is not None else default
    
    # ========================================================================
    # ACESSO DINÂMICO A QUALQUER SEÇÃO
    # ========================================================================
    def __getattr__(self, name: str) -> dict:
        """
        Permite acesso dinâmico a qualquer seção: config.scraping, config.nova_secao, etc.
        
        Returns:
            dict com as configurações da seção, ou dict vazio se não existir
        """
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return self.get(name, {})
    
    # Properties mantidas para compatibilidade com código existente
    @property
    def evolution(self) -> dict:
        """Configurações da Evolution API."""
        return self.get("evolution", {})
    
    @property
    def whatsapp(self) -> dict:
        """Configurações do WhatsApp."""
        return self.get("whatsapp", {})
    
    @property
    def media(self) -> dict:
        """Configurações de mídia."""
        return self.get("media", {})
    
    @property
    def offers(self) -> dict:
        """Configurações de ofertas."""
        return self.get("offers", {})
    
    @property
    def scraping(self) -> dict:  # ✅ NOVO: propriedade para scraping
        """Configurações de scraping e navegação."""
        return self.get("scraping", {})
    
    @property
    def group_jid(self) -> Optional[str]:
        """JID do grupo WhatsApp (crítico para envio)."""
        jid = self.whatsapp.get("group_jid") or os.getenv("WHATSAPP_GROUP_JID")
        if not jid:
            logger.error("❌ group_jid não configurado! Envios falharão.")
        return jid
    
    def validate(self) -> bool:
        """
        Valida configurações críticas.
        
        Returns:
            bool: True se todas as configurações obrigatórias estiverem presentes
        """
        required = [
            ("evolution.api_url", "URL da Evolution API"),
            ("evolution.instance_name", "Nome da instância"),
            ("evolution.api_key", "API Key da Evolution"),
            ("whatsapp.group_jid", "JID do grupo WhatsApp"),
        ]
        
        valid = True
        for key, description in required:
            if not self.get(key):
                logger.error(f"❌ {description} ({key}) não configurado")
                valid = False
        
        return valid