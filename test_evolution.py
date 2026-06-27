# test_evolution.py
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config_loader import Config
from src.evolution_sender import EvolutionSender

def main():
    print("🔍 Carregando configurações...")
    config = Config()

    # Usa config.get() direto (fallback .env funciona corretamente)
    api_url = config.get("evolution.api_url")
    instance = config.get("evolution.instance_name")
    api_key = config.get("evolution.api_key")
    group_jid = config.get("whatsapp.group_jid")

    print(f"📡 URL: {api_url}")
    print(f"🤖 Instância: {instance}")
    print(f"🔑 API Key: {'*' * 8}{api_key[-4:] if api_key else '????'}")
    print(f"📱 Grupo: {group_jid}\n")

    if not all([api_url, instance, api_key, group_jid]):
        print("❌ Configurações incompletas. Verifique config/settings.json ou .env")
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
            print("💡 Acesse http://localhost:8080 e escaneie o QR Code da instância 'VendaBot'")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    main()
