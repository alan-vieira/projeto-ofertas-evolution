# test_formatter.py
from src.core.formatter import normalize_price_string, format_brl

# Testar normalização
tests = [
    ("R$1.899", "R$1.899,00"),
    ("R$59,9", "R$59,90"),
    ("129,90", "R$129,90"),
    ("R$ 2.084,88", "R$2.084,88"),
    ("99", "R$99,00"),
]

print("🔍 Testando normalize_price_string():")
for input_val, expected in tests:
    result = normalize_price_string(input_val)
    status = "✅" if result == expected else "❌"
    print(f"{status} '{input_val}' → '{result}' (esperado: '{expected}')")

# Testar format_brl com valores numéricos
print("\n🔍 Testando format_brl():")
print(f"✅ 1899.0 → '{format_brl(1899.0)}'")
print(f"✅ 'R$1.899' → '{format_brl('R$1.899')}'")
print(f"✅ None → '{format_brl(None)}'")
