"""
app.py
------
Dashboard Geral do sistema Claquete CRM/ERP — página inicial, com os principais
indicadores financeiros e operacionais da produtora.

Para rodar o sistema (a partir da pasta raiz do projeto):

    streamlit run app.py

Veja o README.md para o passo a passo completo de instalação no VSCode.
"""

import pandas as pd
import streamlit as st

import auth
from database import init_db
from db_utils import formatar_data_br, formatar_moeda
from services import eventos as eventos_service
from services import financeiro
from services import socios as socios_service
from ui import charts, theme
from ui.componentes import periodo_iso, seletor_periodo

st.set_page_config(
    page_title="Dashboard Geral · Claquete",
    page_icon="assets/claquete_monograma.png",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()
theme.injetar_css()
auth.exigir_login()
theme.menu_lateral()

# ----------------------------------------------------------------- cabeçalho
theme.cabecalho(
    "Dashboard Geral",
    "Visão consolidada da produtora: caixa, projetos, clientes e sócios.",
)

# ----------------------------------------------------------------- período
data_ini, data_fim = seletor_periodo("dashboard", atalho_padrao="Este ano")
data_ini_iso, data_fim_iso = periodo_iso(data_ini, data_fim)

st.write("")

# ----------------------------------------------------------------- KPIs
caixa_atual = financeiro.saldo_caixa()
totais = financeiro.totais_periodo(data_ini_iso, data_fim_iso)
dividas = socios_service.resumo_dividas()
saldo_devedor_total = round(sum(d["saldo_devedor"] for d in dividas), 2)

eventos_periodo = eventos_service.listar_eventos(data_ini=data_ini_iso, data_fim=data_fim_iso)
receita_contratada = round(sum(e["valor_total"] for e in eventos_periodo), 2)
receita_recebida = round(sum(e["total_recebido"] for e in eventos_periodo), 2)
receita_pendente = round(receita_contratada - receita_recebida, 2)

col1, col2, col3, col4, col5 = st.columns(5)
theme.kpi_card(col1, "Caixa Atual", formatar_moeda(caixa_atual),
               "saldo acumulado total", theme.cor_valor_financeiro(caixa_atual))
theme.kpi_card(col2, "Entradas no Período", formatar_moeda(totais["entradas"]),
               "recebido de clientes e sócios", theme.POSITIVO)
theme.kpi_card(col3, "Saídas no Período", formatar_moeda(totais["saidas"]),
               "custos e investimentos", theme.NEGATIVO)
theme.kpi_card(col4, "A Receber", formatar_moeda(receita_pendente),
               f"de {formatar_moeda(receita_contratada)} contratados", theme.ALERTA)
theme.kpi_card(col5, "Dívida com Sócios", formatar_moeda(saldo_devedor_total),
               "aportes a reembolsar",
               theme.NEGATIVO if saldo_devedor_total > 0 else theme.POSITIVO)

st.write("")

# ----------------------------------------------------------------- gráficos
col_a, col_b = st.columns([3, 2])
with col_a:
    with st.container(border=True):
        evolucao = financeiro.evolucao_mensal(meses=12, data_ini=data_ini_iso,
                                              data_fim=data_fim_iso)
        charts.renderizar(charts.grafico_evolucao_caixa(evolucao))
with col_b:
    with st.container(border=True):
        distrib = financeiro.distribuicao_saidas_por_categoria(data_ini_iso, data_fim_iso)
        charts.renderizar(charts.grafico_distribuicao_categoria(distrib, "Saídas por Categoria"))

col_c, col_d = st.columns(2)
with col_c:
    with st.container(border=True):
        ranking = eventos_service.ranking_clientes_por_receita(6, data_ini_iso, data_fim_iso)
        charts.renderizar(charts.grafico_barra_horizontal(
            [r["nome"] for r in ranking], [r["receita_total"] for r in ranking],
            "Receita Contratada por Cliente",
        ))
with col_d:
    with st.container(border=True):
        funil = eventos_service.funil_status(data_ini_iso, data_fim_iso)
        charts.renderizar(charts.grafico_funil_eventos(funil))

# ----------------------------------------------------------------- tabelas
col_e, col_f = st.columns(2)

with col_e:
    st.markdown("### 🧾 Últimos lançamentos no caixa")
    ultimos = financeiro.listar_fluxo(data_ini=data_ini_iso, data_fim=data_fim_iso)[:8]
    if ultimos:
        df = pd.DataFrame(ultimos)[["data", "tipo", "categoria", "descricao", "valor"]].copy()
        df["data"] = df["data"].apply(formatar_data_br)
        df["valor"] = df["valor"].apply(formatar_moeda)
        df.columns = ["Data", "Tipo", "Categoria", "Descrição", "Valor"]
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info(
            "Nenhum lançamento neste período. Rode `python scripts/seed_demo.py` "
            "para carregar dados de exemplo, ou comece cadastrando um sócio em "
            "**Sócios e Aportes**."
        )

with col_f:
    st.markdown("### 🎬 Projetos do período")
    if eventos_periodo:
        linhas = []
        for e in eventos_periodo[:8]:
            linhas.append({
                "Projeto": e["nome"],
                "Cliente": e["cliente_nome"],
                "Data": formatar_data_br(e["data_evento"]),
                "Valor": formatar_moeda(e["valor_total"]),
                "Status": e["status"],
            })
        st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
    else:
        st.info("Nenhum projeto com data dentro do período selecionado.")
