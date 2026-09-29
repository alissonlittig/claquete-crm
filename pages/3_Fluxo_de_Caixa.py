"""
Página: Fluxo de Caixa
-----------------------
Livro-razão único de todas as entradas e saídas reais de dinheiro da empresa.
A maioria dos lançamentos é criada automaticamente por outras telas (aportes,
recebimentos, custos fixos pagos, investimentos); aqui também é possível
registrar movimentações avulsas.
"""

from datetime import date

import pandas as pd
import streamlit as st

import auth
from database import init_db
from db_utils import formatar_data_br, formatar_moeda
from services import financeiro
from ui import charts, theme
from ui.componentes import input_moeda, periodo_iso, seletor_periodo

st.set_page_config(page_title="Fluxo de Caixa · Claquete",
                   page_icon="assets/claquete_monograma.png", layout="wide")
init_db()
theme.injetar_css()
auth.exigir_login()
theme.menu_lateral()
theme.cabecalho("Fluxo de Caixa",
                "Todas as entradas e saídas reais da empresa, em um único lugar.")

CATEGORIAS_MANUAIS = [
    "Receita de Projeto", "Marketing", "Impostos e Taxas", "Manutenção",
    "Alimentação/Deslocamento", "Outras Receitas", "Outras Despesas",
]

data_ini, data_fim = seletor_periodo("fluxo", atalho_padrao="Este ano")
data_ini_iso, data_fim_iso = periodo_iso(data_ini, data_fim)
st.write("")

# ----------------------------------------------------------------- KPIs
totais = financeiro.totais_periodo(data_ini_iso, data_fim_iso)
saldo_atual = financeiro.saldo_caixa()

c1, c2, c3, c4 = st.columns(4)
theme.kpi_card(c1, "Saldo Atual (total)", formatar_moeda(saldo_atual),
               "considerando todo o histórico",
               theme.cor_valor_financeiro(saldo_atual))
theme.kpi_card(c2, "Entradas no Período", formatar_moeda(totais["entradas"]),
               "", theme.POSITIVO)
theme.kpi_card(c3, "Saídas no Período", formatar_moeda(totais["saidas"]),
               "", theme.NEGATIVO)
theme.kpi_card(c4, "Resultado do Período", formatar_moeda(totais["saldo"]),
               "entradas menos saídas",
               theme.cor_valor_financeiro(totais["saldo"]))

st.write("")

# ----------------------------------------------------------------- gráficos
col_g1, col_g2 = st.columns([3, 2])
with col_g1:
    with st.container(border=True):
        charts.renderizar(charts.grafico_evolucao_caixa(
            financeiro.evolucao_mensal(meses=12, data_ini=data_ini_iso,
                                       data_fim=data_fim_iso)))
with col_g2:
    with st.container(border=True):
        distrib = financeiro.distribuicao_saidas_por_categoria(data_ini_iso, data_fim_iso)
        charts.renderizar(charts.grafico_distribuicao_categoria(
            distrib, "Saídas por Categoria"))

st.divider()

# ----------------------------------------------------------------- lançamento manual
with st.expander("➕ Novo lançamento manual"):
    with st.form("form_lancamento_manual", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        data_lanc = c1.date_input("Data", value=date.today(),
                                   format="DD/MM/YYYY", key="data_lanc")
        tipo_lanc = c2.selectbox("Tipo", ["Entrada", "Saída"])
        valor_lanc = input_moeda(c3, "Valor (R$)", "valor_lanc_manual")
        categoria_lanc = st.selectbox("Categoria", CATEGORIAS_MANUAIS)
        descricao_lanc = st.text_input("Descrição*")
        if st.form_submit_button("Registrar lançamento", width="stretch"):
            if descricao_lanc.strip() and valor_lanc > 0:
                financeiro.lancamento_manual(data_lanc, tipo_lanc, categoria_lanc,
                                              descricao_lanc, valor_lanc)
                st.success("Lançamento registrado!")
                st.rerun()
            else:
                st.error("Informe a descrição e um valor maior que zero.")

# ----------------------------------------------------------------- listagem
st.markdown("### 🧾 Lançamentos do período")
fc1, fc2 = st.columns(2)
filtro_tipo = fc1.selectbox("Filtrar tipo", ["Todos", "Entrada", "Saída"])
categorias_disp = ["Todas"] + financeiro.categorias_existentes()
filtro_categoria = fc2.selectbox("Filtrar categoria", categorias_disp)

lancamentos = financeiro.listar_fluxo(
    data_ini=data_ini_iso, data_fim=data_fim_iso,
    tipo=None if filtro_tipo == "Todos" else filtro_tipo,
    categoria=None if filtro_categoria == "Todas" else filtro_categoria,
)

if not lancamentos:
    st.info("Nenhum lançamento encontrado para o período e filtros selecionados.")
else:
    df = pd.DataFrame(lancamentos)
    df_exibir = df[["data", "tipo", "categoria", "descricao", "valor", "origem_tabela"]].copy()
    df_exibir["data"] = df_exibir["data"].apply(formatar_data_br)
    df_exibir["valor"] = df_exibir["valor"].apply(formatar_moeda)
    df_exibir["origem_tabela"] = df_exibir["origem_tabela"].replace({
        "manual": "Manual",
        "aportes": "Aporte de sócio",
        "recebimentos": "Recebimento",
        "custos_fixos_pagamentos": "Custo fixo",
        "investimentos": "Investimento",
        "reembolsos_socios": "Reembolso",
    })
    df_exibir.columns = ["Data", "Tipo", "Categoria", "Descrição", "Valor", "Origem"]
    st.dataframe(df_exibir, width="stretch", hide_index=True, height=420)

    st.caption(
        "🔒 Lançamentos com origem diferente de *Manual* foram criados automaticamente "
        "por outra tela. Para removê-los, exclua o registro de origem na tela "
        "correspondente — assim o sistema se mantém consistente."
    )

    with st.expander("🗑️ Excluir um lançamento manual"):
        manuais = [l for l in lancamentos if l["origem_tabela"] == "manual"]
        if manuais:
            opcoes = {
                f"{formatar_data_br(l['data'])} · {l['descricao']} · "
                f"{formatar_moeda(l['valor'])}": l["id"]
                for l in manuais
            }
            escolha = st.selectbox("Selecione o lançamento", list(opcoes.keys()))
            if st.button("Confirmar exclusão"):
                financeiro.excluir_lancamento(opcoes[escolha])
                st.success("Lançamento excluído.")
                st.rerun()
        else:
            st.caption("Não há lançamentos manuais no período filtrado.")
