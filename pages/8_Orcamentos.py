"""
Página: Orçamentos
-------------------
Precificação de projetos e geração da proposta comercial.

COMO FUNCIONA
    1. Em **Orçamentos**, você cria o orçamento e preenche a grade de serviços:
       TODOS os serviços aparecem de uma vez. Basta digitar as horas (e, se
       quiser, pessoas e valor) só naqueles que fazem parte do projeto —
       nenhum é obrigatório. Os campos vazios são ignorados.
    2. Em **Proposta**, o sistema monta a proposta comercial com os dados da
       Claquete, do cliente, datas e valores. Você baixa o arquivo e imprime/salva
       em PDF — sai só a proposta, em folha A4.
    3. **Tabela de Preços** e **Dados da Empresa** são ajustados uma vez só.
"""

from datetime import date

import streamlit as st

import auth
from database import init_db
from db_utils import formatar_data_br, formatar_moeda
from services import eventos as eventos_service
from services import orcamentos as orc_service
from services import socios as socios_service
from ui import theme
from ui.componentes import _number_input_seguro, input_moeda, periodo_iso, seletor_periodo
from ui.proposta import _logo, formatar_quantidade, gerar_html_proposta

st.set_page_config(page_title="Orçamentos · Claquete",
                   page_icon="assets/claquete_monograma.png", layout="wide")
init_db()
theme.injetar_css()
auth.exigir_login()
theme.menu_lateral()
theme.cabecalho("Orçamentos",
                "Monte a precificação do projeto e gere a proposta para o cliente.")

orc_service.garantir_precos_iniciais()

UNIDADES = ["hora", "vez", "diária", "km", "mês", "unidade", "pacote"]
ROTULO_UNIDADE = {"hora": "horas", "vez": "vezes", "diária": "diárias", "km": "km",
                  "mês": "meses", "unidade": "unid.", "pacote": "pacotes"}
LINHAS_PERSONALIZADAS = 3
ESTILO_TITULO_GRADE = (f"font-size:0.76rem;text-transform:uppercase;letter-spacing:0.08em;"
                       f"font-weight:700;color:{theme.TEXTO_SECUNDARIO}")


OPCOES_PESSOAS = list(range(1, 11))


def _indice_pessoas(valor) -> int:
    """Posição na lista de pessoas (1 a 10); vazio conta como 1."""
    try:
        return max(0, min(int(valor or 1), 10) - 1)
    except (TypeError, ValueError):
        return 0


def _titulo_categoria(texto):
    st.markdown(
        f"<div style='margin:12px 0 2px;font-weight:700;"
        f"color:{theme.PRIMARIA_CLARA};font-size:0.92rem'>{theme.esc(texto)}</div>",
        unsafe_allow_html=True)


aba_orcamentos, aba_proposta, aba_historico, aba_precos, aba_empresa = st.tabs(
    ["🧮 Orçamentos", "📄 Emitir Proposta", "🗂️ Histórico de Propostas",
     "💲 Tabela de Preços", "🏢 Dados da Empresa"])

CORES_STATUS_ORC = {
    "Rascunho": theme.TEXTO_SECUNDARIO, "Enviado": theme.AZUL,
    "Aprovado": theme.POSITIVO, "Recusado": theme.NEGATIVO,
}


def _badge(texto, cor):
    return (f'<span class="badge" style="background-color:{cor}22;color:{cor};'
            f'border:1px solid {cor}55">{theme.esc(texto)}</span>')

# =====================================================================
# ABA: ORÇAMENTOS
# =====================================================================
with aba_orcamentos:
    nomes_clientes = [c["nome"] for c in eventos_service.listar_clientes()]
    nomes_socios = [s["nome"] for s in socios_service.listar_socios(apenas_ativos=True)]

    with st.expander("➕ Novo orçamento", expanded=False):
        with st.form("form_novo_orcamento", clear_on_submit=True):
            o1, o2 = st.columns(2)
            titulo_orc = o1.text_input("Título do projeto*",
                                        placeholder="Ex: Vídeo institucional 2026")
            cliente_sel = o2.selectbox(
                "Cliente*", ["➕ Digitar um cliente novo"] + nomes_clientes,
                help="Comece a digitar para filtrar a lista.")
            cliente_novo = st.text_input(
                "Nome do cliente novo",
                placeholder="Preencha só se escolheu 'Digitar um cliente novo'")
            o3, o4, o5 = st.columns(3)
            data_orc = o3.date_input("Data de emissão", value=date.today(),
                                      format="DD/MM/YYYY")
            validade = _number_input_seguro(
                o4, "Validade (dias)", "validade_novo_orc", min_value=1,
                value=None, step=1, placeholder="15")
            responsavel = o5.selectbox("Responsável pela proposta", ["—"] + nomes_socios)

            if st.form_submit_button("Criar orçamento", width="stretch"):
                nome_cliente = cliente_novo if cliente_sel.startswith("➕") else cliente_sel
                try:
                    novo_id = orc_service.criar_orcamento(
                        titulo_orc, nome_cliente, data_orc,
                        validade_dias=int(validade or 15))
                    if responsavel != "—":
                        o = orc_service.obter_orcamento(novo_id)
                        orc_service.atualizar_orcamento(
                            novo_id, o["titulo"], o["cliente_nome"], o["data"],
                            o["validade_dias"], o["status"], 0, "", "",
                            responsavel_nome=responsavel)
                    st.session_state["orcamento_aberto"] = novo_id
                    st.success("Orçamento criado! Agora preencha os serviços abaixo.")
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))

    lista_orc = orc_service.listar_orcamentos()
    if not lista_orc:
        st.info("Nenhum orçamento ainda. Crie o primeiro no botão acima.")

    aberto = st.session_state.get("orcamento_aberto")
    precos_ativos = orc_service.listar_precos(apenas_ativos=True)
    nomes_catalogo = {p["nome"] for p in precos_ativos}
    categorias = []
    for p in precos_ativos:
        if p["categoria"] not in categorias:
            categorias.append(p["categoria"])

    for o in lista_orc:
        resumo = (f"{o['titulo']}  ·  {o['cliente_nome']}  ·  "
                  f"{formatar_moeda(o['total'])}  ·  {o['status']}")
        with st.expander(resumo, expanded=(aberto == o["id"])):
            detalhe = orc_service.obter_orcamento(o["id"])
            itens_atuais = {i["descricao"]: i for i in detalhe["itens"]}

            k1, k2, k3, k4 = st.columns(4)
            theme.kpi_card(k1, "Total", formatar_moeda(detalhe["total"]))
            theme.kpi_card(k2, "Horas de trabalho",
                           formatar_quantidade(detalhe["horas_totais"], "hora")
                           if detalhe["horas_totais"] else "0h",
                           "somando toda a equipe")
            theme.kpi_card(k3, "Valor/hora efetivo",
                           formatar_moeda(detalhe["valor_hora_efetivo"]), "total ÷ horas")
            theme.kpi_card(k4, "Serviços incluídos", str(detalhe["quantidade_itens"]))

            # ---------------------------------------------------------- grade
            st.markdown("#### Serviços do projeto")
            st.caption(
                "Preencha as **horas** só dos serviços que fazem parte deste projeto — "
                "nenhum é obrigatório. **Pessoas** vazio conta como 1, e **Valor** "
                "vazio usa o preço da Tabela de Preços (mostrado em cinza). "
                "No **Deslocamento**, digite quantas vezes a equipe se desloca "
                "(normalmente 1) e escolha quantas pessoas vão.")

            with st.form(f"form_grade_{o['id']}"):
                h1, h2, h3, h4 = st.columns([3.2, 1.3, 1.1, 1.6])
                h1.markdown(f"<div style='{ESTILO_TITULO_GRADE}'>Serviço</div>",
                            unsafe_allow_html=True)
                h2.markdown(f"<div style='{ESTILO_TITULO_GRADE}'>Horas</div>",
                            unsafe_allow_html=True)
                h3.markdown(f"<div style='{ESTILO_TITULO_GRADE}'>Pessoas</div>",
                            unsafe_allow_html=True)
                h4.markdown(f"<div style='{ESTILO_TITULO_GRADE}'>Valor unitário (R$)</div>",
                            unsafe_allow_html=True)

                # Os campos de horas e valor são de TEXTO: aceitam "1h30", "1:30",
                # "45min" e "1.500,00", em vez de obrigar a digitar decimais.
                linhas = []
                for categoria in categorias:
                    _titulo_categoria(categoria)
                    for p in [x for x in precos_ativos if x["categoria"] == categoria]:
                        atual = itens_atuais.get(p["nome"])
                        # Se o serviço mudou de unidade depois de salvo (ex.: o
                        # deslocamento, que era por km e virou valor por pessoa),
                        # o valor antigo não é reaproveitado — "80 km" não pode
                        # virar "80 deslocamentos" sem ninguém perceber.
                        if atual and atual["unidade"] != p["unidade"]:
                            atual = None
                        c1, c2, c3, c4 = st.columns([3.2, 1.3, 1.1, 1.6])
                        eh_hora = p["unidade"] == "hora"
                        if eh_hora:
                            sufixo = ""
                        elif p["unidade"] == "vez":
                            sufixo = (f" <span style='color:{theme.TEXTO_SECUNDARIO};"
                                      f"font-size:0.82rem'>(valor fixo por pessoa)</span>")
                        else:
                            sufixo = (f" <span style='color:{theme.TEXTO_SECUNDARIO};"
                                      f"font-size:0.82rem'>(em "
                                      f"{ROTULO_UNIDADE.get(p['unidade'], p['unidade'])})</span>")
                        c1.markdown(f"<div style='padding-top:8px'>{theme.esc(p['nome'])}"
                                    f"{sufixo}</div>", unsafe_allow_html=True)

                        if atual:
                            texto_qtd = (orc_service.horas_para_texto(atual["quantidade"])
                                         if eh_hora else f"{atual['quantidade']:g}".replace(".", ","))
                        else:
                            texto_qtd = ""
                        txt_qtd = c2.text_input(
                            f"Horas {p['nome']}", value=texto_qtd,
                            key=f"q_{o['id']}_{p['id']}", label_visibility="collapsed",
                            placeholder=("ex: 1h30" if eh_hora
                                         else "ex: 1" if p["unidade"] == "vez"
                                         else f"ex: 10 {ROTULO_UNIDADE.get(p['unidade'], '')}"))
                        pessoas = c3.selectbox(
                            f"Pessoas {p['nome']}", OPCOES_PESSOAS,
                            index=_indice_pessoas(atual["pessoas"] if atual else 1),
                            key=f"p_{o['id']}_{p['id']}", label_visibility="collapsed")
                        valor_diferente = atual and atual["valor_unitario"] != p["valor_unitario"]
                        txt_valor = c4.text_input(
                            f"Valor {p['nome']}",
                            value=(orc_service.valor_para_texto(atual["valor_unitario"])
                                   if valor_diferente else ""),
                            key=f"v_{o['id']}_{p['id']}", label_visibility="collapsed",
                            placeholder=orc_service.valor_para_texto(p["valor_unitario"]))
                        linhas.append({
                            "descricao": p["nome"], "txt_qtd": txt_qtd, "pessoas": pessoas,
                            "txt_valor": txt_valor, "unidade": p["unidade"],
                            "categoria": p["categoria"], "preco_tabela": p["valor_unitario"]})

                # ---- linhas livres para serviços fora da tabela ----
                personalizados = [i for i in detalhe["itens"]
                                  if i["descricao"] not in nomes_catalogo]
                _titulo_categoria("Outros serviços (livre)")
                for n in range(max(LINHAS_PERSONALIZADAS, len(personalizados) + 1)):
                    atual = personalizados[n] if n < len(personalizados) else None
                    c1, c2, c3, c4 = st.columns([3.2, 1.3, 1.1, 1.6])
                    nome_livre = c1.text_input(
                        f"Serviço livre {n}", key=f"nl_{o['id']}_{n}",
                        value=atual["descricao"] if atual else "",
                        placeholder="Ex: Aluguel de estúdio", label_visibility="collapsed")
                    txt_qtd = c2.text_input(
                        f"Horas livre {n}", key=f"ql_{o['id']}_{n}",
                        value=orc_service.horas_para_texto(atual["quantidade"]) if atual else "",
                        placeholder="ex: 2h", label_visibility="collapsed")
                    pessoas = c3.selectbox(
                        f"Pessoas livre {n}", OPCOES_PESSOAS,
                        index=_indice_pessoas(atual["pessoas"] if atual else 1),
                        key=f"pl_{o['id']}_{n}", label_visibility="collapsed")
                    txt_valor = c4.text_input(
                        f"Valor livre {n}", key=f"vl_{o['id']}_{n}",
                        value=orc_service.valor_para_texto(atual["valor_unitario"]) if atual else "",
                        placeholder="0,00", label_visibility="collapsed")
                    linhas.append({
                        "descricao": nome_livre, "txt_qtd": txt_qtd, "pessoas": pessoas,
                        "txt_valor": txt_valor, "unidade": "hora",
                        "categoria": atual["categoria"] if atual else "Outro",
                        "preco_tabela": 0})

                st.write("")
                if st.form_submit_button("💾 Salvar e calcular", width="stretch"):
                    entradas, erros, sem_valor = [], [], []
                    for linha in linhas:
                        nome = linha["descricao"].strip() or "Linha livre"
                        try:
                            if linha["unidade"] == "hora":
                                qtd = orc_service.interpretar_horas(linha["txt_qtd"])
                            else:
                                qtd = orc_service.interpretar_numero(linha["txt_qtd"])
                            valor = orc_service.interpretar_valor(linha["txt_valor"])
                        except ValueError as erro:
                            erros.append(f"**{nome}**: {erro}")
                            continue
                        if not qtd:
                            continue
                        valor = valor if valor else linha["preco_tabela"]
                        if not valor:
                            sem_valor.append(nome)
                            continue
                        entradas.append({
                            "descricao": linha["descricao"], "quantidade": qtd,
                            "pessoas": linha["pessoas"], "valor_unitario": valor,
                            "unidade": linha["unidade"], "categoria": linha["categoria"]})

                    if erros:
                        # Não salva nada: o formulário continua preenchido para correção.
                        st.error("Corrija antes de salvar:\n\n" + "\n\n".join(erros))
                    else:
                        gravados = orc_service.substituir_itens(o["id"], entradas)
                        st.session_state["orcamento_aberto"] = o["id"]
                        if sem_valor:
                            st.warning("Ignorado por falta de valor: " + ", ".join(sem_valor))
                        st.success(f"{gravados} serviço(s) salvos no orçamento.")
                        st.rerun()

            # ---------------------------------------------------------- resumo
            if detalhe["itens"]:
                with st.container(border=True):
                    st.markdown("**Resumo do cálculo**")
                    for item in detalhe["itens"]:
                        r1, r2 = st.columns([4, 1.4])
                        r1.markdown(
                            f"<span style='font-size:0.95rem'>{theme.esc(item['descricao'])}</span> "
                            f"<span style='color:{theme.TEXTO_SECUNDARIO};font-size:0.85rem'>"
                            f"· {theme.esc(formatar_quantidade(item['quantidade'], item['unidade']))}"
                            f" × {item['pessoas']} pessoa(s) × "
                            f"{formatar_moeda(item['valor_unitario'])}</span>",
                            unsafe_allow_html=True)
                        r2.markdown(f"<div style='text-align:right;font-weight:700'>"
                                    f"{formatar_moeda(item['subtotal'])}</div>",
                                    unsafe_allow_html=True)

            st.divider()

            # ---------------------------------------------------------- dados
            with st.form(f"form_dados_orc_{o['id']}"):
                st.markdown("#### Dados da proposta")
                d1, d2, d3 = st.columns([2, 2, 1.3])
                ed_titulo = d1.text_input("Título do projeto", value=o["titulo"],
                                           key=f"ot_{o['id']}")
                ed_cliente = d2.text_input("Cliente (empresa)", value=o["cliente_nome"],
                                            key=f"oc_{o['id']}")
                ed_status = d3.selectbox(
                    "Status", orc_service.STATUS,
                    index=orc_service.STATUS.index(o["status"])
                    if o["status"] in orc_service.STATUS else 0, key=f"os_{o['id']}")

                st.markdown("**Contato do cliente**")
                c1, c2, c3 = st.columns(3)
                ed_contato = c1.text_input("Nome do contato",
                                            value=detalhe.get("cliente_contato") or "",
                                            key=f"occ_{o['id']}")
                ed_email = c2.text_input("E-mail", value=detalhe.get("cliente_email") or "",
                                          key=f"oce_{o['id']}")
                ed_tel = c3.text_input("Telefone", value=detalhe.get("cliente_telefone") or "",
                                        key=f"oct_{o['id']}")

                st.markdown("**Responsável e datas**")
                opcoes_resp = ["—"] + nomes_socios
                resp_atual = detalhe.get("responsavel_nome") or "—"
                if resp_atual not in opcoes_resp:
                    opcoes_resp.append(resp_atual)
                e1, e2, e3, e4 = st.columns(4)
                ed_resp = e1.selectbox("Responsável Claquete", opcoes_resp,
                                        index=opcoes_resp.index(resp_atual),
                                        key=f"or_{o['id']}")
                ed_data = e2.date_input(
                    "Data de emissão",
                    value=date.fromisoformat(o["data"][:10]) if o["data"] else date.today(),
                    format="DD/MM/YYYY", key=f"od_{o['id']}")
                ed_validade = _number_input_seguro(
                    e3, "Validade (dias)", f"ov_{o['id']}", min_value=1,
                    value=int(o["validade_dias"] or 15), step=1)
                ed_evento = e4.date_input(
                    "Data do evento",
                    value=(date.fromisoformat(detalhe["data_evento"][:10])
                           if detalhe.get("data_evento") else None),
                    format="DD/MM/YYYY", key=f"oev_{o['id']}")

                f1, f2 = st.columns([2, 1])
                ed_prazo = f1.text_input("Prazo de entrega",
                                          value=detalhe.get("prazo_entrega") or "",
                                          key=f"opz_{o['id']}",
                                          placeholder="Ex: 15 dias úteis após a captação")
                ed_desconto = _number_input_seguro(
                    f2, "Desconto (%)", f"odesc_{o['id']}", min_value=0.0, max_value=100.0,
                    value=float(o["desconto_percent"]) if o["desconto_percent"] else None,
                    step=5.0, placeholder="0")

                ed_escopo = st.text_area(
                    "Escopo do projeto", value=detalhe.get("escopo") or "", height=100,
                    key=f"oesc_{o['id']}",
                    placeholder="O que será entregue: formato, duração, quantidade de "
                                "vídeos/fotos, rodadas de alteração...")
                ed_cond = st.text_area(
                    "Condições de pagamento", value=o["condicoes"] or "", height=70,
                    key=f"ocond_{o['id']}",
                    placeholder="Ex: 50% na assinatura e 50% na entrega final.")
                ed_obs = st.text_area("Observações", value=o["observacoes"] or "",
                                       height=70, key=f"oo_{o['id']}")

                bb1, bb2 = st.columns(2)
                salvar_dados = bb1.form_submit_button("💾 Salvar dados",
                                                       width="stretch")
                gerar = bb2.form_submit_button("📄 Salvar e ver proposta",
                                                width="stretch")
                if salvar_dados or gerar:
                    orc_service.atualizar_orcamento(
                        o["id"], ed_titulo, ed_cliente, ed_data, int(ed_validade or 15),
                        ed_status, float(ed_desconto or 0), ed_obs, ed_cond,
                        responsavel_nome="" if ed_resp == "—" else ed_resp,
                        cliente_contato=ed_contato, cliente_email=ed_email,
                        cliente_telefone=ed_tel, data_evento=ed_evento,
                        prazo_entrega=ed_prazo, escopo=ed_escopo)
                    st.session_state["orcamento_aberto"] = o["id"]
                    st.session_state["proposta_id"] = o["id"]
                    st.success("Dados salvos! Abra a aba **📄 Proposta** para ver e baixar."
                               if gerar else "Dados salvos!")
                    st.rerun()

            ac1, ac2 = st.columns(2)
            if ac1.button("📋 Duplicar orçamento", key=f"dup_{o['id']}",
                          width="stretch", type="secondary"):
                st.session_state["orcamento_aberto"] = orc_service.duplicar_orcamento(o["id"])
                st.rerun()
            if ac2.button("🗑️ Excluir orçamento", key=f"delorc_{o['id']}",
                          width="stretch", type="secondary"):
                orc_service.excluir_orcamento(o["id"])
                st.session_state["orcamento_aberto"] = None
                st.rerun()

# =====================================================================
# ABA: PROPOSTA
# =====================================================================
with aba_proposta:
    todos = orc_service.listar_orcamentos()
    if not todos:
        st.info("Crie um orçamento primeiro na aba **Orçamentos**.")
    else:
        rotulos = {f"{o['titulo']} — {o['cliente_nome']}": o["id"] for o in todos}
        padrao = 0
        if st.session_state.get("proposta_id") in rotulos.values():
            padrao = list(rotulos.values()).index(st.session_state["proposta_id"])
        escolhido = st.selectbox("Qual orçamento deseja transformar em proposta?",
                                  list(rotulos.keys()), index=padrao)

        orc = orc_service.obter_orcamento(rotulos[escolhido])
        empresa = orc_service.obter_dados_empresa()
        numero = orc_service.numero_proposta(orc)

        # ---- emissões anteriores deste orçamento ----
        anteriores = [p for p in orc_service.listar_propostas_emitidas()
                      if p["orcamento_id"] == orc["id"]]
        if anteriores:
            ultima = anteriores[0]
            st.info(
                f"Este orçamento já foi emitido **{len(anteriores)} vez(es)**. Última emissão: "
                f"revisão {ultima['versao']}, em {formatar_data_br(ultima['emitida_em'])}"
                f" — {formatar_moeda(ultima['total'])}. Uma nova emissão vira a "
                f"**revisão {ultima['versao'] + 1}**; as anteriores continuam no histórico.")

        # ---- o que falta para uma proposta completa ----
        faltando = []
        if not orc["itens"]:
            faltando.append("nenhum serviço preenchido")
        if not orc.get("responsavel_nome"):
            faltando.append("responsável da Claquete")
        if not orc.get("cliente_contato") and not orc.get("cliente_email"):
            faltando.append("contato do cliente")
        if not (orc.get("condicoes") or "").strip():
            faltando.append("condições de pagamento")
        if not empresa.get("empresa_email") and not empresa.get("empresa_telefone"):
            faltando.append("contato da Claquete (aba Dados da Empresa)")
        if faltando:
            st.warning("Para uma proposta completa, ainda falta: " + ", ".join(faltando) + ".")

        col_e1, col_e2 = st.columns([1.3, 2])
        emitir = col_e1.button("📨 Emitir proposta", width="stretch",
                               disabled=not orc["itens"])
        col_e2.markdown(
            f"<div style='padding-top:6px;font-size:0.92rem;color:{theme.TEXTO_SECUNDARIO}'>"
            "Emitir registra uma <b>cópia congelada</b> no histórico — exatamente o que "
            "será enviado ao cliente — e libera o arquivo para imprimir.</div>",
            unsafe_allow_html=True)

        if emitir:
            documento = gerar_html_proposta(orc, empresa, numero, para_impressao=True)
            registro = orc_service.emitir_proposta(
                orc["id"], documento, _logo(), auth.usuario_logado())
            st.session_state["ultima_emitida"] = registro["id"]
            st.session_state["ultima_emitida_orc"] = orc["id"]
            st.rerun()

        # ---- download da proposta que acabou de ser emitida ----
        if (st.session_state.get("ultima_emitida")
                and st.session_state.get("ultima_emitida_orc") == orc["id"]):
            doc = orc_service.obter_documento_emitido(
                st.session_state["ultima_emitida"], _logo())
            if doc:
                emitida = next((p for p in orc_service.listar_propostas_emitidas()
                                if p["id"] == st.session_state["ultima_emitida"]), None)
                revisao = f" (revisão {emitida['versao']})" if emitida else ""
                st.success(f"Proposta Nº {numero}{revisao} emitida e salva no histórico.")
                nome_cliente = "".join(c for c in orc["cliente_nome"] if c.isalnum() or c in " -_")
                st.download_button(
                    "⬇️ Baixar proposta para imprimir", data=doc.encode("utf-8"),
                    file_name=f"Proposta_Claquete_{numero}_{nome_cliente.strip().replace(' ', '_')}.html",
                    mime="text/html", width="stretch")
                st.caption("Abra o arquivo baixado e clique em **Imprimir / Salvar em PDF**. "
                           "Na impressão, escolha **Salvar como PDF** e desmarque "
                           "**Cabeçalhos e rodapés**.")

        st.write("")
        st.markdown("**Pré-visualização**")
        # O documento só contém texto escapado (ver ui/proposta.py), por isso
        # pode ser exibido num iframe.
        st.iframe(gerar_html_proposta(orc, empresa, numero, para_impressao=False),
                  height=1250)

# =====================================================================
# ABA: HISTÓRICO DE PROPOSTAS
# =====================================================================
with aba_historico:
    st.markdown("### Propostas enviadas")
    st.caption("Cada linha é uma cópia congelada, exatamente como foi enviada ao cliente. "
               "Alterar o orçamento depois não muda as propostas já emitidas.")

    hist_ini, hist_fim = seletor_periodo("historico", atalho_padrao="Todo o período")
    h_ini_iso, h_fim_iso = periodo_iso(hist_ini, hist_fim)

    todas = orc_service.listar_propostas_emitidas(data_ini=h_ini_iso, data_fim=h_fim_iso)
    clientes_hist = sorted({p["cliente_nome"] for p in todas})
    filtro = st.selectbox("Filtrar por cliente", ["Todos"] + clientes_hist,
                          key="filtro_hist_cliente")
    if filtro != "Todos":
        todas = [p for p in todas if p["cliente_nome"] == filtro]

    # Indicadores consideram só a versão mais recente de cada orçamento
    vigentes = [p for p in todas if not p["substituida"]]
    aprovadas = [p for p in vigentes if p["status_atual"] == "Aprovado"]
    decididas = [p for p in vigentes if p["status_atual"] in ("Aprovado", "Recusado")]
    k1, k2, k3, k4 = st.columns(4)
    theme.kpi_card(k1, "Propostas emitidas", str(len(vigentes)),
                   f"{len(todas)} contando revisões")
    theme.kpi_card(k2, "Valor proposto", formatar_moeda(sum(p["total"] for p in vigentes)))
    theme.kpi_card(k3, "Aprovadas", formatar_moeda(sum(p["total"] for p in aprovadas)),
                   f"{len(aprovadas)} proposta(s)", theme.POSITIVO)
    theme.kpi_card(k4, "Taxa de aprovação",
                   f"{len(aprovadas) / len(decididas) * 100:.0f}%" if decididas else "—",
                   "entre aprovadas e recusadas")
    st.write("")

    if not todas:
        st.info("Nenhuma proposta emitida neste período. Emita a primeira na aba "
                "**📄 Emitir Proposta**.")

    aberta = st.session_state.get("proposta_hist_aberta")
    for p in todas:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3.4, 2, 1.7, 1.2])
            revisao = f" · rev. {p['versao']}" if p["versao"] > 1 else ""
            etiquetas = _badge(p["status_atual"] or "Excluído",
                               CORES_STATUS_ORC.get(p["status_atual"], theme.TEXTO_SECUNDARIO))
            if p["substituida"]:
                etiquetas += " " + _badge("substituída por revisão", theme.TEXTO_SECUNDARIO)
            c1.markdown(
                f"**Nº {theme.esc(p['numero'])}{revisao}** &nbsp; {etiquetas}<br>"
                f"<span style='font-size:0.9rem'>{theme.esc(p['titulo'])}</span> · "
                f"<span style='color:{theme.TEXTO_SECUNDARIO};font-size:0.9rem'>"
                f"{theme.esc(p['cliente_nome'])}</span>",
                unsafe_allow_html=True)
            quem = f" por {theme.esc(p['emitida_por'])}" if p["emitida_por"] else ""
            c2.markdown(
                f"<span style='font-size:0.88rem'>Emitida em "
                f"<b>{formatar_data_br(p['emitida_em'])}</b>{quem}</span>",
                unsafe_allow_html=True)
            c3.markdown(f"### {formatar_moeda(p['total'])}")
            rotulo_botao = "Fechar" if aberta == p["id"] else "👁️ Ver"
            if c4.button(rotulo_botao, key=f"ver_hist_{p['id']}", width="stretch"):
                st.session_state["proposta_hist_aberta"] = None if aberta == p["id"] else p["id"]
                st.rerun()

            # O documento só é buscado no banco quando a proposta é aberta —
            # carregar todos de uma vez deixaria a tela lenta com o banco na nuvem.
            if aberta == p["id"]:
                doc = orc_service.obter_documento_emitido(p["id"], _logo())
                if doc:
                    nome_cliente = "".join(ch for ch in p["cliente_nome"]
                                           if ch.isalnum() or ch in " -_")
                    b1, b2 = st.columns([2, 1])
                    b1.download_button(
                        "⬇️ Baixar esta proposta", data=doc.encode("utf-8"),
                        file_name=f"Proposta_Claquete_{p['numero']}_rev{p['versao']}_"
                                  f"{nome_cliente.strip().replace(' ', '_')}.html",
                        mime="text/html", width="stretch", key=f"dl_hist_{p['id']}")
                    confirmar = b2.checkbox("Confirmo excluir", key=f"conf_del_hist_{p['id']}")
                    if b2.button("🗑️ Excluir do histórico", key=f"del_hist_{p['id']}",
                                 width="stretch", type="secondary",
                                 disabled=not confirmar):
                        orc_service.excluir_proposta_emitida(p["id"])
                        st.session_state["proposta_hist_aberta"] = None
                        st.rerun()
                    st.iframe(doc.replace('class="barra no-print"',
                                          'class="barra no-print" style="display:none"'),
                              height=1250)

# =====================================================================
# ABA: TABELA DE PREÇOS
# =====================================================================
with aba_precos:
    st.markdown("### Quanto a Claquete cobra por cada serviço")
    st.caption("Estes valores alimentam a grade dos orçamentos. Ajuste-os à realidade da "
               "produtora — os que vieram preenchidos são só um ponto de partida.")

    with st.expander("➕ Novo serviço", expanded=False):
        with st.form("form_novo_preco", clear_on_submit=True):
            p1, p2, p3, p4 = st.columns([3, 1.3, 1.6, 2])
            nome_serv = p1.text_input("Nome do serviço*", placeholder="Ex: Captação com drone")
            unidade_serv = p2.selectbox("Cobrado por", UNIDADES)
            valor_serv = input_moeda(p3, "Valor (R$)", "valor_novo_preco")
            cat_serv = p4.selectbox("Categoria", orc_service.CATEGORIAS)
            if st.form_submit_button("Adicionar serviço", width="stretch"):
                try:
                    orc_service.criar_preco(nome_serv, unidade_serv, valor_serv, cat_serv)
                    st.success("Serviço adicionado!")
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))

    for preco in orc_service.listar_precos():
        chave_ed = f"editando_preco_{preco['id']}"
        with st.container(border=True):
            if not st.session_state.get(chave_ed, False):
                c1, c2, c3, c4, c5 = st.columns([3.4, 2, 1.6, 1.1, 1.1])
                c1.markdown(f"**{theme.esc(preco['nome'])}**  \n"
                            f"<span style='font-size:0.8rem;color:{theme.TEXTO_SECUNDARIO}'>"
                            f"{theme.esc(preco['categoria'])}</span>", unsafe_allow_html=True)
                c2.markdown(f"### {formatar_moeda(preco['valor_unitario'])}")
                c3.markdown(f"<span style='color:{theme.TEXTO_SECUNDARIO}'>por "
                            f"{theme.esc(preco['unidade'])}</span>", unsafe_allow_html=True)
                if c4.button("✏️", key=f"btn_ed_preco_{preco['id']}", width="stretch"):
                    st.session_state[chave_ed] = True
                    st.rerun()
                ativo = c5.toggle("Ativo", value=bool(preco["ativo"]),
                                   key=f"ativo_preco_{preco['id']}")
                if ativo != bool(preco["ativo"]):
                    orc_service.alternar_ativo_preco(preco["id"], ativo)
                    st.rerun()
            else:
                with st.form(f"form_ed_preco_{preco['id']}"):
                    e1, e2, e3, e4 = st.columns([3, 1.3, 1.6, 2])
                    ed_nome = e1.text_input("Nome*", value=preco["nome"], key=f"pn_{preco['id']}")
                    ed_un = e2.selectbox("Cobrado por", UNIDADES,
                                         index=UNIDADES.index(preco["unidade"])
                                         if preco["unidade"] in UNIDADES else 0,
                                         key=f"pu_{preco['id']}")
                    ed_valor = input_moeda(e3, "Valor (R$)", f"pv_{preco['id']}",
                                            valor_inicial=float(preco["valor_unitario"]))
                    ed_cat = e4.selectbox("Categoria", orc_service.CATEGORIAS,
                                          index=orc_service.CATEGORIAS.index(preco["categoria"])
                                          if preco["categoria"] in orc_service.CATEGORIAS else 0,
                                          key=f"pc_{preco['id']}")
                    b1, b2, b3 = st.columns(3)
                    if b1.form_submit_button("💾 Salvar", width="stretch"):
                        orc_service.atualizar_preco(preco["id"], ed_nome, ed_un, ed_valor, ed_cat)
                        st.session_state[chave_ed] = False
                        st.rerun()
                    if b2.form_submit_button("🗑️ Excluir", width="stretch"):
                        orc_service.excluir_preco(preco["id"])
                        st.session_state[chave_ed] = False
                        st.rerun()
                    if b3.form_submit_button("Cancelar", width="stretch"):
                        st.session_state[chave_ed] = False
                        st.rerun()

# =====================================================================
# ABA: DADOS DA EMPRESA
# =====================================================================
with aba_empresa:
    st.markdown("### Dados da Claquete nas propostas")
    st.caption("Estas informações aparecem no quadro da Claquete e no rodapé de todas as "
               "propostas. Preencha uma vez; campos vazios simplesmente não aparecem.")
    dados = orc_service.obter_dados_empresa()
    with st.form("form_dados_empresa"):
        novos = {}
        campos = orc_service.CAMPOS_EMPRESA
        for i in range(0, len(campos), 2):
            colunas = st.columns(2)
            for coluna, (chave, rotulo, _) in zip(colunas, campos[i:i + 2]):
                novos[chave] = coluna.text_input(rotulo, value=dados.get(chave, ""),
                                                  key=f"emp_{chave}")
        if st.form_submit_button("💾 Salvar dados da empresa", width="stretch"):
            orc_service.salvar_dados_empresa(novos)
            st.success("Dados da empresa salvos!")
            st.rerun()
