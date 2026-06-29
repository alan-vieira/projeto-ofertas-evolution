import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.evolution_sender import EvolutionSender

def main():
    print("=" * 70)
    print("📱 TESTE DE ENVIO DE MENSAGEM (CORRIGIDO)")
    print("=" * 70)
    
    # Carregar configurações
    api_url = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
    instance = os.getenv("EVOLUTION_INSTANCE_NAME", "VendaBot")
    api_key = os.getenv("EVOLUTION_API_KEY")
    group_jid = os.getenv("WHATSAPP_GROUP_JID")
    
    print(f"📡 URL: {api_url}")
    print(f"🤖 Instância: {instance}")
    print(f"🔑 API Key: ********{api_key[-4:]}")
    print(f"📱 Grupo: {group_jid}")
    print()
    
    # Criar sender
    sender = EvolutionSender(
        api_url=api_url,
        instance_name=instance,
        api_key=api_key
    )
    
    # Testar envio com método correto
    print("📤 Enviando mensagem com send_text...")
    try:
        result = sender.send_text(
            number=group_jid,
            text="🤖 Teste de conexão bem-sucedido! A Evolution API está funcionando perfeitamente!"
        )
        
        print(f"✅ MENSAGEM ENVIADA!")
        print(f"   Resposta: {result}")
            
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()