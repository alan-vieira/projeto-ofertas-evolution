# verificar_metodos.py
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.evolution_sender import EvolutionSender

# Criar instância
sender = EvolutionSender(
    api_url=os.getenv("EVOLUTION_API_URL"),
    instance_name=os.getenv("EVOLUTION_INSTANCE_NAME"),
    api_key=os.getenv("EVOLUTION_API_KEY")
)

# Listar todos os métodos públicos
print("=" * 70)
print("🔍 MÉTODOS DISPONÍVEIS EM EvolutionSender")
print("=" * 70)

metodos = [m for m in dir(sender) if not m.startswith('_') and callable(getattr(sender, m))]

for metodo in metodos:
    print(f"  - {metodo}")

print("\n" + "=" * 70)