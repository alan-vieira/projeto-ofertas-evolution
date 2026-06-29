import sys
from pathlib import Path
from dotenv import load_dotenv
import requests
import base64
import json

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config_loader import Config

def print_separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def main():
    print_separator("🔍 DIAGNÓSTICO EVOLUTION API")
    
    # Carregar configurações
    config = Config()
    api_url = config.get("evolution.api_url")
    instance = config.get("evolution.instance_name")
    api_key = config.get("evolution.api_key")
    
    print(f"📡 URL: {api_url}")
    print(f"🤖 Instância: {instance}")
    print(f"🔑 API Key: {'*' * 8}{api_key[-4:] if api_key else '????'}")
    
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json"
    }
    
    # 1. Testar conexão básica
    print_separator("1️⃣ TESTE DE CONEXÃO BÁSICA")
    try:
        response = requests.get(api_url, timeout=10)
        print(f"✅ Status: {response.status_code}")
        data = response.json()
        print(f"✅ Versão: {data.get('version')}")
        print(f"✅ WhatsApp Web Version: {data.get('whatsappWebVersion')}")
        print(f"✅ Manager: {data.get('manager')}")
    except Exception as e:
        print(f"❌ Erro: {e}")
        return
    
    # 2. Listar instâncias
    print_separator("2️⃣ LISTAR INSTÂNCIAS")
    try:
        response = requests.get(
            f"{api_url}/instance/fetchInstances",
            headers=headers,
            timeout=10
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            instances = response.json()
            print(f"Total de instâncias: {len(instances)}")
            
            for inst in instances:
                name = inst.get("name") or inst.get("instanceName")
                state = inst.get("state", "unknown")
                print(f"  - {name} (estado: {state})")
            
            instance_exists = any(
                (inst.get("name") == instance or inst.get("instanceName") == instance)
                for inst in instances
            )
            
            if instance_exists:
                print(f"\n✅ Instância '{instance}' ENCONTRADA")
            else:
                print(f"\n⚠️ Instância '{instance}' NÃO ENCONTRADA")
        else:
            print(f"❌ Erro: {response.text}")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    # 3. Verificar estado da conexão
    print_separator("3️⃣ ESTADO DA CONEXÃO")
    try:
        response = requests.get(
            f"{api_url}/instance/connectionState/{instance}",
            headers=headers,
            timeout=10
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Resposta completa: {json.dumps(data, indent=2)}")
            
            state = data.get("instance", {}).get("state")
            print(f"\n📊 Estado atual: {state}")
            
            if state == "open":
                print("✅ Instância CONECTADA")
            elif state == "connecting":
                print("⏳ Instância CONECTANDO")
            elif state == "close":
                print("❌ Instância DESCONECTADA")
            else:
                print(f"⚠️ Estado desconhecido: {state}")
        else:
            print(f"❌ Erro: {response.text}")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    # 4. Gerar QR Code
    print_separator("4️⃣ GERAR QR CODE")
    try:
        print("⏳ Tentando gerar QR Code (pode levar alguns segundos)...")
        
        response = requests.get(
            f"{api_url}/instance/connect/{instance}",
            headers=headers,
            timeout=60
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ QR Code gerado com sucesso!")
            print(f"Chaves retornadas: {list(data.keys())}")
            
            if "base64" in data:
                base64_data = data["base64"]
                print(f"\n📱 QR Code (primeiros 100 chars): {base64_data[:100]}...")
                
                # Salvar como imagem
                try:
                    if "," in base64_data:
                        base64_data = base64_data.split(",")[1]
                    img_data = base64.b64decode(base64_data)
                    with open("qrcode_teste.png", "wb") as f:
                        f.write(img_data)
                    print(f"💾 QR Code salvo em: qrcode_teste.png")
                except Exception as e:
                    print(f"⚠️ Erro ao salvar imagem: {e}")
            
            if "pairingCode" in data:
                print(f"🔢 Pairing Code: {data['pairingCode']}")
            
            # Salvar resposta completa
            with open("qrcode_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"💾 Resposta completa salva em: qrcode_response.json")
            
        else:
            print(f"❌ Erro ao gerar QR Code")
            print(f"Resposta: {response.text}")
            
    except requests.exceptions.Timeout:
        print("⏱️ TIMEOUT (60s) - O servidor demorou muito para responder")
        print("💡 Isso indica que o QR Code não está sendo gerado")
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Tentar criar instância se não existir
    print_separator("5️⃣ CRIAR INSTÂNCIA (se necessário)")
    try:
        print(f"Tentando criar instância '{instance}'...")
        
        response = requests.post(
            f"{api_url}/instance/create",
            headers=headers,
            json={
                "instanceName": instance,
                "integration": "WHATSAPP-BAILEYS",
                "qrcode": True
            },
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.text}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    print_separator("✅ DIAGNÓSTICO CONCLUÍDO")
    print("📁 Arquivos gerados:")
    print("  - qrcode_teste.png (se QR Code foi gerado)")
    print("  - qrcode_response.json (resposta completa da API)")

if __name__ == "__main__":
    main()