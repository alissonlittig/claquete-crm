"""
Página: Investimentos
----------------------
Cadastro de compras de equipamentos e softwares (CAPEX). Cada investimento
pode ter sido pago pelo caixa da empresa ou diretamente por um sócio — nesse
segundo caso, o sistema gera automaticamente um aporte (dívida) para aquele
sócio, sem duplicar o valor no fluxo de caixa.
"""

from datetime import date

import streamlit as st

import auth
from database import init_db
from db_utils import formatar_data_br, formatar_moeda
from services import financeiro
from services import socios as socios_service
from ui import charts, theme
from ui.componentes import input_inteiro, input_moeda, periodo_iso, seletor_periodo

st.set_page_config(page_title="Investimentos · Claquete",
                   page_icon="assets/claquete_monograma.png", layout="wide")
init_db()
theme.injetar_css()
auth.exigir_login()
theme.menu_lateral()
theme.cabecalho("Investimentos",
                "Equipamentos e softwares adquiridos pela produtora.")

CATEGORIAS_INVESTIMENTO = ["Equipamento", "Software", "Outro"]

data_ini, data_fim = seletor_periodo("investimentos", atalho_padrao="Este ano")
data_ini_iso, data_fim_iso = periodo_iso(data_ini, data_fim)
st.write("")

aba_visao, aba_cadastro = st.tabs(["📊 Visão Geral", "➕ Novo Investimento"])

# =====================================================================
# ABA: VISÃO GERAL
# =====================================================================
with aba_visao:
    investimentos = financeiro.listar_investimentos(
        data_ini=data_ini_iso, data_fim=data_fim_iso)
    total_geral = sum(i["valor"] for i in investimentos)
    total_equip = sum(i["valor"] for i in investimentos if i["categoria"] == "Equipamento")
    total_soft = sum(i["valor"] for i in investimentos if i["categoria"] == "Software")
    depreciacao = financeiro.depreciacao_mensal_total()

    c1, c2, c3, c4 = st.columns(4)
    theme.kpi_card(c1, "Investido no Período", formatar_moeda(total_geral),
                   f"{len(investimentos)} item(ns)")
    theme.kpi_card(c2, "Em Equipamentos", formatar_moeda(total_equip))
    theme.kpi_card(c3, "Em Softwares", formatar_moeda(total_soft))
    theme.kpi_card(c4, "Depreciação Mensal", formatar_moeda(depreciacao),
                   "linear, todo o acervo")

    st.write("")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        with st.container(border=True):
            por_categoria = {}
            for i in investimentos:
                por_categoria[i["categoria"]] = por_categoria.get(i["categoria"], 0) + i["valor"]
            dados = [{"categoria": k, "total": v} for k, v in por_categoria.items()]
            charts.renderizar(charts.grafico_distribuicao_categoria(
                dados, "Investimentos por Categoria"))
    with col_g2:
        with st.container(border=True):
            por_forma = {}
            for i in investimentos:
                chave = ("Caixa da Empresa" if i["forma_pagamento"] == "Caixa da Empresa"
                         else f"Sócio: {i['socio_nome']}")
                por_forma[chave] = por_forma.get(chave, 0) + i["valor"]
            charts.renderizar(charts.grafico_pizza_simples(
                list(por_forma.keys()), list(por_forma.values()),
                "Quem Financiou os Investimentos",
            ))

    st.markdown("### 📋 Histórico de investimentos")
    if not investimentos:
        st.info("Nenhum investimento cadastrado neste período.")
    for i in investimentos:
        with st.container(border=True):
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 0.9])
            col1.markdown(
                f"**{theme.esc(i['nome'])}**  \n"
                f"<span style='font-size:0.82rem;color:{theme.TEXTO_SECUNDARIO}'>"
                f"{theme.esc(i['categoria'])}"
                f"{' · ' + i['fornecedor'] if i['fornecedor'] else ''}</span>",
                unsafe_allow_html=True,
            )
            col2.markdown(f"### {formatar_moeda(i['valor'])}")
            col3.markdown(f"📅 {formatar_data_br(i['data_compra'])}")
            financiador = ("💵 Caixa da Empresa"
                           if i["forma_pagamento"] == "Caixa da Empresa"
                           else f"🤝 {theme.esc(i['socio_nome'])}")
            col4.markdown(
                f"<span style='font-size:0.88rem'>{theme.esc(financiador)}</span>"
                + (f"<br><span style='font-size:0.78rem;color:{theme.TEXTO_SECUNDARIO}'>"
                   f"vida útil {i['vida_util_meses']} meses</span>"
                   if i["vida_util_meses"] else ""),
                unsafe_allow_html=True,
            )
            if col5.button("🗑️", key=f"del_inv_{i['id']}", help="Excluir investimento"):
                financeiro.excluir_investimento(i["id"])
                st.rerun()

# =====================================================================
# ABA: CADASTRO
# =====================================================================
with aba_cadastro:
    socios_ativos = socios_service.listar_socios(apenas_ativos=True)

    forma_pagamento_inv = st.radio(
        "Forma de pagamento", ["Caixa da Empresa", "Sócio"], horizontal=True,
        help="'Sócio' significa que o sócio pagou do próprio bolso — isso gera "
             "automaticamente um aporte (dívida da empresa com ele), sem duplicar no caixa.",
        key="forma_pagamento_inv",
    )
    socio_pagador = None
    if forma_pagamento_inv == "Sócio":
        if socios_ativos:
            socio_sel = st.selectbox("Qual sócio pagou?", socios_ativos,
                                      format_func=lambda s: s["nome"])
            socio_pagador = socio_sel["id"]
        else:
            st.warning("Cadastre um sócio ativo antes de registrar um investimento "
                       "pago por sócio.")

    with st.form("form_novo_investimento", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        nome_inv = c1.text_input("Nome do item*", placeholder="Ex: Câmera mirrorless + lente")
        categoria_inv = c2.selectbox("Categoria", CATEGORIAS_INVESTIMENTO)
        valor_inv = input_moeda(c3, "Valor (R$)", "valor_novo_inv")

        c4, c5, c6 = st.columns(3)
        data_compra_inv = c4.date_input("Data da compra", value=date.today(),
                                         format="DD/MM/YYYY")
        fornecedor_inv = c5.text_input("Fornecedor")
        vida_util_inv = input_inteiro(
            c6, "Vida útil (meses)", "vida_util_inv", valor_inicial=36, minimo=0,
            ajuda="Usado apenas como referência de depreciação linear. Deixe vazio "
                  "se não quiser calcular.",
        )
        obs_inv = st.text_area("Observação", height=68)

        if st.form_submit_button("Registrar investimento", width="stretch"):
            if not nome_inv.strip() or valor_inv <= 0:
                st.error("Informe o nome do item e um valor maior que zero.")
            elif forma_pagamento_inv == "Sócio" and not socio_pagador:
                st.error("Selecione qual sócio realizou o pagamento.")
            else:
                financeiro.criar_investimento(
                    nome_inv, categoria_inv, valor_inv, data_compra_inv,
                    fornecedor_inv, vida_util_inv or None,
                    forma_pagamento_inv, socio_pagador, obs_inv,
                )
                st.success(f"Investimento **{nome_inv}** registrado com sucesso!")
                st.rerun()
