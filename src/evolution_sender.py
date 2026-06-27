"""
Cliente HTTP para Evolution API - envio de mídia para WhatsApp.

Substitui o whatsapp_sender.py baseado em Playwright/PyAutoGUI por
chamadas REST diretas à Evolution API v2.3.7+.
"""

import time
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class EvolutionSender:
    """
    Sender para Evolution API v2.x (compatível com v2.3.7)
    
    Envio de mensagens de mídia (imagem/vídeo) e texto para WhatsApp
    via API REST, com rate limiting, retry e tratamento de erros.
    """
    
    def __init__(
        self,
        api_url: str,
        instance_name: str,
        api_key: str,
        delay_seconds: int = 2,
        timeout: int = 60,
        max_retries: int = 3
    ):
        if not api_url or not instance_name or not api_key:
            raise ValueError(
                "❌ Configuração incompleta!\n"
                "   Verifique se .env ou config/settings.json estão preenchidos com:\n"
                "   - EVOLUTION_API_URL\n"
                "   - EVOLUTION_INSTANCE_NAME\n"
                "   - EVOLUTION_API_KEY"
            )
        
        self.base_url = api_url.rstrip("/")
        self.instance = instance_name
        self.api_key = api_key
        self.delay = delay_seconds
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }
        self._last_send = 0
    
    def _rate_limit(self):
        """Aplica delay mínimo entre envios para evitar rate limiting."""
        elapsed = time.time() - self._last_send
        if elapsed < self.delay:
            sleep_time = self.delay - elapsed
            logger.debug(f"⏳ Rate limiting: aguardando {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self._last_send = time.time()
    
    def _get_endpoint(self, path: str) -> str:
        """Constrói endpoint completo."""
        return f"{self.base_url}{path}"
    
    def check_connection(self) -> bool:
        """
        Verifica se a instância está conectada ao WhatsApp.
        Compatível com Evolution API v2.3.7 (resposta aninhada em 'instance').
        """
        try:
            # Endpoint correto para v2.3.7
            endpoint = f"{self.base_url}/instance/connectionState/{self.instance}"
            
            response = requests.get(
                endpoint,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # 🔍 Estrutura v2.3.7: { "instance": { "state": "open" } }
                state = (
                    # Caminho principal (v2.3.7)
                    (data.get("instance") or {}).get("state") or
                    # Fallbacks para outras versões
                    data.get("state") or 
                    data.get("status") or 
                    data.get("connectionState") or
                    # Booleano direto
                    (True if data.get("connected") is True else None)
                )
                
                if state in ["open", "connected", True]:
                    logger.debug(f"✅ Instância '{self.instance}' conectada (state: {state})")
                    return True
                else:
                    logger.debug(f"⚠️ Instância '{self.instance}' estado: {state}")
                    return False
            
            logger.warning(f"⚠️ Erro HTTP {response.status_code} ao verificar conexão")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro de rede ao verificar conexão: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao verificar conexão: {e}")
            return False
    
    def send_media(
        self,
        number: str,
        media_url: str,
        caption: str,
        mimetype: str = "image/jpeg",
        link_preview: bool = False
    ) -> bool:
        """
        Envia imagem ou vídeo para número/grupo via Evolution API.
        
        Args:
            number: Número de destino ou JID de grupo
            media_url: URL pública da mídia ou base64
            caption: Legenda da mídia (markdown do WhatsApp suportado)
            mimetype: MIME type da mídia
            link_preview: Se True, gera preview de links na caption
        
        Returns:
            bool: True se enviado com sucesso
        """
        mediatype = "image" if mimetype.startswith("image") else "video"
        
        payload = {
            "number": number,
            "mediatype": mediatype,
            "mimetype": mimetype,
            "media": media_url,
            "caption": caption,
            "delay": 1200,
            "linkPreview": link_preview
        }
        
        endpoint = self._get_endpoint(f"/message/sendMedia/{self.instance}")
        
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                
                logger.debug(f"📤 Enviando mídia para {number} (tentativa {attempt+1}/{self.max_retries})")
                
                response = requests.post(
                    endpoint,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    msg_id = result.get("message", {}).get("key", {}).get("id", "N/A")
                    logger.info(f"✅ Mídia enviada: {msg_id}")
                    return True
                    
                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"⚠️ Rate limit da Evolution (tentativa {attempt+1}), aguardando {wait_time}s")
                    time.sleep(wait_time)
                    continue
                    
                elif response.status_code == 403:
                    logger.error(f"❌ API Key inválida ou instância não encontrada")
                    return False
                    
                elif response.status_code == 400:
                    error_msg = response.json().get("error", "Bad Request")
                    logger.error(f"❌ Erro na requisição: {error_msg}")
                    return False
                    
                else:
                    logger.error(f"❌ Erro {response.status_code}: {response.text[:200]}")
                    return False
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Timeout na requisição (tentativa {attempt+1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError:
                logger.error(f"❌ Erro de conexão com Evolution API")
                return False
            except Exception as e:
                logger.error(f"❌ Erro inesperado: {e}")
                return False
        
        logger.error(f"❌ Falha após {self.max_retries} tentativas")
        return False
    
    def send_text(
        self,
        number: str,
        text: str,
        link_preview: bool = False
    ) -> bool:
        """Envia mensagem de texto para número/grupo."""
        payload = {
            "number": number,
            "text": text,
            "delay": 1200,
            "linkPreview": link_preview
        }
        
        endpoint = self._get_endpoint(f"/message/sendText/{self.instance}")
        
        try:
            self._rate_limit()
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Texto enviado para {number}")
                return True
            else:
                logger.error(f"❌ Erro ao enviar texto: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar texto: {e}")
            return False
