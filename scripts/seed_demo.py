"""
scripts/seed_demo.py
---------------------
Volta o banco da demonstração ao estado inicial, com os dados fictícios de
services/demo.py.

Como rodar (a partir da pasta raiz do projeto):

    python scripts/seed_demo.py

ATENÇÃO: apaga todos os dados atuais do banco antes de inserir os de exemplo.
Não é preciso rodar este script para usar a demo: quando o banco abre vazio,
o próprio sistema carrega os dados sozinho.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import descricao_banco, init_db
from services import demo


if __name__ == "__main__":
    init_db()
    demo.seed()
    print("Banco de dados de demonstração recriado com sucesso:")
    print(f"  {descricao_banco()}")
