"""
Definição do modelo de dados para produtos extraídos de marketplaces.

Contém a classe Product, usada para representar ofertas do Magazine Luiza,
Mercado Livre e outros varejistas suportados.

Integração: Compatível com Evolution API, cache e formatação avançada.
"""

from dataclasses import dataclass, field
from typing import Optional, Literal
from datetime import datetime
import re


# Tipo seguro para stores suportadas
StoreType = Literal["mercado_livre", "magalu", "amazon", "shopee", "outros"]


@dataclass
class Product:
    """
    Representa uma oferta de produto extraída de um marketplace.

    Valores monetários são armazenados como strings formatadas (ex: "R$129,90")
    para preservar a exibição exata do site original, evitando problemas de
    arredondamento e facilitando a formatação direta na mensagem final.

    Attributes:
        title (str): Título do produto.
        price_discounted (str): Preço com desconto, formatado (ex: "R$1.299,90").
        affiliate_link (str): URL do produto com parâmetro de afiliado.
        image_url (str): URL direta da imagem do produto.
        store (StoreType): Marketplace de origem.
        price_original (Optional[str]): Preço original antes do desconto.
        discount (Optional[str]): Descrição do desconto (ex: "20% de desconto").
        coupon (Optional[str]): Código do cupom promocional.
        coupon_discount (Optional[str]): Descrição do benefício do cupom.
        has_pix (bool): Indica se aceita pagamento via Pix.
        id (Optional[str]): Identificador único para deduplicação (SKU, URL hash, etc).
        extracted_at (Optional[datetime]): Timestamp da extração para analytics.

    Example:
        >>> p = Product(
        ...     title="Notebook Lenovo IdeaPad 1",
        ...     price_discounted="R$2.879,10",
        ...     price_original="R$3.499,00",
        ...     discount="17% de desconto",
        ...     has_pix=True,
        ...     affiliate_link="https://meli.la/xyz",
        ...     image_url="https://http2.mlstatic.com/D_NQ_NP_2X_712683...webp",
        ...     store="mercado_livre"
        ... )
        >>> print(p.title)
        'Notebook Lenovo IdeaPad 1'
        >>> print(p.price_discounted_value)
        2879.10
        >>> print(p.discount_percent)
        17.0
    """

    # Campos obrigatórios
    title: str
    price_discounted: str
    affiliate_link: str
    image_url: str
    store: StoreType

    # Campos opcionais
    price_original: Optional[str] = None
    discount: Optional[str] = None
    coupon: Optional[str] = None
    coupon_discount: Optional[str] = None
    has_pix: bool = False
    id: Optional[str] = None  # Para deduplicação
    extracted_at: datetime = field(default_factory=datetime.now)  # Para analytics

    # NOVOS CAMPOS PARA CUPOM (adicione aqui)
    coupon_code: Optional[str] = None           # Ex: "CASASBAHIATV"
    coupon_message: Optional[str] = None        # Ex: "Aplique o cupom..."
    price_with_coupon: Optional[str] = None     # Ex: "R$ 2.990,33"

    # ========================================================================
    # PROPRIEDADES DERIVADAS (cálculos e parsing)
    # ========================================================================

    @property
    def price_discounted_value(self) -> Optional[float]:
        """
        Extrai valor numérico do preço formatado para comparações.
        
        Ex: "R$1.299,90" → 1299.90
        Retorna None se não conseguir parsear.
        
        Returns:
            float | None: Valor numérico do preço ou None
        """
        return self._parse_brl(self.price_discounted)

    @property
    def price_original_value(self) -> Optional[float]:
        """
        Extrai valor numérico do preço original formatado.
        
        Returns:
            float | None: Valor numérico do preço original ou None
        """
        return self._parse_brl(self.price_original) if self.price_original else None

    @property
    def discount_percent(self) -> Optional[float]:
        """
        Extrai percentual de desconto como float.
        
        Ex: "20% de desconto" → 20.0
        Ex: "15% OFF" → 15.0
        
        Returns:
            float | None: Percentual de desconto ou None
        """
        if not self.discount:
            return None
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", str(self.discount))
        return float(match.group(1)) if match else None

    @property
    def mimetype(self) -> str:
        """
        Infere mimetype da imagem pela extensão da URL.
        
        Returns:
            str: MIME type (ex: "image/jpeg", "image/webp", "image/png")
        
        Example:
            >>> p = Product(..., image_url="https://example.com/img.webp")
            >>> p.mimetype
            'image/webp'
        """
        ext = self.image_url.lower().split("?")[0].split(".")[-1]
        return {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
        }.get(ext, "image/jpeg")

    @property
    def has_discount(self) -> bool:
        """
        Verifica se o produto tem desconto (preço original > preço com desconto).
        
        Returns:
            bool: True se tem desconto válido
        """
        if not self.price_original_value or not self.price_discounted_value:
            return False
        return self.price_original_value > self.price_discounted_value

    @property
    def savings(self) -> Optional[float]:
        """
        Calcula economia em valor absoluto.
        
        Ex: R$1.599,00 - R$1.299,90 = R$299,10
        
        Returns:
            float | None: Valor economizado ou None
        """
        if self.has_discount:
            return self.price_original_value - self.price_discounted_value
        return None

    # ========================================================================
    # MÉTODOS ESTÁTICOS DE UTILIDADE
    # ========================================================================

    @staticmethod
    def _parse_brl(value: Optional[str]) -> Optional[float]:
        """
        Parse de string BRL para float.
        
        Ex: "R$1.299,90" → 1299.90
        Ex: "R$ 99,90" → 99.90
        Ex: "1.500" → 1500.0
        
        Args:
            value: String formatada em BRL
        
        Returns:
            float | None: Valor numérico ou None se falhar
        """
        if not value:
            return None
        try:
            # Remove "R$", espaços, e caracteres não numéricos exceto , e .
            clean = re.sub(r"[^\d,.]", "", str(value))
            
            # Detectar formato: se tiver vírgula, é decimal brasileiro
            if "," in clean:
                # Formato brasileiro: 1.299,90 → 1299.90
                clean = clean.replace(".", "").replace(",", ".")
            else:
                # Formato sem centavos ou já em formato US: 1299.90
                pass
            
            return float(clean)
        except (ValueError, AttributeError, TypeError):
            return None

    # ========================================================================
    # MÉTODOS DE VALIDAÇÃO E SERIALIZAÇÃO
    # ========================================================================

    def is_valid(self) -> bool:
        """
        Validação mínima para envio.
        
        Verifica:
        - Título não vazio
        - Preço com desconto presente e válido
        - Link de afiliado começa com http
        - URL da imagem começa com http
        
        Returns:
            bool: True se produto é válido para envio
        """
        checks = [
            bool(self.title and self.title.strip()),
            bool(self.price_discounted and self.price_discounted.strip()),
            bool(self.affiliate_link and self.affiliate_link.strip().startswith("http")),
            bool(self.image_url and self.image_url.strip().startswith("http")),
        ]
        return all(checks)

    def to_dict(self) -> dict:
        """
        Serializa para dict (útil para logging, webhook, cache).
        
        Returns:
            dict: Representação em dicionário do produto
        """
        return {
            "id": self.id,
            "title": self.title,
            "price_discounted": self.price_discounted,
            "price_original": self.price_original,
            "discount": self.discount,
            "coupon": self.coupon,
            "coupon_discount": self.coupon_discount,
            "has_pix": self.has_pix,
            "affiliate_link": self.affiliate_link,
            "image_url": self.image_url,
            "store": self.store,
            "extracted_at": self.extracted_at.isoformat() if self.extracted_at else None,
            # Campos derivados úteis
            "price_discounted_value": self.price_discounted_value,
            "discount_percent": self.discount_percent,
            "has_discount": self.has_discount,
            "savings": self.savings,
            # NOVOS CAMPOS DE CUPOM
            "coupon_code": self.coupon_code,
            "coupon_message": self.coupon_message,
            "price_with_coupon": self.price_with_coupon,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        """
        Cria instância a partir de dict (útil para carregar de cache/JSON).
        
        Args:
            data: Dicionário com dados do produto
        
        Returns:
            Product: Instância criada
        
        Example:
            >>> data = {"title": "Teste", "price_discounted": "R$99,90", ...}
            >>> p = Product.from_dict(data)
        """
        # Converter string de timestamp para datetime se presente
        if "extracted_at" in data and isinstance(data["extracted_at"], str):
            data = data.copy()  # Não modificar o original
            try:
                data["extracted_at"] = datetime.fromisoformat(data["extracted_at"])
            except ValueError:
                data["extracted_at"] = datetime.now()
        
        # Filtrar apenas campos válidos do dataclass
        valid_fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid_fields)

    # ========================================================================
    # REPRESENTAÇÃO E DEBUG
    # ========================================================================

    def __str__(self) -> str:
        """Representação string simples."""
        return f"Product(title={self.title[:50]}..., price={self.price_discounted}, store={self.store})"

    def __repr__(self) -> str:
        """Representação para debug."""
        return (
            f"Product("
            f"title={self.title!r}, "
            f"price_discounted={self.price_discounted!r}, "
            f"store={self.store!r}, "
            f"valid={self.is_valid()})"
        )

    def summary(self) -> str:
        """
        Retorna resumo formatado para logs.
        
        Returns:
            str: Resumo legível do produto
        """
        lines = [
            f"📦 {self.title[:60]}",
            f"💰 {self.price_discounted}",
            f"🔗 {self.affiliate_link[:50]}...",
            f"🏪 {self.store}",
        ]
        
        if self.price_original:
            lines.append(f"📉 De {self.price_original}")
        
        if self.discount:
            lines.append(f"🎯 {self.discount}")
        
        if self.has_pix:
            lines.append("💳 Pix disponível")
        
        if self.coupon:
            lines.append(f"🎟️ Cupom: {self.coupon}")
        
        return "\n  ".join(lines)
