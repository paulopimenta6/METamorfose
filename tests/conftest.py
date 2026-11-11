import sys
from pathlib import Path

# Permite importar phase0_harness diretamente nos testes.
sys.path.insert(0, str(Path(__file__).resolve().parent))
