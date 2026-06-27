# test_price_fix.py
import sys, logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

# Ativar logs detalhados
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

from src.extractors.mercadolivre import extrair_dados_produto_mercadolivre

# Link da máquina Brastemp que estava com preço errado
test_url = "https://meli.la/2vR2no7"  # ← Confirme se é este o link

print(f"🔗 Testando extração de preço: {test_url}\n")
product = extrair_dados_produto_mercadolivre(test_url, close_browser=True)

if product:
    print(f"\n{'='*60}")
    print(f"✅ EXTRAÇÃO CONCLUÍDA")
    print(f"{'='*60}")
    print(f"📦 Título: {product.title}")
    print(f"💰 Preço extraído: {product.price_discounted}")
    print(f"📉 Desconto: {product.discount}")
    print(f"💳 Pix: {'Sim' if product.has_pix else 'Não'}")
    print(f"{'='*60}")
    
    # Validação do preço
    try:
        price_val = float(product.price_discounted.replace("R$", "").replace(".", "").replace(",", "."))
        if price_val > 100:  # Preço razoável para uma máquina de lavar
            print("🎯 PREÇO CORRETO! ✅")
        else:
            print(f"⚠️ Preço suspeito: R$ {price_val:.2f} (esperado ~1899.00)")
    except:
        print("⚠️ Não foi possível validar o preço numericamente")
else:
    print("\n❌ Falha na extração. Verifique logs/screenshots/")
