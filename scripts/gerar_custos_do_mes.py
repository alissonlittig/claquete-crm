"""
scripts/gerar_custos_do_mes.py
--------------------------------
Script standalone que gera automaticamente as contas do mês corrente para
todos os custos fixos ativos — sem precisar abrir o Streamlit. Feito para
ser agendado (rodar sozinho, uma vez por mês).

Rodar manualmente:
    python scripts/gerar_custos_do_mes.py

Agendar no Linux/Mac (roda todo dia 1 às 06:00 — editar com `crontab -e`):
    0 6 1 * * cd /caminho/completo/para/claquete-crm && ./venv/bin/python scripts/gerar_custos_do_mes.py >> logs.txt 2>&1

Agendar no Windows (Agendador de Tarefas > Criar Tarefa Básica):
    Programa/script:  C:\\caminho\\completo\\para\\claquete-crm\\venv\\Scripts\\python.exe
    Argumentos:        scripts\\gerar_custos_do_mes.py
    Iniciar em:        C:\\caminho\\completo\\para\\claquete-crm
    Gatilho:           Mensalmente, todo dia 1
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db
from services import financeiro


def main() -> None:
    init_db()
    referencia = date.today().strftime("%Y-%m")
    criados = financeiro.gerar_lancamentos_do_mes(referencia)
    print(f"[{date.today().isoformat()}] {criados} nova(s) conta(s) de custo fixo gerada(s) para {referencia}.")


if __name__ == "__main__":
    main()
