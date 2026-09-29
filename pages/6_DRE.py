"""
Página: DRE
------------
Demonstrativo de Resultado do Exercício em regime de caixa, por período
selecionável, com gráfico de cascata, evolução mensal, movimentações com
sócios e uma explicação clara de como a margem é calculada.
"""

import streamlit as st

import auth
from database import init_db
from db_utils import formatar_moeda
from services import dre as dre_service
from services import socios as socios_service
from ui import charts, theme
from ui.componentes import periodo_iso, seletor_periodo

st.set_page_config(page_title="DRE · Claquete",
                   page_icon="assets/claquete_monograma.png", layout="wide")
init_db()
theme.injetar_css()
auth.exigir_login()
theme.menu_lateral()
theme.cabecalho("DRE — Demonstrativo de Resultado",
                "Regime de caixa: o que realmente entrou e saiu da empresa no período.")

data_ini, data_fim = seletor_periodo("dre", atalho_padrao="Este ano")
data_ini_iso, data_fim_iso = periodo_iso(data_ini, data_fim)
st.write("")

dre = dre_service.calcular_dre(data_ini_iso, data_fim_iso)
receita_total = dre["receitas"]["total"]
custos_total = dre["custos"]["total"]
resultado = dre["resultado_operacional"]
margem = dre["margem_percentual"]

# ----------------------------------------------------------------- KPIs
c1, c2, c3, c4 = st.columns(4)
theme.kpi_card(c1, "Receita Total", formatar_moeda(receita_total),
               "entradas operacionais", theme.POSITIVO)
theme.kpi_card(c2, "Custos e Despesas", formatar_moeda(custos_total),
               "saídas operacionais", theme.NEGATIVO)
theme.kpi_card(c3, "Resultado Operacional", formatar_moeda(resultado),
               f"margem de {margem}%", theme.cor_valor_financeiro(resultado))
theme.kpi_card(c4, "Saldo de Caixa Final", formatar_moeda(dre["caixa"]["saldo_final"]),
               f"variação de {formatar_moeda(dre['caixa']['variacao'])}",
               theme.cor_valor_financeiro(dre["caixa"]["variacao"]))

st.write("")

# ----------------------------------------------------------------- gráficos
col_r1, col_r2 = st.columns(2)
with col_r1:
    with st.container(border=True):
        charts.renderizar(charts.grafico_resumo_dre(dre))
with col_r2:
    with st.container(border=True):
        charts.renderizar(charts.grafico_detalhe_custos(dre))

# ----------------------------------------------------------------- detalhamento
col_dre, col_socios = st.columns([3, 2])

with col_dre:
    with st.container(border=True):
        st.markdown("### 📑 Demonstrativo detalhado")

        st.markdown("**(+) RECEITAS**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Receita de Projetos: "
                    f"{formatar_moeda(dre['receitas']['receita_projetos'])}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Outras Receitas: "
                    f"{formatar_moeda(dre['receitas']['outras_receitas'])}")
        st.markdown(f"**Total de Receitas: {formatar_moeda(receita_total)}**")

        st.divider()

        st.markdown("**(−) CUSTOS E DESPESAS**")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Custos Fixos: "
                    f"{formatar_moeda(dre['custos']['custos_fixos'])}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Investimentos (Equip./Software): "
                    f"{formatar_moeda(dre['custos']['investimentos'])}")
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;Outras Despesas: "
                    f"{formatar_moeda(dre['custos']['outras_despesas'])}")
        st.markdown(f"**Total de Custos e Despesas: {formatar_moeda(custos_total)}**")

        st.divider()

        cor = theme.cor_valor_financeiro(resultado)
        st.markdown(
            f"### Resultado Operacional: "
            f"<span style='color:{cor}'>{formatar_moeda(resultado)}</span>",
            unsafe_allow_html=True,
        )

with col_socios:
    with st.container(border=True):
        st.markdown("### 🤝 Movimentações com Sócios")
        st.caption("Informativo — é financiamento, não entra no resultado acima.")
        s = dre["socios"]
        st.markdown(f"Aportes em dinheiro: **{formatar_moeda(s['aportes_em_caixa'])}**")
        st.markdown(f"Despesas pagas por sócios: "
                    f"**{formatar_moeda(s['despesas_financiadas_por_socios'])}**")
        st.markdown(f"Reembolsos pagos: **{formatar_moeda(s['reembolsos_pagos'])}**")
        st.divider()
        st.markdown(f"##### Dívida total atual: {formatar_moeda(s['saldo_devedor_total'])}")
        for d in socios_service.resumo_dividas():
            if d["saldo_devedor"] != 0:
                st.markdown(f"- {d['nome']}: {formatar_moeda(d['saldo_devedor'])}")

    with st.container(border=True):
        st.markdown("### 💰 Saldo de Caixa")
        st.markdown(f"Saldo inicial: **{formatar_moeda(dre['caixa']['saldo_inicial'])}**")
        st.markdown(f"Saldo final: **{formatar_moeda(dre['caixa']['saldo_final'])}**")
        st.markdown(f"Variação: **{formatar_moeda(dre['caixa']['variacao'])}**")

st.write("")

# ----------------------------------------------------------------- evolução mensal
with st.container(border=True):
    # Os meses do gráfico saem do PERÍODO escolhido no topo da página, então
    # mudar o período atualiza este gráfico junto com o resto da tela.
    meses_ref = []
    ano, mes = data_ini.year, data_ini.month
    while (ano, mes) <= (data_fim.year, data_fim.month):
        meses_ref.append(f"{ano}-{mes:02d}")
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    # "Todo o período" pode gerar centenas de meses; nesse caso mostramos os
    # 24 meses mais recentes, para o gráfico continuar legível.
    if len(meses_ref) > 24:
        meses_ref = meses_ref[-24:]
        st.caption("Exibindo os 24 meses mais recentes do período selecionado.")

    if meses_ref:
        charts.renderizar(charts.grafico_dre_evolucao(
            dre_service.evolucao_dre_mensal(meses_ref)))
    else:
        st.info("Selecione um período de pelo menos um mês para ver a evolução.")
