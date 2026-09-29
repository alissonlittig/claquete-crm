"""
Página: Sócios e Aportes
------------------------
Cadastro e edição de sócios, registro de aportes de capital (dinheiro ou
despesas pagas diretamente pelo sócio), reembolsos, controle de dívida da
empresa com cada sócio.

Os sócios são remunerados por pró-labore fixo (ver Custos Fixos), e não mais
por uma fatia de cada projeto — por isso não há relatório de ganhos aqui.
"""

from datetime import date

import pandas as pd
import streamlit as st

import auth
from database import init_db
from db_utils import formatar_data_br, formatar_moeda
from services import socios as socios_service
from ui import charts, theme
from ui.componentes import input_moeda, periodo_iso, seletor_periodo

st.set_page_config(page_title="Sócios e Aportes · Claquete",
                   page_icon="assets/claquete_monograma.png", layout="wide")
init_db()
theme.injetar_css()
auth.exigir_login()
theme.menu_lateral()
theme.cabecalho("Sócios e Aportes",
                "Capital investido pelos sócios e dívidas da empresa com cada um.")

CATEGORIAS_APORTE = [
    "Dinheiro em Caixa", "Despesa Operacional", "Assinatura/Software",
    "Investimento", "Equipamento", "Outro",
]

data_ini, data_fim = seletor_periodo("socios", atalho_padrao="Este ano")
data_ini_iso, data_fim_iso = periodo_iso(data_ini, data_fim)
st.write("")

aba_visao, aba_socios, aba_aportes, aba_reembolsos = st.tabs(
    ["📊 Visão Geral", "👤 Sócios", "💰 Aportes", "↩️ Reembolsos"]
)

# =====================================================================
# ABA: VISÃO GERAL
# =====================================================================
with aba_visao:
    dividas = socios_service.resumo_dividas()

    if not dividas:
        st.info("Cadastre o primeiro sócio na aba **Sócios** para começar.")
    else:
        cols = st.columns(len(dividas))
        for col, d in zip(cols, dividas):
            theme.kpi_card(
                col, d["nome"], formatar_moeda(d["saldo_devedor"]),
                f"aportou {formatar_moeda(d['total_aportado'])}",
                theme.NEGATIVO if d["saldo_devedor"] > 0 else theme.POSITIVO,
            )

        st.write("")
        with st.container(border=True):
            charts.renderizar(charts.grafico_barra_horizontal(
                [d["nome"] for d in dividas],
                [d["saldo_devedor"] for d in dividas],
                "Saldo Devedor por Sócio",
            ))

        st.info(
            "Os sócios são remunerados por **pró-labore fixo**, cadastrado na aba "
            "**Custos Fixos**. Esta tela acompanha apenas o capital que cada um "
            "investiu na empresa e o quanto ainda há para reembolsar."
        )

# =====================================================================
# ABA: SÓCIOS (cadastro + edição)
# =====================================================================
with aba_socios:
    with st.expander("➕ Cadastrar novo sócio", expanded=False):
        with st.form("form_novo_socio", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            nome = c1.text_input("Nome*")
            email = c2.text_input("E-mail")
            telefone = c3.text_input("Telefone")
            data_entrada = st.date_input("Data de entrada na sociedade",
                                          value=date.today(), format="DD/MM/YYYY")
            if st.form_submit_button("Cadastrar sócio", width="stretch"):
                if nome.strip():
                    socios_service.criar_socio(nome, email, telefone, data_entrada)
                    st.success(f"Sócio **{nome}** cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.error("Informe o nome do sócio.")

    st.markdown("### Sócios cadastrados")
    st.caption("Clique em **Editar** para alterar os dados de um sócio.")

    for s in socios_service.listar_socios():
        chave_edicao = f"editando_socio_{s['id']}"
        editando = st.session_state.get(chave_edicao, False)

        with st.container(border=True):
            if not editando:
                c1, c2, c3, c4, c5 = st.columns([3, 2.4, 2, 1.2, 1.2])
                c1.markdown(
                    f"**{theme.esc(s['nome'])}**  \n"
                    f"<span style='font-size:0.82rem;color:{theme.TEXTO_SECUNDARIO}'>"
                    f"{theme.esc(s['email'] or '—')}</span>",
                    unsafe_allow_html=True,
                )
                c2.markdown(f"📞 {theme.esc(s['telefone'] or '—')}")
                c3.markdown(
                    f"<span style='font-size:0.85rem'>Desde "
                    f"{formatar_data_br(s['data_entrada'])}</span>",
                    unsafe_allow_html=True,
                )
                if c4.button("✏️ Editar", key=f"btn_edit_socio_{s['id']}",
                             width="stretch"):
                    st.session_state[chave_edicao] = True
                    st.rerun()
                ativo_novo = c5.toggle("Ativo", value=bool(s["ativo"]), key=f"ativo_{s['id']}")
                if ativo_novo != bool(s["ativo"]):
                    socios_service.alternar_ativo(s["id"], ativo_novo)
                    st.rerun()
            else:
                st.markdown(f"#### ✏️ Editando: {s['nome']}")
                with st.form(f"form_edit_socio_{s['id']}"):
                    e1, e2, e3 = st.columns(3)
                    novo_nome = e1.text_input("Nome*", value=s["nome"],
                                               key=f"en_{s['id']}")
                    novo_email = e2.text_input("E-mail", value=s["email"] or "",
                                                key=f"ee_{s['id']}")
                    novo_tel = e3.text_input("Telefone", value=s["telefone"] or "",
                                              key=f"et_{s['id']}")
                    b1, b2 = st.columns(2)
                    salvar = b1.form_submit_button("💾 Salvar alterações",
                                                    width="stretch")
                    cancelar = b2.form_submit_button("Cancelar", width="stretch")

                    if salvar:
                        if novo_nome.strip():
                            socios_service.atualizar_socio(
                                s["id"], novo_nome, novo_email, novo_tel)
                            st.session_state[chave_edicao] = False
                            st.success("Dados atualizados!")
                            st.rerun()
                        else:
                            st.error("O nome não pode ficar vazio.")
                    if cancelar:
                        st.session_state[chave_edicao] = False
                        st.rerun()

# =====================================================================
# ABA: APORTES
# =====================================================================
with aba_aportes:
    socios_lista = socios_service.listar_socios(apenas_ativos=True)
    if not socios_lista:
        st.warning("Cadastre um sócio ativo antes de registrar aportes.")
    else:
        with st.expander("➕ Registrar novo aporte", expanded=False):
            with st.form("form_novo_aporte", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                socio_sel = c1.selectbox("Sócio", socios_lista,
                                          format_func=lambda s: s["nome"])
                data_aporte = c2.date_input("Data", value=date.today(),
                                             format="DD/MM/YYYY", key="data_aporte")
                valor_aporte = input_moeda(c3, "Valor (R$)", "valor_aporte")

                descricao_aporte = st.text_input(
                    "Descrição*",
                    placeholder="Ex: dinheiro em caixa, compra de equipamento...",
                )
                c4, c5, c6 = st.columns(3)
                categoria_aporte = c4.selectbox("Categoria", CATEGORIAS_APORTE)
                entrou_caixa = c5.checkbox(
                    "💵 Entrou na conta da empresa?", value=True,
                    help="Desmarque se o sócio pagou uma despesa direto do próprio "
                         "bolso, sem o dinheiro passar pela conta da empresa.",
                )
                reembolsavel = c6.checkbox("↩️ Deve ser reembolsado ao sócio?", value=True)
                observacao_aporte = st.text_area("Observação", height=68)

                if st.form_submit_button("Registrar aporte", width="stretch"):
                    if descricao_aporte.strip() and valor_aporte > 0:
                        socios_service.registrar_aporte(
                            socio_sel["id"], data_aporte, descricao_aporte, valor_aporte,
                            categoria_aporte, entrou_caixa, reembolsavel, observacao_aporte,
                        )
                        st.success("Aporte registrado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Informe a descrição e um valor maior que zero.")

        st.markdown("### Histórico de aportes")
        filtro_socio = st.selectbox(
            "Filtrar por sócio", ["Todos"] + [s["nome"] for s in socios_lista],
            key="filtro_aportes",
        )
        socio_id_filtro = None
        if filtro_socio != "Todos":
            socio_id_filtro = next(s["id"] for s in socios_lista if s["nome"] == filtro_socio)

        aportes = socios_service.listar_aportes(
            socio_id=socio_id_filtro, data_ini=data_ini_iso, data_fim=data_fim_iso)
        if not aportes:
            st.caption("Nenhum aporte registrado neste período.")
        for a in aportes:
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([2, 3, 2, 2, 0.9])
                c1.markdown(f"**{theme.esc(a['socio_nome'])}**  \n{formatar_data_br(a['data'])}")
                c2.markdown(
                    f"{theme.esc(a['descricao'])}  \n"
                    f"<span style='font-size:0.8rem;color:{theme.TEXTO_SECUNDARIO}'>"
                    f"{theme.esc(a['categoria'])}</span>",
                    unsafe_allow_html=True,
                )
                c3.markdown(f"### {formatar_moeda(a['valor'])}")
                origem = "💵 Entrou no caixa" if a["entrou_no_caixa"] else "🧾 Pago direto"
                reemb = "↩️ Reembolsável" if a["reembolsavel"] else "🎁 Não reembolsável"
                c4.markdown(
                    f"<span style='font-size:0.85rem'>{origem}<br>{reemb}</span>",
                    unsafe_allow_html=True,
                )
                if c5.button("🗑️", key=f"del_aporte_{a['id']}", help="Excluir aporte"):
                    socios_service.excluir_aporte(a["id"])
                    st.rerun()

# =====================================================================
# ABA: REEMBOLSOS
# =====================================================================
with aba_reembolsos:
    socios_lista = socios_service.listar_socios(apenas_ativos=True)
    if not socios_lista:
        st.warning("Cadastre um sócio ativo antes de registrar reembolsos.")
    else:
        with st.expander("➕ Registrar novo reembolso", expanded=False):
            with st.form("form_novo_reembolso", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                socio_sel_r = c1.selectbox("Sócio", socios_lista,
                                            format_func=lambda s: s["nome"],
                                            key="socio_reembolso")
                data_reembolso = c2.date_input("Data", value=date.today(),
                                                format="DD/MM/YYYY", key="data_reembolso")
                valor_reembolso = input_moeda(c3, "Valor (R$)", "valor_reembolso")
                descricao_reembolso = st.text_input("Descrição (opcional)",
                                                     key="desc_reembolso")

                saldo_atual = socios_service.saldo_devedor(socio_sel_r["id"])
                st.caption(
                    f"Saldo devedor atual com {socio_sel_r['nome']}: "
                    f"**{formatar_moeda(saldo_atual)}**"
                )

                if st.form_submit_button("Registrar reembolso", width="stretch"):
                    if valor_reembolso > 0:
                        socios_service.registrar_reembolso(
                            socio_sel_r["id"], data_reembolso,
                            valor_reembolso, descricao_reembolso,
                        )
                        st.success("Reembolso registrado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Informe um valor maior que zero.")

        st.markdown("### Histórico de reembolsos")
        reembolsos = socios_service.listar_reembolsos()
        if not reembolsos:
            st.caption("Nenhum reembolso registrado ainda.")
        else:
            df = pd.DataFrame(reembolsos)[["data", "socio_nome", "valor", "descricao"]].copy()
            df["data"] = df["data"].apply(formatar_data_br)
            df["valor"] = df["valor"].apply(formatar_moeda)
            df.columns = ["Data", "Sócio", "Valor", "Descrição"]
            st.dataframe(df, width="stretch", hide_index=True)
