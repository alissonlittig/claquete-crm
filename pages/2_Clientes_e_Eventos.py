"""
Página: Clientes e Eventos
---------------------------
Núcleo do CRM: cadastro de clientes, criação e edição de eventos/projetos,
definição de como a receita de cada projeto é dividida (em %) entre a empresa
e os sócios, e registro dos recebimentos conforme o cliente paga.

Observações sobre o funcionamento:
- Um projeto pode ser criado já digitando um CLIENTE NOVO, sem precisar
  cadastrá-lo antes em outra aba (ver `obter_ou_criar_cliente`).
- O painel de um projeto continua ABERTO depois de salvar qualquer alteração,
  graças ao controle em `st.session_state["projeto_aberto"]`.
"""

from datetime import date

import pandas as pd
import streamlit as st

import auth
from database import init_db
from db_utils import formatar_data_br, formatar_moeda
from services import eventos as eventos_service
from services import socios as socios_service
from ui import charts, theme
from ui.componentes import input_moeda, input_percentual, periodo_iso, seletor_periodo

st.set_page_config(page_title="Clientes e Eventos · Claquete",
                   page_icon="assets/claquete_monograma.png", layout="wide")
init_db()
theme.injetar_css()
auth.exigir_login()
theme.menu_lateral()
theme.cabecalho("Clientes e Eventos",
                "CRM da produtora: da negociação ao recebimento.")

TIPOS_EVENTO = ["Institucional", "Publicidade", "Evento", "Casamento",
                "Documentário", "Outro"]
OPCAO_NOVO_CLIENTE = "➕ Cadastrar um cliente novo"

data_ini, data_fim = seletor_periodo("eventos", atalho_padrao="Este ano")
data_ini_iso, data_fim_iso = periodo_iso(data_ini, data_fim)
st.write("")

aba_visao, aba_eventos, aba_clientes = st.tabs(
    ["📊 Visão Geral", "🎬 Eventos/Projetos", "🧑‍💼 Clientes"]
)

# =====================================================================
# ABA: VISÃO GERAL
# =====================================================================
with aba_visao:
    eventos_periodo = eventos_service.listar_eventos(
        data_ini=data_ini_iso, data_fim=data_fim_iso)
    total_contratado = sum(e["valor_total"] for e in eventos_periodo)
    total_recebido = sum(e["total_recebido"] for e in eventos_periodo)
    total_pendente = round(total_contratado - total_recebido, 2)
    ticket_medio = round(total_contratado / len(eventos_periodo), 2) if eventos_periodo else 0

    c1, c2, c3, c4 = st.columns(4)
    theme.kpi_card(c1, "Projetos no Período", str(len(eventos_periodo)),
                   f"ticket médio {formatar_moeda(ticket_medio)}")
    theme.kpi_card(c2, "Valor Contratado", formatar_moeda(total_contratado))
    theme.kpi_card(c3, "Já Recebido", formatar_moeda(total_recebido),
                   f"{(total_recebido / total_contratado * 100):.0f}% do contratado"
                   if total_contratado else "", theme.POSITIVO)
    theme.kpi_card(c4, "A Receber", formatar_moeda(total_pendente), "", theme.ALERTA)

    st.write("")
    col_a, col_b = st.columns(2)
    with col_a:
        with st.container(border=True):
            charts.renderizar(charts.grafico_funil_eventos(
                eventos_service.funil_status(data_ini_iso, data_fim_iso)))
    with col_b:
        with st.container(border=True):
            ranking = eventos_service.ranking_clientes_por_receita(
                6, data_ini_iso, data_fim_iso)
            charts.renderizar(charts.grafico_barra_horizontal(
                [r["nome"] for r in ranking], [r["receita_total"] for r in ranking],
                "Receita Contratada por Cliente",
            ))

    with st.container(border=True):
        charts.renderizar(charts.grafico_recebido_vs_pendente(eventos_periodo[:8]))

# =====================================================================
# ABA: EVENTOS / PROJETOS
# =====================================================================
with aba_eventos:
    clientes_lista = eventos_service.listar_clientes()
    nomes_clientes = [c["nome"] for c in clientes_lista]

    # ---------------------------------------------------------- criar projeto
    with st.expander("➕ Criar novo projeto", expanded=not clientes_lista):
        with st.form("form_novo_evento", clear_on_submit=True):
            st.markdown("**Cliente**")
            cliente_escolhido = st.selectbox(
                "Selecione um cliente já cadastrado ou cadastre um novo",
                [OPCAO_NOVO_CLIENTE] + nomes_clientes,
                help="Comece a digitar para filtrar a lista — não precisa apertar Enter.",
            )
            nome_cliente_novo = st.text_input(
                "Nome do cliente novo",
                placeholder="Preencha apenas se escolheu 'Cadastrar um cliente novo' acima",
            )

            st.divider()
            st.markdown("**Projeto**")
            c1, c2 = st.columns([3, 2])
            nome_evento = c1.text_input("Nome do projeto*")
            tipo_evento = c2.selectbox("Tipo", TIPOS_EVENTO)

            c3, c4, c5 = st.columns(3)
            data_evento = c3.date_input("Data do evento", value=date.today(),
                                         format="DD/MM/YYYY")
            valor_total = input_moeda(c4, "Valor total do contrato (R$)", "valor_novo_evento")
            status_evento = c5.selectbox("Status", eventos_service.STATUS_EVENTO)
            obs_evento = st.text_area("Descrição do projeto", height=110, key="obs_evento_novo",
                                       placeholder="Escopo, briefing, o que foi combinado...")

            if st.form_submit_button("Criar projeto", width="stretch"):
                if not nome_evento.strip():
                    st.error("Informe o nome do projeto.")
                elif valor_total <= 0:
                    st.error("Informe um valor de contrato maior que zero.")
                else:
                    try:
                        if cliente_escolhido == OPCAO_NOVO_CLIENTE:
                            if not nome_cliente_novo.strip():
                                raise ValueError(
                                    "Digite o nome do cliente novo no campo indicado.")
                            cliente_id = eventos_service.obter_ou_criar_cliente(
                                nome_cliente_novo)
                        else:
                            cliente_id = next(
                                c["id"] for c in clientes_lista
                                if c["nome"] == cliente_escolhido
                            )
                        novo_id = eventos_service.criar_evento(
                            cliente_id, nome_evento, tipo_evento, data_evento,
                            valor_total, status_evento, obs_evento,
                        )
                        st.session_state["projeto_aberto"] = novo_id
                        st.success(f"Projeto **{nome_evento}** criado!")
                        st.rerun()
                    except ValueError as erro:
                        st.error(str(erro))

    # ---------------------------------------------------------- lista de projetos
    st.markdown("### Projetos cadastrados")
    col_f1, col_f2 = st.columns([1, 1])
    filtro_status = col_f1.selectbox("Filtrar por status",
                                      ["Todos"] + eventos_service.STATUS_EVENTO)
    filtro_cliente = col_f2.selectbox("Filtrar por cliente", ["Todos"] + nomes_clientes)

    cliente_id_filtro = None
    if filtro_cliente != "Todos":
        cliente_id_filtro = next(c["id"] for c in clientes_lista
                                  if c["nome"] == filtro_cliente)

    lista_eventos = eventos_service.listar_eventos(
        cliente_id=cliente_id_filtro,
        status=None if filtro_status == "Todos" else filtro_status,
        data_ini=data_ini_iso, data_fim=data_fim_iso,
    )

    if not lista_eventos:
        st.info("Nenhum projeto encontrado para o período e filtros selecionados.")

    socios_ativos = socios_service.listar_socios(apenas_ativos=True)
    projeto_aberto = st.session_state.get("projeto_aberto")

    for ev in lista_eventos:
        resumo = (
            f"{ev['nome']}  ·  {ev['cliente_nome']}  ·  "
            f"{formatar_moeda(ev['valor_total'])}  ·  {ev['status']}"
        )
        with st.expander(resumo, expanded=(projeto_aberto == ev["id"])):
            detalhe = eventos_service.obter_evento(ev["id"])
            chave_edicao = f"editando_evento_{ev['id']}"

            # --------- linha de status + ações rápidas ---------
            st.markdown(
                f"{theme.badge_status(ev['status'])} &nbsp;&nbsp; "
                f"<span style='color:{theme.TEXTO_SECUNDARIO}'>Data do evento: "
                f"{formatar_data_br(ev['data_evento'])} · {ev['tipo'] or 'Sem tipo'}</span>",
                unsafe_allow_html=True,
            )

            ca1, ca2, ca3 = st.columns([2, 1, 1])
            novo_status = ca1.selectbox(
                "Status do projeto", eventos_service.STATUS_EVENTO,
                index=eventos_service.STATUS_EVENTO.index(ev["status"]),
                key=f"status_{ev['id']}",
            )
            if ca2.button("💾 Salvar status", key=f"salvar_status_{ev['id']}",
                          width="stretch"):
                eventos_service.atualizar_status(ev["id"], novo_status)
                st.session_state["projeto_aberto"] = ev["id"]
                st.success("Status atualizado.")
                st.rerun()
            if ca3.button("✏️ Editar projeto", key=f"btn_edit_ev_{ev['id']}",
                          width="stretch"):
                st.session_state[chave_edicao] = True
                st.session_state["projeto_aberto"] = ev["id"]
                st.rerun()

            # --------- formulário de edição do projeto ---------
            if st.session_state.get(chave_edicao, False):
                st.divider()
                st.markdown("#### ✏️ Editar dados do projeto")
                with st.form(f"form_edit_evento_{ev['id']}"):
                    e1, e2 = st.columns([3, 2])
                    ed_nome = e1.text_input("Nome do projeto*", value=ev["nome"],
                                             key=f"ed_nome_{ev['id']}")
                    ed_tipo = e2.selectbox(
                        "Tipo", TIPOS_EVENTO,
                        index=TIPOS_EVENTO.index(ev["tipo"]) if ev["tipo"] in TIPOS_EVENTO else 0,
                        key=f"ed_tipo_{ev['id']}",
                    )
                    e3, e4, e5 = st.columns(3)
                    ed_cliente = e3.selectbox(
                        "Cliente", nomes_clientes,
                        index=nomes_clientes.index(ev["cliente_nome"])
                        if ev["cliente_nome"] in nomes_clientes else 0,
                        key=f"ed_cli_{ev['id']}",
                    )
                    ed_data = e4.date_input(
                        "Data do evento",
                        value=date.fromisoformat(ev["data_evento"][:10])
                        if ev["data_evento"] else date.today(),
                        format="DD/MM/YYYY", key=f"ed_data_{ev['id']}",
                    )
                    ed_valor = input_moeda(e5, "Valor total (R$)", f"ed_valor_{ev['id']}",
                                            valor_inicial=float(ev["valor_total"]))
                    ed_obs = st.text_area("Descrição do projeto", value=ev["observacao"] or "",
                                           height=140, key=f"ed_obs_{ev['id']}",
                                           help="Escopo, briefing, o que foi combinado com o cliente.")

                    b1, b2 = st.columns(2)
                    salvar_ev = b1.form_submit_button("💾 Salvar alterações",
                                                       width="stretch")
                    cancelar_ev = b2.form_submit_button("Cancelar", width="stretch")

                    if salvar_ev:
                        if not ed_nome.strip() or ed_valor <= 0:
                            st.error("Informe o nome e um valor maior que zero.")
                        else:
                            novo_cliente_id = next(
                                c["id"] for c in clientes_lista if c["nome"] == ed_cliente)
                            eventos_service.atualizar_evento(
                                ev["id"], ed_nome, ed_tipo, ed_data, ed_valor,
                                novo_status, ed_obs, cliente_id=novo_cliente_id,
                            )
                            st.session_state[chave_edicao] = False
                            st.session_state["projeto_aberto"] = ev["id"]
                            st.success("Projeto atualizado!")
                            st.rerun()
                    if cancelar_ev:
                        st.session_state[chave_edicao] = False
                        st.rerun()

            st.divider()
            col_div, col_receb = st.columns(2)

            # --------- descrição e documentos do projeto ---------
            with col_div:
                st.markdown("#### 📝 Descrição do projeto")
                descricao_atual = detalhe.get("observacao") or ""
                if descricao_atual.strip():
                    st.markdown(
                        f"<div style='background:{theme.SUPERFICIE};border:1px solid "
                        f"{theme.BORDA};border-radius:12px;padding:14px 16px;"
                        f"white-space:pre-wrap'>{theme.esc(descricao_atual)}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption(
                        "Sem descrição ainda. Use **Editar projeto** para "
                        "registrar o escopo, o briefing e o que foi combinado."
                    )

                st.markdown("#### 📎 Contratos, notas fiscais e documentos")
                st.caption(
                    "Guarde aqui o **link** do arquivo no Drive. O documento "
                    "continua no Drive — o sistema apenas aponta para ele."
                )

                anexos = detalhe.get("anexos", [])
                if anexos:
                    for anexo in anexos:
                        an1, an2, an3 = st.columns([1.6, 3.4, 0.8])
                        an1.markdown(
                            f"<span style='font-size:0.88rem;font-weight:600'>"
                            f"{theme.esc(anexo['tipo'])}</span>",
                            unsafe_allow_html=True,
                        )
                        rotulo = anexo["descricao"] or "abrir documento"
                        an2.markdown(f"[{rotulo}]({anexo['url']})")
                        if an3.button("🗑️", key=f"del_anexo_{anexo['id']}",
                                      help="Remover este link"):
                            eventos_service.excluir_anexo(anexo["id"])
                            st.session_state["projeto_aberto"] = ev["id"]
                            st.rerun()
                else:
                    st.caption("Nenhum documento vinculado ainda.")

                with st.form(f"form_anexo_{ev['id']}", clear_on_submit=True):
                    fa1, fa2 = st.columns([1.2, 2.8])
                    tipo_anexo = fa1.selectbox(
                        "Tipo", eventos_service.TIPOS_ANEXO,
                        key=f"tipo_anexo_{ev['id']}",
                    )
                    desc_anexo = fa2.text_input(
                        "Descrição (opcional)", key=f"desc_anexo_{ev['id']}",
                        placeholder="Ex: Contrato assinado, NF 0012...",
                    )
                    url_anexo = st.text_input(
                        "Link do Drive*", key=f"url_anexo_{ev['id']}",
                        placeholder="https://drive.google.com/...",
                    )
                    if st.form_submit_button("Vincular documento",
                                              width="stretch"):
                        try:
                            eventos_service.adicionar_anexo(
                                ev["id"], tipo_anexo, url_anexo, desc_anexo)
                            st.session_state["projeto_aberto"] = ev["id"]
                            st.success("Documento vinculado!")
                            st.rerun()
                        except ValueError as erro:
                            st.error(str(erro))

            # --------- recebimentos ---------
            with col_receb:
                st.markdown("#### 💰 Recebimentos do cliente")
                pct_recebido = (
                    detalhe["total_recebido"] / ev["valor_total"] * 100
                    if ev["valor_total"] else 0
                )
                st.markdown(
                    f"<span style='font-size:1.02rem'>"
                    f"Recebido: <b>{formatar_moeda(detalhe['total_recebido'])}</b> "
                    f"({pct_recebido:.0f}%) &nbsp;·&nbsp; "
                    f"Pendente: <b>{formatar_moeda(detalhe['total_pendente'])}</b>"
                    f"</span>",
                    unsafe_allow_html=True,
                )
                st.progress(min(pct_recebido / 100, 1.0))

                for r in detalhe["recebimentos"]:
                    rc1, rc2, rc3, rc4 = st.columns([2, 2, 2, 0.9])
                    rc1.markdown(formatar_data_br(r["data"]))
                    rc2.markdown(f"**{formatar_moeda(r['valor'])}**")
                    forma = r["forma_pagamento"] or "—"
                    recibo = (f" · [recibo]({r['link_recibo']})"
                              if r.get("link_recibo") else "")
                    rc3.markdown(
                        f"<span style='font-size:0.82rem;color:{theme.TEXTO_SECUNDARIO}'>"
                        f"{theme.esc(forma)}</span>{recibo}",
                        unsafe_allow_html=True,
                    )
                    if rc4.button("🗑️", key=f"del_receb_{r['id']}"):
                        eventos_service.excluir_recebimento(r["id"])
                        st.session_state["projeto_aberto"] = ev["id"]
                        st.rerun()

                with st.form(f"form_recebimento_{ev['id']}", clear_on_submit=True):
                    fr1, fr2 = st.columns(2)
                    data_receb = fr1.date_input("Data", value=date.today(),
                                                 format="DD/MM/YYYY",
                                                 key=f"data_receb_{ev['id']}")
                    valor_receb = input_moeda(fr2, "Valor recebido (R$)",
                                               f"valor_receb_{ev['id']}")
                    forma_receb = st.text_input("Forma de pagamento",
                                                 key=f"forma_receb_{ev['id']}",
                                                 placeholder="Pix, boleto, cartão...")
                    link_recibo = st.text_input(
                        "Link do recibo no Drive (opcional)",
                        key=f"link_receb_{ev['id']}",
                        placeholder="https://drive.google.com/...",
                    )
                    if st.form_submit_button("Registrar recebimento",
                                              width="stretch"):
                        if valor_receb > 0:
                            eventos_service.registrar_recebimento(
                                ev["id"], data_receb, valor_receb, forma_receb,
                                link_recibo=link_recibo)
                            st.session_state["projeto_aberto"] = ev["id"]
                            st.success("Recebimento registrado!")
                            st.rerun()
                        else:
                            st.error("Informe um valor maior que zero.")

            st.divider()
            if st.button("🗑️ Excluir este projeto", key=f"del_evento_{ev['id']}",
                         type="secondary"):
                eventos_service.excluir_evento(ev["id"])
                st.session_state["projeto_aberto"] = None
                st.rerun()

# =====================================================================
# ABA: CLIENTES
# =====================================================================
with aba_clientes:
    with st.expander("➕ Cadastrar novo cliente", expanded=False):
        with st.form("form_novo_cliente", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nome_cli = c1.text_input("Nome*")
            empresa_cli = c2.text_input("Empresa (opcional)")
            c3, c4 = st.columns(2)
            email_cli = c3.text_input("E-mail")
            telefone_cli = c4.text_input("Telefone")
            origem_cli = st.text_input("Origem",
                                        placeholder="Ex: Indicação, Instagram, Site...")
            obs_cli = st.text_area("Observação", height=68)
            if st.form_submit_button("Cadastrar cliente", width="stretch"):
                if nome_cli.strip():
                    eventos_service.criar_cliente(nome_cli, empresa_cli, email_cli,
                                                   telefone_cli, origem_cli, obs_cli)
                    st.success(f"Cliente **{nome_cli}** cadastrado!")
                    st.rerun()
                else:
                    st.error("Informe o nome do cliente.")

    st.markdown("### Clientes cadastrados")
    todos_clientes = eventos_service.listar_clientes()
    if todos_clientes:
        busca = st.selectbox(
            "🔎 Buscar cliente",
            ["Todos"] + [c["nome"] for c in todos_clientes],
            help="Comece a digitar para filtrar — não precisa apertar Enter.",
        )
        exibidos = (todos_clientes if busca == "Todos"
                    else [c for c in todos_clientes if c["nome"] == busca])
    else:
        exibidos = []
        st.info("Nenhum cliente cadastrado ainda.")

    for c in exibidos:
        chave_edicao_cli = f"editando_cliente_{c['id']}"
        with st.container(border=True):
            if not st.session_state.get(chave_edicao_cli, False):
                col1, col2, col3, col4 = st.columns([3, 3, 1.2, 1.2])
                col1.markdown(
                    f"**{theme.esc(c['nome'])}**" + (f"  \n{theme.esc(c['empresa'])}" if c["empresa"] else "")
                )
                contato = " · ".join(filter(None, [c["email"], c["telefone"]])) or "—"
                col2.markdown(
                    f"<span style='font-size:0.86rem'>📇 {theme.esc(contato)}<br>"
                    f"🏷️ {theme.esc(c['origem'] or '—')}</span>",
                    unsafe_allow_html=True,
                )
                if col3.button("✏️ Editar", key=f"edit_cli_{c['id']}",
                               width="stretch"):
                    st.session_state[chave_edicao_cli] = True
                    st.rerun()
                if col4.button("🗑️ Excluir", key=f"del_cliente_{c['id']}",
                               type="secondary", width="stretch"):
                    eventos_service.excluir_cliente(c["id"])
                    st.rerun()
            else:
                st.markdown(f"#### ✏️ Editando: {c['nome']}")
                with st.form(f"form_edit_cliente_{c['id']}"):
                    d1, d2 = st.columns(2)
                    ed_nome_cli = d1.text_input("Nome*", value=c["nome"],
                                                 key=f"ecn_{c['id']}")
                    ed_empresa = d2.text_input("Empresa", value=c["empresa"] or "",
                                                key=f"ece_{c['id']}")
                    d3, d4 = st.columns(2)
                    ed_email = d3.text_input("E-mail", value=c["email"] or "",
                                              key=f"ecm_{c['id']}")
                    ed_tel = d4.text_input("Telefone", value=c["telefone"] or "",
                                            key=f"ect_{c['id']}")
                    ed_origem = st.text_input("Origem", value=c["origem"] or "",
                                               key=f"eco_{c['id']}")
                    ed_obs_cli = st.text_area("Observação", value=c["observacao"] or "",
                                               height=68, key=f"ecb_{c['id']}")
                    b1, b2 = st.columns(2)
                    salvar_cli = b1.form_submit_button("💾 Salvar alterações",
                                                        width="stretch")
                    cancelar_cli = b2.form_submit_button("Cancelar",
                                                          width="stretch")
                    if salvar_cli:
                        if ed_nome_cli.strip():
                            eventos_service.atualizar_cliente(
                                c["id"], ed_nome_cli, ed_empresa, ed_email,
                                ed_tel, ed_origem, ed_obs_cli,
                            )
                            st.session_state[chave_edicao_cli] = False
                            st.success("Cliente atualizado!")
                            st.rerun()
                        else:
                            st.error("O nome não pode ficar vazio.")
                    if cancelar_cli:
                        st.session_state[chave_edicao_cli] = False
                        st.rerun()
