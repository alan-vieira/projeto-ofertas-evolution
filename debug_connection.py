# debug_connection.py
import requests
import json
import sys
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME", "VendaBot")
BASE_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080").rstrip("/")

print(f"🔐 Configurações:")
print(f"   API Key: {API_KEY[:10]}...{API_KEY[-4:] if API_KEY else 'N/A'}")
print(f"   Instância: {INSTANCE}")
print(f"   Base URL: {BASE_URL}\n")

if not API_KEY:
    print("❌ API Key não encontrada no .env")
    sys.exit(1)

headers = {"apikey": API_KEY}

# Testar MÚLTIPLAS rotas possíveis (v2.x tem variações)
endpoints_to_try = [
    f"{BASE_URL}/instance/connectionState/{INSTANCE}",
    f"{BASE_URL}/instance/{INSTANCE}/connectionState", 
    f"{BASE_URL}/instance/{INSTANCE}/fetchInstance",
    f"{BASE_URL}/instance/fetchInstance?instanceName={INSTANCE}",
]

print("🔍 Testando endpoints possíveis:\n")

found_working = False

for i, endpoint in enumerate(endpoints_to_try, 1):
    print(f"{i}. GET {endpoint.replace(BASE_URL, '')}")
    try:
        resp = requests.get(endpoint, headers=headers, timeout=10)
        print(f"   Status: {resp.status_code}")
        
        try:
            data = resp.json()
            # Mostrar apenas campos relevantes
            if isinstance(data, dict):
                state = data.get("state") or data.get("status") or data.get("connectionState")
                print(f"   📡 State: {state}")
                if state == "open" or data.get("connected") is True:
                    print(f"   ✅ ESTE ENDPOINT FUNCIONA! State: {state}")
                    print(f"   💡 Endpoint correto: {endpoint.replace(BASE_URL, '')}")
                    found_working = True
                    break
            print(f"   📦 Response: {json.dumps(data, indent=2)[:300]}")
        except json.JSONDecodeError:
            print(f"   📦 Response (texto): {resp.text[:300]}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Erro de rede: {e}")
    print()

if not found_working:
    print("❌ Nenhum endpoint retornou state='open'")
    print("💡 Verifique: 1) API Key correta, 2) Instância conectada no dashboard, 3) Versão da Evolution")
    sys.exit(1)
else:
    print("\n🎯 Próximo passo: atualize check_connection() para usar este endpoint!")
    