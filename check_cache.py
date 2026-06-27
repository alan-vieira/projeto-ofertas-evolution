# check_cache.py
from src.cache import get_cache

cache = get_cache()
data = cache._load_cache()

print(f"📦 Total no cache: {len(data)} itens\n")

for url, entry in data.items():
    product = entry.get("product", {})
    title = product.get("title", "")
    price = product.get("price_discounted", "")
    
    # Filtrar Brastemp ou mostrar todos
    if 'brastemp' in title.lower() or 'bwj14ab' in url.lower():
        print(f"🔍 Brastemp encontrada:")
        print(f"   URL: {url[:70]}...")
        print(f"   Título: {title[:50]}...")
        print(f"   Preço: {price}")
        print()

# Se quiser ver TODOS os itens, descomente a linha abaixo:
# for url, entry in data.items(): print(f"{entry['product'].get('price_discounted')} - {entry['product'].get('title')[:40]}")
