"""
Página: Agenda / Planner
-------------------------
Quadro de tarefas da equipe: o que cada sócio está fazendo, com prazo e
situação (A Fazer, Em Andamento, Concluída e Atrasada).

Sobre o status "Atrasada": ele não é escolhido por ninguém — o sistema
calcula sozinho, comparando o prazo com a data de hoje. Uma tarefa sai
automaticamente dessa condição quando é concluída ou quando o prazo é
esticado.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
from database import init_db
from db_utils import formatar_data_br
from services import eventos as eventos_service
from services import socios as socios_service
from services import tarefas as tarefas_service
from ui import charts, theme
from ui.componentes import periodo_iso, seletor_periodo

st.set_page_config(page_title="Agenda · Claquete",
                   page_icon="assets/claquete_monograma.png", layout="wide")
init_db()
theme.injetar_css()
auth.exigir_login()
theme.menu_lateral()
theme.cabecalho("Agenda da Equipe",
                "O que cada sócio está fazendo, com prazos e situação de cada tarefa.")

CORES_SITUACAO = {
    "A Fazer": theme.TEXTO_SECUNDARIO,
    "Em Andamento": theme.ALERTA,
    "Concluída": theme.POSITIVO,
    "Atrasada": theme.NEGATIVO,
}
ICONES_SITUACAO = {
    "A Fazer": "○", "Em Andamento": "◐", "Concluída": "●", "Atrasada": "⚠",
}
CORES_PRIORIDADE = {
    "Alta": theme.NEGATIVO, "Normal": theme.TEXTO_SECUNDARIO, "Baixa": theme.CIANO,
}

data_ini, data_fim = seletor_periodo("agenda", atalho_padrao="Este mês")
data_ini_iso, data_fim_iso = periodo_iso(data_ini, data_fim)
st.write("")

socios_ativos = socios_service.listar_socios(apenas_ativos=True)
projetos = eventos_service.listar_eventos()


def _badge_situacao(situacao: str) -> str:
    cor = CORES_SITUACAO.get(situacao, theme.TEXTO_SECUNDARIO)
    icone = ICONES_SITUACAO.get(situacao, "○")
    return (f'<span class="badge" style="background-color:{cor}22;color:{cor};'
            f'border:1px solid {cor}55">{icone} {situacao}</span>')


def _texto_prazo(tarefa: dict) -> str:
    if not tarefa["data_prazo"]:
        return "sem prazo"
    texto = formatar_data_br(tarefa["data_prazo"])
    dias = tarefa["dias_restantes"]
    if dias is None:
        return texto
    if dias < 0:
        return f"{texto} · {abs(dias)} dia(s) em atraso"
    if dias == 0:
        return f"{texto} · vence hoje"
    if dias <= 7:
        return f"{texto} · em {dias} dia(s)"
    return texto


# ----------------------------------------------------------------- KPIs
resumo = tarefas_service.resumo_por_status(data_ini_iso, data_fim_iso)
c1, c2, c3, c4 = st.columns(4)
theme.kpi_card(c1, "A Fazer", str(resumo["A Fazer"]))
theme.kpi_card(c2, "Em Andamento", str(resumo["Em Andamento"]), "", theme.ALERTA)
theme.kpi_card(c3, "Concluídas", str(resumo["Concluída"]), "", theme.POSITIVO)
theme.kpi_card(c4, "Atrasadas", str(resumo["Atrasada"]),
               "precisam de atenção" if resumo["Atrasada"] else "tudo em dia",
               theme.NEGATIVO if resumo["Atrasada"] else theme.POSITIVO)

st.write("")

aba_quadro, aba_prazos, aba_equipe = st.tabs(
    ["🗂️ Quadro de Tarefas", "📅 Próximos Prazos", "👥 Por Sócio"]
)

# =====================================================================
# ABA: QUADRO DE TAREFAS
# =====================================================================
with aba_quadro:
    with st.expander("➕ Nova tarefa", expanded=False):
        with st.form("form_nova_tarefa", clear_on_submit=True):
            titulo = st.text_input("O que precisa ser feito?*",
                                    placeholder="Ex: Editar vídeo institucional do cliente X")
            c1, c2, c3 = st.columns(3)
            responsavel = c1.selectbox(
                "Responsável", ["— sem responsável —"] + [s["nome"] for s in socios_ativos])
            prazo = c2.date_input("Prazo", value=date.today() + timedelta(days=7),
                                   format="DD/MM/YYYY")
            prioridade = c3.selectbox("Prioridade", tarefas_service.PRIORIDADES, index=1)

            c4, c5 = st.columns(2)
            status_inicial = c4.selectbox("Situação inicial", tarefas_service.STATUS)
            projeto_vinculado = c5.selectbox(
                "Vincular a um projeto (opcional)",
                ["— nenhum —"] + [p["nome"] for p in projetos])

            descricao = st.text_area("Detalhes (opcional)", height=80)

            if st.form_submit_button("Criar tarefa", width="stretch"):
                if not titulo.strip():
                    st.error("Descreva o que precisa ser feito.")
                else:
                    socio_id = None
                    if responsavel != "— sem responsável —":
                        socio_id = next(s["id"] for s in socios_ativos
                                        if s["nome"] == responsavel)
                    evento_id = None
                    if projeto_vinculado != "— nenhum —":
                        evento_id = next(p["id"] for p in projetos
                                         if p["nome"] == projeto_vinculado)
                    tarefas_service.criar_tarefa(
                        titulo, socio_id, descricao, data_prazo=prazo,
                        status=status_inicial, prioridade=prioridade,
                        evento_id=evento_id,
                    )
                    st.success("Tarefa criada!")
                    st.rerun()

    # ---- filtros ----
    f1, f2 = st.columns(2)
    filtro_socio = f1.selectbox("Filtrar por responsável",
                                 ["Todos"] + [s["nome"] for s in socios_ativos])
    filtro_situacao = f2.selectbox("Filtrar por situação",
                                    ["Todas", "A Fazer", "Em Andamento",
                                     "Concluída", "Atrasada"])

    socio_id_filtro = None
    if filtro_socio != "Todos":
        socio_id_filtro = next(s["id"] for s in socios_ativos if s["nome"] == filtro_socio)

    lista = tarefas_service.listar_tarefas(
        socio_id=socio_id_filtro, data_ini=data_ini_iso, data_fim=data_fim_iso)
    if filtro_situacao != "Todas":
        lista = [t for t in lista if t["situacao"] == filtro_situacao]

    if not lista:
        st.info("Nenhuma tarefa encontrada para o período e filtros selecionados.")

    for t in lista:
        chave_ed = f"editando_tarefa_{t['id']}"
        with st.container(border=True):
            if not st.session_state.get(chave_ed, False):
                col1, col2, col3, col4 = st.columns([4, 2.2, 2.6, 1.2])

                cor_prio = CORES_PRIORIDADE.get(t["prioridade"], theme.TEXTO_SECUNDARIO)
                projeto_txt = (f" · 🎬 {theme.esc(t['evento_nome'])}" if t["evento_nome"] else "")
                col1.markdown(
                    f"**{theme.esc(t['titulo'])}**  \n"
                    f"<span style='font-size:0.82rem;color:{theme.TEXTO_SECUNDARIO}'>"
                    f"<span style='color:{cor_prio}'>▪ {theme.esc(t['prioridade'])}</span>"
                    f"{theme.esc(projeto_txt)}</span>",
                    unsafe_allow_html=True,
                )
                col2.markdown(
                    f"<span style='font-size:0.9rem'>👤 "
                    f"{theme.esc(t['socio_nome'] or '—')}</span>",
                    unsafe_allow_html=True,
                )
                col3.markdown(
                    f"{_badge_situacao(t['situacao'])}<br>"
                    f"<span style='font-size:0.8rem;color:{theme.TEXTO_SECUNDARIO}'>"
                    f"🗓️ {_texto_prazo(t)}</span>",
                    unsafe_allow_html=True,
                )

                with col4:
                    if t["status"] != "Concluída":
                        proximo = ("Em Andamento" if t["status"] == "A Fazer"
                                   else "Concluída")
                        rotulo = ("▶ Iniciar" if t["status"] == "A Fazer"
                                  else "✓ Concluir")
                        if st.button(rotulo, key=f"avancar_{t['id']}",
                                     width="stretch"):
                            tarefas_service.mudar_status(t["id"], proximo)
                            st.rerun()
                    else:
                        if st.button("↩ Reabrir", key=f"reabrir_{t['id']}",
                                     width="stretch", type="secondary"):
                            tarefas_service.mudar_status(t["id"], "Em Andamento")
                            st.rerun()
                    if st.button("✏️", key=f"editar_tarefa_{t['id']}",
                                 width="stretch", type="secondary"):
                        st.session_state[chave_ed] = True
                        st.rerun()

                if t["descricao"]:
                    st.caption(t["descricao"])
            else:
                st.markdown(f"#### ✏️ Editando: {t['titulo']}")
                with st.form(f"form_edit_tarefa_{t['id']}"):
                    ed_titulo = st.text_input("Título*", value=t["titulo"],
                                               key=f"et_{t['id']}")
                    e1, e2, e3 = st.columns(3)
                    nomes = ["— sem responsável —"] + [s["nome"] for s in socios_ativos]
                    indice_resp = (nomes.index(t["socio_nome"])
                                   if t["socio_nome"] in nomes else 0)
                    ed_resp = e1.selectbox("Responsável", nomes, index=indice_resp,
                                            key=f"er_{t['id']}")
                    ed_prazo = e2.date_input(
                        "Prazo",
                        value=(date.fromisoformat(t["data_prazo"][:10])
                               if t["data_prazo"] else date.today()),
                        format="DD/MM/YYYY", key=f"ep_{t['id']}",
                    )
                    ed_prioridade = e3.selectbox(
                        "Prioridade", tarefas_service.PRIORIDADES,
                        index=tarefas_service.PRIORIDADES.index(t["prioridade"])
                        if t["prioridade"] in tarefas_service.PRIORIDADES else 1,
                        key=f"epr_{t['id']}",
                    )
                    ed_status = st.selectbox(
                        "Situação", tarefas_service.STATUS,
                        index=tarefas_service.STATUS.index(t["status"])
                        if t["status"] in tarefas_service.STATUS else 0,
                        key=f"es_{t['id']}",
                    )
                    ed_desc = st.text_area("Detalhes", value=t["descricao"] or "",
                                            height=80, key=f"ed_{t['id']}")

                    b1, b2, b3 = st.columns(3)
                    salvar = b1.form_submit_button("💾 Salvar", width="stretch")
                    excluir = b2.form_submit_button("🗑️ Excluir",
                                                     width="stretch")
                    cancelar = b3.form_submit_button("Cancelar",
                                                      width="stretch")

                    if salvar:
                        if not ed_titulo.strip():
                            st.error("O título não pode ficar vazio.")
                        else:
                            novo_socio = None
                            if ed_resp != "— sem responsável —":
                                novo_socio = next(s["id"] for s in socios_ativos
                                                  if s["nome"] == ed_resp)
                            tarefas_service.atualizar_tarefa(
                                t["id"], ed_titulo, ed_desc, novo_socio,
                                t["data_inicio"], ed_prazo, ed_status,
                                ed_prioridade, t["evento_id"],
                            )
                            st.session_state[chave_ed] = False
                            st.success("Tarefa atualizada!")
                            st.rerun()
                    if excluir:
                        tarefas_service.excluir_tarefa(t["id"])
                        st.session_state[chave_ed] = False
                        st.rerun()
                    if cancelar:
                        st.session_state[chave_ed] = False
                        st.rerun()

# =====================================================================
# ABA: PRÓXIMOS PRAZOS
# =====================================================================
with aba_prazos:
    st.markdown("### ⚠️ Atrasadas")
    atrasadas = tarefas_service.listar_tarefas(apenas_atrasadas=True)
    if atrasadas:
        for t in atrasadas:
            st.markdown(
                f"- **{t['titulo']}** — {t['socio_nome'] or 'sem responsável'} · "
                f"{_texto_prazo(t)}"
            )
    else:
        st.success("Nenhuma tarefa atrasada. 👏")

    st.markdown("### 📅 Próximos 14 dias")
    hoje = date.today()
    limite = hoje + timedelta(days=14)
    proximas = [
        t for t in tarefas_service.listar_tarefas(
            data_ini=hoje.isoformat(), data_fim=limite.isoformat())
        if t["status"] != "Concluída" and not t["atrasada"] and t["data_prazo"]
    ]
    if proximas:
        linhas = [{
            "Prazo": formatar_data_br(t["data_prazo"]),
            "Tarefa": t["titulo"],
            "Responsável": t["socio_nome"] or "—",
            "Situação": t["situacao"],
            "Prioridade": t["prioridade"],
        } for t in proximas]
        st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
    else:
        st.info("Nada com prazo nos próximos 14 dias.")

# =====================================================================
# ABA: POR SÓCIO
# =====================================================================
with aba_equipe:
    por_socio = tarefas_service.resumo_por_socio(data_ini_iso, data_fim_iso)
    if not por_socio:
        st.info("Cadastre sócios para acompanhar a distribuição das tarefas.")
    else:
        colunas = st.columns(len(por_socio))
        for col, s in zip(colunas, por_socio):
            theme.kpi_card(
                col, s["nome"], str(s["total"]),
                f"{s['atrasadas']} atrasada(s)" if s["atrasadas"] else "em dia",
                theme.NEGATIVO if s["atrasadas"] else theme.POSITIVO,
            )

        st.write("")
        with st.container(border=True):
            charts.renderizar(charts.grafico_barras_comparativo(
                [s["nome"] for s in por_socio],
                [
                    {"nome": "A Fazer",
                     "valores": [s["a_fazer"] for s in por_socio],
                     "cor": theme.TEXTO_SECUNDARIO},
                    {"nome": "Em Andamento",
                     "valores": [s["em_andamento"] for s in por_socio],
                     "cor": theme.ALERTA},
                    {"nome": "Concluídas",
                     "valores": [s["concluidas"] for s in por_socio],
                     "cor": theme.POSITIVO},
                    {"nome": "Atrasadas",
                     "valores": [s["atrasadas"] for s in por_socio],
                     "cor": theme.NEGATIVO},
                ],
                "Tarefas por Sócio", moeda=False,
            ))
