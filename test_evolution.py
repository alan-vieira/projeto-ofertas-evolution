# test_evolution.py
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

# IMPORTANTE: Usar os.getenv() diretamente, não Config()
from src.evolution_sender import EvolutionSender

def main():
    print("🔍 Carregando configurações (via os.getenv)...")
    
    # Usar os.getenv() diretamente
    api_url = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
    instance = os.getenv("EVOLUTION_INSTANCE_NAME", "VendaBot")
    api_key = os.getenv("EVOLUTION_API_KEY")
    group_jid = os.getenv("WHATSAPP_GROUP_JID")

    print(f"📡 URL: {api_url}")
    print(f"🤖 Instância: {instance}")
    print(f"🔑 API Key: {'*' * 8}{api_key[-4:] if api_key else '????'}")
    print(f"📱 Grupo: {group_jid}\n")

    if not all([api_url, instance, api_key, group_jid]):
        print("❌ Configurações incompletas. Verifique .env")
        print(f"   api_url: {api_url}")
        print(f"   instance: {instance}")
        print(f"   api_key: {api_key}")
        print(f"   group_jid: {group_jid}")
        return

    print("🔌 Testando conexão com Evolution API...")
    try:
        sender = EvolutionSender(
            api_url=api_url,
            instance_name=instance,
            api_key=api_key
        )
        
        if sender.check_connection():
            print("✅ SUCESSO! Instância conectada e pronta.")
        else:
            print("❌ Instância NÃO conectada.")
            print("💡 Acesse http://localhost:8080 e escaneie o QR Code")
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()