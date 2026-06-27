# test_fixed.py
import requests
import json
from dotenv import load_dotenv
import os
import sys

# Adicionar src ao path
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

API_KEY = os.getenv("EVOLUTION_API_KEY", "").strip()
INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME", "VendaBot")
BASE_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080").rstrip("/")

print(f"🔐 Testando check_connection() corrigido...")
print(f"   API Key: {API_KEY[:10]}...{API_KEY[-4:]}")
print(f"   Instância: {INSTANCE}\n")

headers = {"apikey": API_KEY}
endpoint = f"{BASE_URL}/instance/connectionState/{INSTANCE}"

resp = requests.get(endpoint, headers=headers, timeout=10)
print(f"📡 Status: {resp.status_code}")

if resp.status_code == 200:
    data = resp.json()
    
    # Lógica corrigida (igual ao check_connection atualizado)
    state = (
        (data.get("instance") or {}).get("state") or
        data.get("state") or 
        data.get("status") or 
        data.get("connectionState") or
        (True if data.get("connected") is True else None)
    )
    
    print(f"🔍 State extraído: {state}")
    
    if state in ["open", "connected", True]:
        print("✅ SUCESSO! Instância conectada.")
        print("🚀 Agora execute: python send_only.py")
    else:
        print(f"⚠️ Instância não está 'open'. Estado atual: {state}")
        print("📱 Escaneie QR Code em http://localhost:8080 se necessário")
else:
    print(f"❌ Erro: {resp.text}")
