import os
import sys
import requests
import base64
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME", "VendaBot")
API_KEY = os.getenv("EVOLUTION_API_KEY")

headers = {
    "apikey": API_KEY,
    "Content-Type": "application/json"
}

print("=" * 70)
print("🔌 CONECTAR INSTÂNCIA EVOLUTION API")
print("=" * 70)
print(f"📡 URL: {API_URL}")
print(f"🤖 Instância: {INSTANCE}")
print(f"🔑 API Key: ********{API_KEY[-4:]}")
print()

# 1. Verificar status atual
print("1️⃣ Verificando status da instância...")
try:
    r = requests.get(f"{API_URL}/instance/connectionState/{INSTANCE}", headers=headers, timeout=10)
    print(f"   Status HTTP: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        state = data.get("instance", {}).get("state")
        print(f"   Estado: {state}")
        
        if state == "open":
            print("   ✅ Instância JÁ ESTÁ CONECTADA!")
            print("   Pode usar normalmente.")
            sys.exit(0)
        elif state == "connecting":
            print("   ⏳ Instância está conectando...")
            print("   Aguarde ou gere novo QR Code.")
        else:
            print(f"   ⚠️ Instância não conectada (estado: {state})")
    else:
        print(f"   ❌ Erro: {r.text}")
except Exception as e:
    print(f"   ❌ Erro: {e}")

# 2. Gerar QR Code
print("\n2️⃣ Gerando QR Code...")
print("   ⏳ Aguarde (pode levar alguns segundos)...")

try:
    r = requests.get(f"{API_URL}/instance/connect/{INSTANCE}", headers=headers, timeout=60)
    print(f"   Status HTTP: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        print(f"   ✅ QR Code gerado com sucesso!")
        print(f"   Chaves retornadas: {list(data.keys())}")
        
        # Salvar QR Code como imagem
        if "base64" in data:
            base64_data = data["base64"]
            
            # Remover prefixo "data:image/png;base64," se existir
            if "," in base64_data:
                base64_data = base64_data.split(",")[1]
            
            try:
                img_data = base64.b64decode(base64_data)
                with open("qrcode.png", "wb") as f:
                    f.write(img_data)
                print(f"   💾 QR Code salvo em: qrcode.png")
                print(f"   📱 Abra o arquivo e escaneie com o WhatsApp!")
            except Exception as e:
                print(f"   ⚠️ Erro ao salvar imagem: {e}")
        
        # Mostrar Pairing Code se existir
        if "pairingCode" in data:
            print(f"   🔢 Pairing Code: {data['pairingCode']}")
            print(f"   💡 Você pode usar este código no WhatsApp em 'Conectar com número de telefone'")
        
        # Salvar resposta completa
        with open("qrcode_response.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"   💾 Resposta completa salva em: qrcode_response.json")
        
        # Mostrar URL do Manager
        print(f"\n   🌐 Ou acesse: {API_URL}/manager/")
        print(f"   🔑 API Key: {API_KEY}")
        
    else:
        print(f"   ❌ Erro ao gerar QR Code")
        print(f"   Resposta: {r.text}")
        
except requests.exceptions.Timeout:
    print("   ⏱️ TIMEOUT (60s) - O servidor demorou muito para responder")
    print("   💡 Verifique os logs do Docker: docker compose logs -f evolution-api")
except Exception as e:
    print(f"   ❌ Erro: {e}")
    import traceback
    traceback.print_exc()

# 3. Verificar status novamente
print("\n3️⃣ Verificando status após geração do QR Code...")
try:
    r = requests.get(f"{API_URL}/instance/connectionState/{INSTANCE}", headers=headers, timeout=10)
    if r.status_code == 200:
        data = r.json()
        state = data.get("instance", {}).get("state")
        print(f"   Estado atual: {state}")
        
        if state == "connecting":
            print("   ✅ QR Code gerado! Aguardando escaneamento...")
            print("   📱 Escaneie o QR Code com o WhatsApp")
        elif state == "open":
            print("   ✅ Instância CONECTADA!")
        else:
            print(f"   ⚠️ Estado: {state}")
    else:
        print(f"   ❌ Erro: {r.text}")
except Exception as e:
    print(f"   ❌ Erro: {e}")

print("\n" + "=" * 70)
print("✅ PROCESSO CONCLUÍDO")
print("=" * 70)