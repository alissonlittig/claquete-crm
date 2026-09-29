"""
Página: Custos Fixos
---------------------
Cadastro de despesas recorrentes (assinaturas, serviços contratados etc.),
geração automática das contas de cada mês e controle de pagamento — incluindo
a possibilidade de editar uma conta ou desmarcá-la como paga.
"""

from datetime import date

import pandas as pd
import streamlit as st

import auth
from database import init_db
from db_utils import formatar_data_br, formatar_mes_br, formatar_moeda
from services import financeiro
from ui import charts, theme
from ui.componentes import input_inteiro, input_moeda, periodo_iso, seletor_periodo

st.set_page_config(page_title="Custos Fixos · Claquete",
                   page_icon="assets/claquete_monograma.png", layout="wide")
init_db()
theme.injetar_css()
auth.exigir_login()
theme.menu_lateral()
theme.cabecalho("Custos Fixos",
                "Despesas recorrentes da produtora e controle mensal de pagamento.")

# Sugestões que aparecem na lista. A categoria é um CAMPO LIVRE: você pode
# escolher uma destas ou digitar uma nova (ex.: "Folha Salarial").
CATEGORIAS_SUGERIDAS = [
    "Folha Salarial", "Assinatura/Software", "Serviço Contratado",
    "Contabilidade", "Impostos", "Outro",
]


NOVA_CATEGORIA = "➕ Digitar nova categoria"


def campo_categoria(container, chave: str, valor_atual: str = ""):
    """
    Campo de categoria com sugestões + digitação livre.

    Mostra uma lista com as categorias já usadas no sistema mais as sugeridas,
    e a opção "➕ Digitar nova categoria", que libera um campo de texto.
    """
    ja_usadas = financeiro.categorias_custos_existentes()
    opcoes = []
    for c in CATEGORIAS_SUGERIDAS + ja_usadas:
        if c and c not in opcoes:
            opcoes.append(c)
    if valor_atual and valor_atual not in opcoes:
        opcoes.insert(0, valor_atual)
    opcoes.append(NOVA_CATEGORIA)

    indice = opcoes.index(valor_atual) if valor_atual in opcoes else 0
    escolha = container.selectbox("Categoria", opcoes, index=indice,
                                   key=f"cat_sel_{chave}")
    if escolha == NOVA_CATEGORIA:
        digitada = container.text_input("Nome da nova categoria",
                                         key=f"cat_txt_{chave}",
                                         placeholder="Ex: Folha Salarial")
        return digitada.strip()
    return escolha

aba_visao, aba_cadastro, aba_pagamentos = st.tabs(
    ["📊 Visão Geral", "🏷️ Custos Cadastrados", "📅 Pagamentos Mensais"]
)

# =====================================================================
# ABA: VISÃO GERAL
# =====================================================================
with aba_visao:
    total_mensal = financeiro.total_custos_fixos_mensais()
    pendentes = financeiro.listar_pagamentos_custos_fixos(apenas_pendentes=True)
    total_pendente = sum(p["valor"] for p in pendentes)
    ativos = financeiro.listar_custos_fixos(apenas_ativos=True)

    c1, c2, c3 = st.columns(3)
    theme.kpi_card(c1, "Compromisso Mensal", formatar_moeda(total_mensal),
                   "soma dos custos ativos")
    theme.kpi_card(c2, "Contas Pendentes", str(len(pendentes)),
                   formatar_moeda(total_pendente),
                   theme.ALERTA if pendentes else theme.POSITIVO)
    theme.kpi_card(c3, "Custos Ativos", str(len(ativos)),
                   f"custo médio {formatar_moeda(total_mensal / len(ativos))}"
                   if ativos else "")

    st.write("")
    col_a, col_b = st.columns(2)
    with col_a:
        with st.container(border=True):
            por_categoria = {}
            for c in ativos:
                por_categoria[c["categoria"]] = por_categoria.get(c["categoria"], 0) + c["valor"]
            dados_pizza = [{"categoria": k, "total": v} for k, v in por_categoria.items()]
            charts.renderizar(charts.grafico_distribuicao_categoria(
                dados_pizza, "Custos Fixos por Categoria"))
    with col_b:
        with st.container(border=True):
            charts.renderizar(charts.grafico_barra_horizontal(
                [c["nome"] for c in ativos], [c["valor"] for c in ativos],
                "Valor Mensal por Custo",
            ))

# =====================================================================
# ABA: CADASTRO
# =====================================================================
with aba_cadastro:
    with st.expander("➕ Cadastrar novo custo fixo", expanded=False):
        with st.form("form_novo_custo", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            nome_custo = c1.text_input("Nome*", placeholder="Ex: Adobe Creative Cloud")
            categoria_custo = campo_categoria(c2, "novo")
            valor_custo = input_moeda(c3, "Valor mensal (R$)", "valor_novo_custo")
            c4, c5 = st.columns(2)
            dia_venc = input_inteiro(c4, "Dia de vencimento", "dia_venc_novo",
                                      valor_inicial=10, minimo=1, maximo=28)
            data_inicio_custo = c5.date_input("Ativo a partir de", value=date.today(),
                                               format="DD/MM/YYYY")
            obs_custo = st.text_area("Observação", height=68)
            if st.form_submit_button("Cadastrar custo fixo", width="stretch"):
                if nome_custo.strip() and valor_custo > 0:
                    financeiro.criar_custo_fixo(
                        nome_custo, categoria_custo, valor_custo,
                        dia_venc or 10, data_inicio_custo, obs_custo)
                    st.success(f"Custo fixo **{nome_custo}** cadastrado!")
                    st.rerun()
                else:
                    st.error("Informe o nome e um valor maior que zero.")

    st.markdown("### Custos fixos cadastrados")
    for c in financeiro.listar_custos_fixos():
        chave_ed = f"editando_custo_{c['id']}"
        with st.container(border=True):
            if not st.session_state.get(chave_ed, False):
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1.2, 1.2])
                col1.markdown(
                    f"**{theme.esc(c['nome'])}**  \n"
                    f"<span style='font-size:0.82rem;color:{theme.TEXTO_SECUNDARIO}'>"
                    f"{theme.esc(c['categoria'])}</span>",
                    unsafe_allow_html=True,
                )
                col2.markdown(f"### {formatar_moeda(c['valor'])}")
                col3.markdown(f"Vence dia **{c['dia_vencimento']}**")
                if col4.button("✏️ Editar", key=f"btn_ed_custo_{c['id']}",
                               width="stretch"):
                    st.session_state[chave_ed] = True
                    st.rerun()
                ativo_novo = col5.toggle("Ativo", value=bool(c["ativo"]),
                                          key=f"ativo_custo_{c['id']}")
                if ativo_novo != bool(c["ativo"]):
                    financeiro.alternar_ativo_custo_fixo(c["id"], ativo_novo)
                    st.rerun()
            else:
                st.markdown(f"#### ✏️ Editando: {c['nome']}")
                with st.form(f"form_edit_custo_{c['id']}"):
                    e1, e2, e3, e4 = st.columns(4)
                    ed_nome = e1.text_input("Nome*", value=c["nome"], key=f"cn_{c['id']}")
                    ed_cat = campo_categoria(e2, f"ed_{c['id']}", c["categoria"])
                    ed_valor = input_moeda(e3, "Valor mensal (R$)", f"cv_{c['id']}",
                                            valor_inicial=float(c["valor"]))
                    ed_dia = input_inteiro(e4, "Dia vencimento", f"cd_{c['id']}",
                                            valor_inicial=int(c["dia_vencimento"] or 10),
                                            minimo=1, maximo=28)
                    ed_obs = st.text_area("Observação", value=c["observacao"] or "",
                                           height=68, key=f"cb_{c['id']}")
                    contas = financeiro.contar_pagamentos_do_custo(c["id"])
                    if contas["total"]:
                        st.caption(
                            f"Este custo tem {contas['total']} conta(s) mensal(is) "
                            f"gerada(s), sendo {contas['pagas']} já paga(s). "
                            "Excluir o custo remove todas elas — e estorna do fluxo "
                            "de caixa as que estavam pagas."
                        )
                    confirmar_exclusao = st.checkbox(
                        "Confirmo que quero excluir este custo fixo",
                        key=f"conf_del_{c['id']}",
                    )

                    b1, b2, b3 = st.columns(3)
                    salvar = b1.form_submit_button("💾 Salvar alterações",
                                                    width="stretch")
                    excluir = b2.form_submit_button("🗑️ Excluir custo",
                                                     width="stretch")
                    cancelar = b3.form_submit_button("Cancelar", width="stretch")

                    if salvar:
                        if ed_nome.strip() and ed_valor > 0:
                            financeiro.atualizar_custo_fixo(
                                c["id"], ed_nome, ed_cat, ed_valor, ed_dia or 10, ed_obs)
                            st.session_state[chave_ed] = False
                            st.success("Custo fixo atualizado!")
                            st.rerun()
                        else:
                            st.error("Informe o nome e um valor maior que zero.")
                    if excluir:
                        if not confirmar_exclusao:
                            st.error(
                                "Marque a caixa de confirmação antes de excluir."
                            )
                        else:
                            resumo = financeiro.excluir_custo_fixo(c["id"])
                            st.session_state[chave_ed] = False
                            st.success(
                                f"Custo fixo excluído. {resumo['contas_removidas']} "
                                f"conta(s) removida(s)."
                            )
                            st.rerun()
                    if cancelar:
                        st.session_state[chave_ed] = False
                        st.rerun()

# =====================================================================
# ABA: PAGAMENTOS MENSAIS
# =====================================================================
with aba_pagamentos:
    hoje = date.today()
    # A lista de anos começa em 2025 e vai sempre até o ano seguinte ao atual,
    # então ela se expande sozinha com o passar do tempo (em 2029 haverá 2029).
    anos_disponiveis = list(range(2025, hoje.year + 2))
    indice_ano_atual = (anos_disponiveis.index(hoje.year)
                        if hoje.year in anos_disponiveis else 0)

    c1, c2, c3 = st.columns([1, 1, 2])
    ano_ref = c1.selectbox("Ano", anos_disponiveis, index=indice_ano_atual)
    mes_ref_num = c2.selectbox(
        "Mês", list(range(1, 13)), index=hoje.month - 1,
        format_func=lambda m: formatar_mes_br(f"2000-{m:02d}").split("/")[0],
    )
    mes_ref = f"{ano_ref}-{mes_ref_num:02d}"

    # Espaçador invisível: alinha o botão com a base dos dois seletores acima,
    # que são mais altos por causa do rótulo ("Ano" / "Mês").
    c3.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
    if c3.button(f"🔄 Gerar contas de {formatar_mes_br(mes_ref)}",
                 width="stretch"):
        criados = financeiro.gerar_lancamentos_do_mes(mes_ref)
        if criados:
            st.success(f"{criados} nova(s) conta(s) gerada(s).")
        else:
            st.info("Todas as contas deste mês já haviam sido geradas.")
        st.rerun()

    st.divider()
    st.markdown(f"### Contas de {formatar_mes_br(mes_ref)}")

    pagamentos = financeiro.listar_pagamentos_custos_fixos(referencia_mes=mes_ref)
    if not pagamentos:
        st.info("Nenhuma conta gerada para este mês ainda. Use o botão acima.")
    else:
        total_mes = sum(p["valor"] for p in pagamentos)
        pago_mes = sum(p["valor"] for p in pagamentos if p["pago"])
        k1, k2, k3 = st.columns(3)
        theme.kpi_card(k1, "Total do Mês", formatar_moeda(total_mes))
        theme.kpi_card(k2, "Já Pago", formatar_moeda(pago_mes), "", theme.POSITIVO)
        theme.kpi_card(k3, "Em Aberto", formatar_moeda(total_mes - pago_mes), "",
                       theme.ALERTA if total_mes - pago_mes > 0 else theme.POSITIVO)
        st.write("")

    for p in pagamentos:
        chave_ed_pag = f"editando_pag_{p['id']}"
        with st.container(border=True):
            if not st.session_state.get(chave_ed_pag, False):
                col1, col2, col3, col4, col5 = st.columns([3, 1.6, 2, 1.9, 1.1])
                col1.markdown(
                    f"**{theme.esc(p['custo_nome'])}**  \n"
                    f"<span style='font-size:0.82rem;color:{theme.TEXTO_SECUNDARIO}'>"
                    f"{theme.esc(p['custo_categoria'])}</span>",
                    unsafe_allow_html=True,
                )
                col2.markdown(f"### {formatar_moeda(p['valor'])}")
                col3.markdown(
                    f"<span style='font-size:0.86rem'>Vencimento<br>"
                    f"<b>{formatar_data_br(p['data_vencimento'])}</b></span>",
                    unsafe_allow_html=True,
                )
                if p["pago"]:
                    col4.markdown(
                        f"<span style='color:{theme.POSITIVO};font-weight:700'>✅ Pago</span><br>"
                        f"<span style='font-size:0.8rem'>em "
                        f"{formatar_data_br(p['data_pagamento'])}</span>",
                        unsafe_allow_html=True,
                    )
                    if col5.button("↩️ Desfazer", key=f"desmarcar_{p['id']}",
                                    help="Desmarcar como pago e remover do fluxo de caixa",
                                    width="stretch"):
                        financeiro.desmarcar_pagamento(p["id"])
                        st.success("Pagamento desfeito.")
                        st.rerun()
                else:
                    if col4.button("💸 Marcar como pago", key=f"pagar_{p['id']}",
                                    width="stretch"):
                        financeiro.marcar_pagamento(p["id"])
                        st.success("Pagamento registrado no fluxo de caixa!")
                        st.rerun()
                    if col5.button("✏️", key=f"btn_ed_pag_{p['id']}",
                                    help="Editar esta conta", width="stretch"):
                        st.session_state[chave_ed_pag] = True
                        st.rerun()
            else:
                st.markdown(f"#### ✏️ Editando conta: {p['custo_nome']}")
                with st.form(f"form_edit_pag_{p['id']}"):
                    e1, e2 = st.columns(2)
                    ed_valor_pag = input_moeda(e1, "Valor (R$)", f"pv_{p['id']}",
                                                valor_inicial=float(p["valor"]))
                    ed_venc = e2.date_input(
                        "Vencimento",
                        value=date.fromisoformat(p["data_vencimento"][:10])
                        if p["data_vencimento"] else date.today(),
                        format="DD/MM/YYYY", key=f"pd_{p['id']}",
                    )
                    b1, b2, b3 = st.columns(3)
                    salvar_pag = b1.form_submit_button("💾 Salvar",
                                                        width="stretch")
                    excluir_pag = b2.form_submit_button("🗑️ Excluir conta",
                                                         width="stretch")
                    cancelar_pag = b3.form_submit_button("Cancelar",
                                                          width="stretch")
                    if salvar_pag:
                        if ed_valor_pag > 0:
                            financeiro.atualizar_pagamento(p["id"], ed_valor_pag, ed_venc)
                            st.session_state[chave_ed_pag] = False
                            st.success("Conta atualizada!")
                            st.rerun()
                        else:
                            st.error("Informe um valor maior que zero.")
                    if excluir_pag:
                        financeiro.excluir_pagamento(p["id"])
                        st.session_state[chave_ed_pag] = False
                        st.rerun()
                    if cancelar_pag:
                        st.session_state[chave_ed_pag] = False
                        st.rerun()
