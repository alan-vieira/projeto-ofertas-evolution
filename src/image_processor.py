"""
Processador de imagens para WhatsApp.
Redimensiona proporcionalmente (com upscale permitido), centraliza em fundo branco 1080x1080
e converte para base64 PURO (compatível com Evolution API v2).

✅ Lógica idêntica à sua função download_image original.
"""
import logging
import base64
import requests
from io import BytesIO
from PIL import Image
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def process_image_to_base64(
    image_url: str,
    target_size: Tuple[int, int] = (1080, 1080),
    quality: int = 95
) -> Optional[str]:
    """
    Baixa, processa e retorna APENAS a string base64 pura.
    
    ✅ Mesma lógica da sua função download_image original:
    - Redimensionamento proporcional (sem crop)
    - Upscale permitido (imagens pequenas são ampliadas)
    - Centralizado em fundo branco 1080x1080
    - Base64 puro (sem prefixo) para Evolution API v2
    """
    try:
        logger.debug(f"📥 Baixando: {image_url[:60]}...")
        
        # Download
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(image_url, headers=headers, timeout=30)
        r.raise_for_status()

        with Image.open(BytesIO(r.content)) as img:
            # Converter para RGB com fundo branco se tiver transparência
            if img.mode in ("RGBA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Redimensionar com upscale se necessário, mantendo proporção
            original_width, original_height = img.size

            # Evita divisão por zero
            if original_width == 0 or original_height == 0:
                raise ValueError("Imagem tem dimensão zero")

            # ✅ Sua lógica original: permite upscale
            scale = min(target_size[0] / original_width, target_size[1] / original_height)
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)

            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Criar fundo branco e colar centralizado
            final_img = Image.new("RGB", target_size, (255, 255, 255))
            x = (target_size[0] - new_width) // 2
            y = (target_size[1] - new_height) // 2
            final_img.paste(img_resized, (x, y))

            # ✅ Converter para base64 PURO (sem prefixo, sem salvar em arquivo)
            buffer = BytesIO()
            final_img.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            logger.debug(f"✅ Processada: {original_width}x{original_height} → {new_width}x{new_height} (canvas 1080x1080)")
            
            # Retorna apenas o base64 puro (Evolution v2 valida melhor assim)
            return b64

    except Exception as e:
        logger.error(f"❌ Erro ao processar imagem: {e}")
        return None
