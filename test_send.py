# test_send.py
from src.core.config_loader import Config
from src.evolution_sender import EvolutionSender

config = Config()
sender = EvolutionSender(
    api_url=config.get("evolution.api_url"),
    instance_name=config.get("evolution.instance_name"),
    api_key=config.get("evolution.api_key")
)

# Envia mensagem de teste
success = sender.send_text(
    number=config.get("whatsapp.group_jid"),
    text="🤖 *Teste de conexão*\nSe recebeu esta mensagem, a Evolution API está funcionando! ✅"
)

print("✅ Mensagem enviada!" if success else "❌ Falha no envio")
