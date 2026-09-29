"""
services/dre.py
----------------
Cálculo do DRE (Demonstrativo de Resultado do Exercício) em regime de caixa,
adaptado à realidade de uma produtora audiovisual pequena com sócios que
atuam também como prestadores/fornecedores de capital.

Estrutura do relatório (ver função `calcular_dre`):

    1. RECEITA OPERACIONAL
       - Receita de Projetos (comissão da empresa recebida dos clientes)
       - Outras Receitas
    2. CUSTOS E DESPESAS
       - Custos Fixos (pagos no período)
       - Investimentos em Equipamentos/Softwares (comprados no período,
         independente de terem sido pagos pelo caixa da empresa ou por um sócio)
       - Outras Despesas
    3. RESULTADO OPERACIONAL = Receitas - Custos e Despesas
    4. MOVIMENTAÇÕES COM SÓCIOS (informativo, não entra no resultado)
       - Aportes em dinheiro recebidos no período
       - Despesas financiadas diretamente por sócios no período
       - Reembolsos pagos a sócios no período
       - Saldo devedor acumulado atual com cada sócio
    5. SALDO DE CAIXA (inicial, do período e final)
"""

from db_utils import consultar, escalar
from services import financeiro, socios as socios_service


def calcular_dre(data_ini: str, data_fim: str) -> dict:
    # 1. Receitas -----------------------------------------------------------
    receita_projetos = escalar(
        "SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Entrada' AND categoria='Receita de Projeto' "
        "AND data BETWEEN ? AND ?",
        (data_ini, data_fim),
    )
    outras_receitas = escalar(
        "SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Entrada' "
        "AND categoria NOT IN ('Receita de Projeto', 'Aporte de Sócio') "
        "AND data BETWEEN ? AND ?",
        (data_ini, data_fim),
    )
    total_receitas = round(receita_projetos + outras_receitas, 2)

    # 2. Custos e despesas ----------------------------------------------------
    custos_fixos = escalar(
        "SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Saída' AND categoria='Custo Fixo' "
        "AND data BETWEEN ? AND ?",
        (data_ini, data_fim),
    )
    investimentos_periodo = financeiro.total_investido(data_ini=data_ini, data_fim=data_fim)
    outras_despesas = escalar(
        "SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Saída' "
        "AND categoria NOT IN ('Custo Fixo', 'Investimento', 'Reembolso a Sócio') "
        "AND data BETWEEN ? AND ?",
        (data_ini, data_fim),
    )
    total_custos = round(custos_fixos + investimentos_periodo + outras_despesas, 2)

    # 3. Resultado ------------------------------------------------------------
    resultado_operacional = round(total_receitas - total_custos, 2)

    # 4. Movimentações com sócios (informativo) --------------------------------
    aportes_em_caixa = escalar(
        "SELECT SUM(valor) FROM aportes WHERE entrou_no_caixa=1 AND data BETWEEN ? AND ?",
        (data_ini, data_fim),
    )
    despesas_financiadas_por_socios = escalar(
        "SELECT SUM(valor) FROM aportes WHERE entrou_no_caixa=0 AND data BETWEEN ? AND ?",
        (data_ini, data_fim),
    )
    reembolsos_pagos = escalar(
        "SELECT SUM(valor) FROM reembolsos_socios WHERE data BETWEEN ? AND ?",
        (data_ini, data_fim),
    )
    saldo_devedor_total = round(sum(s["saldo_devedor"] for s in socios_service.resumo_dividas()), 2)

    # 5. Saldo de caixa ---------------------------------------------------------
    saldo_inicial = financeiro.saldo_caixa(ate_data=_dia_anterior(data_ini))
    saldo_final = financeiro.saldo_caixa(ate_data=data_fim)

    return {
        "periodo": {"inicio": data_ini, "fim": data_fim},
        "receitas": {
            "receita_projetos": round(receita_projetos, 2),
            "outras_receitas": round(outras_receitas, 2),
            "total": total_receitas,
        },
        "custos": {
            "custos_fixos": round(custos_fixos, 2),
            "investimentos": round(investimentos_periodo, 2),
            "outras_despesas": round(outras_despesas, 2),
            "total": total_custos,
        },
        "resultado_operacional": resultado_operacional,
        "margem_percentual": round((resultado_operacional / total_receitas * 100), 1) if total_receitas else 0.0,
        "socios": {
            "aportes_em_caixa": round(aportes_em_caixa, 2),
            "despesas_financiadas_por_socios": round(despesas_financiadas_por_socios, 2),
            "reembolsos_pagos": round(reembolsos_pagos, 2),
            "saldo_devedor_total": saldo_devedor_total,
        },
        "caixa": {
            "saldo_inicial": saldo_inicial,
            "saldo_final": saldo_final,
            "variacao": round(saldo_final - saldo_inicial, 2),
        },
    }


def evolucao_dre_mensal(meses: list) -> list:
    """
    Recebe uma lista de referências 'YYYY-MM' e devolve o resumo de cada mês.

    DESEMPENHO
        A versão anterior chamava `calcular_dre()` uma vez por mês — e como
        cada chamada faz cerca de dez consultas, um gráfico de 24 meses
        disparava mais de 240 consultas ao banco. Com o banco na nuvem, isso
        deixava a página do DRE lenta demais.

        Agora tudo é resolvido em DUAS consultas agrupadas por mês,
        independentemente de quantos meses forem pedidos.
    """
    if not meses:
        return []

    mes_ini, mes_fim = min(meses), max(meses)
    data_ini = f"{mes_ini}-01"
    ano_fim, num_fim = (int(p) for p in mes_fim.split("-"))
    data_fim = f"{mes_fim}-{_ultimo_dia_mes(ano_fim, num_fim):02d}"

    # 1) Entradas e saídas do caixa, agrupadas por mês
    linhas_caixa = consultar(
        """
        SELECT strftime('%Y-%m', data) AS mes,
               SUM(CASE WHEN tipo = 'Entrada' AND categoria <> 'Aporte de Sócio'
                        THEN valor ELSE 0 END) AS receitas,
               SUM(CASE WHEN tipo = 'Saída' AND categoria <> 'Reembolso a Sócio'
                             AND categoria <> 'Investimento'
                        THEN valor ELSE 0 END) AS custos
        FROM fluxo_caixa
        WHERE data BETWEEN ? AND ?
        GROUP BY mes
        """,
        (data_ini, data_fim),
    )

    # 2) Investimentos do período, agrupados por mês (entram como custo do
    #    mês da compra, mesmo quando pagos diretamente por um sócio)
    linhas_inv = consultar(
        """
        SELECT strftime('%Y-%m', data_compra) AS mes, SUM(valor) AS total
        FROM investimentos
        WHERE data_compra BETWEEN ? AND ?
        GROUP BY mes
        """,
        (data_ini, data_fim),
    )

    mapa_caixa = {l["mes"]: l for l in linhas_caixa}
    mapa_inv = {l["mes"]: l["total"] for l in linhas_inv}

    resultado = []
    for ref in meses:
        caixa = mapa_caixa.get(ref, {})
        receitas = round(caixa.get("receitas", 0) or 0, 2)
        custos = round((caixa.get("custos", 0) or 0) + (mapa_inv.get(ref, 0) or 0), 2)
        resultado.append({
            "mes": ref,
            "receitas": receitas,
            "custos": custos,
            "resultado": round(receitas - custos, 2),
        })
    return resultado


def _ultimo_dia_mes(ano: int, mes: int) -> int:
    import calendar
    return calendar.monthrange(ano, mes)[1]


def _dia_anterior(data_iso: str) -> str:
    from datetime import date, timedelta
    d = date.fromisoformat(data_iso)
    return (d - timedelta(days=1)).isoformat()
