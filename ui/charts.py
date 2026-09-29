"""
ui/charts.py
------------
Gráficos do sistema, estilizados com a identidade da Claquete: fundo grafite,
amarelo/ciano/lima nas séries principais, tipografia Space Grotesk/Inter e
rótulos de valor diretamente no gráfico (para leitura sem precisar passar
o mouse).

Todas as funções devolvem um `go.Figure`; use `renderizar(fig)` para exibir.
"""

import plotly.graph_objects as go
import streamlit as st

from ui.theme import (
    ALERTA, BORDA, BRANCO, CINZA_TEXTO, CORES_GRAFICO, CORES_STATUS_EVENTO,
    AMARELO, AZUL, CIANO, FUNDO, LIMA, NEGATIVO, POSITIVO, PRIMARIA,
    SUPERFICIE, TEAL, TEXTO_SECUNDARIO,
)

FONTE_BASE = dict(family="Inter, sans-serif", color=CINZA_TEXTO, size=14.5)
FONTE_TITULO = dict(family="Space Grotesk, Inter, sans-serif", color=BRANCO, size=19)
GRADE = "rgba(255,255,255,0.06)"


def _moeda_curta(valor: float) -> str:
    """Formata valores para caber nos rótulos do gráfico (ex: R$ 12,5 mil)."""
    if valor is None:
        return "—"
    negativo = valor < 0
    v = abs(valor)
    if v >= 1_000_000:
        texto = f"R$ {v/1_000_000:.1f}M".replace(".", ",")
    elif v >= 1_000:
        texto = f"R$ {v/1_000:.1f} mil".replace(".", ",")
    else:
        texto = f"R$ {v:.0f}"
    return f"-{texto}" if negativo else texto


def _rotulo_mes(referencia: str) -> str:
    """Converte '2026-09' em 'set/26', para eixos mais limpos."""
    meses = ["jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"]
    try:
        ano, mes = referencia.split("-")
        return f"{meses[int(mes) - 1]}/{ano[2:]}"
    except (ValueError, IndexError):
        return referencia


def _layout_base(fig: go.Figure, titulo: str = "", altura: int = 380,
                 legenda_embaixo: bool = True) -> go.Figure:
    fig.update_layout(
        title=dict(text=titulo, font=FONTE_TITULO, x=0, xanchor="left", y=0.96) if titulo else None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=FONTE_BASE,
        height=altura,
        margin=dict(l=8, r=14, t=58 if titulo else 18, b=8),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=TEXTO_SECUNDARIO, size=13.5),
            orientation="h" if legenda_embaixo else "v",
            yanchor="bottom", y=-0.22 if legenda_embaixo else 1,
            xanchor="left", x=0,
        ),
        hoverlabel=dict(
            bgcolor=SUPERFICIE, font=dict(color=BRANCO, family="Inter, sans-serif", size=14),
            bordercolor=PRIMARIA,
        ),
        separators=",.",
    )
    # fixedrange=True desativa zoom e arraste: os gráficos ficam sempre no
    # enquadramento correto, sem o usuário conseguir "perder" a visualização.
    fig.update_xaxes(gridcolor=GRADE, zerolinecolor="rgba(255,255,255,0.14)",
                     linecolor=BORDA, tickfont=dict(size=14, color=CINZA_TEXTO),
                     fixedrange=True)
    fig.update_yaxes(gridcolor=GRADE, zerolinecolor="rgba(255,255,255,0.14)",
                     linecolor=BORDA, tickfont=dict(size=14, color=CINZA_TEXTO),
                     fixedrange=True)
    return fig


def renderizar(fig: go.Figure) -> None:
    """Exibe o gráfico já sem as ferramentas de zoom do Plotly."""
    st.plotly_chart(
        fig,
        width="stretch",
        config={
            "displayModeBar": False,   # esconde a barra de ferramentas
            "scrollZoom": False,       # desativa zoom com a roda do mouse
            "doubleClick": False,      # desativa zoom por duplo clique
            "showTips": False,
            # Faz o gráfico se redesenhar quando o espaço disponível muda —
            # é o que permite que ele acompanhe o recolher da barra lateral.
            "responsive": True,
        },
    )


def _grafico_vazio(titulo: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text="Sem dados neste período",
        showarrow=False,
        font=dict(color=TEXTO_SECUNDARIO, size=15, family="Inter, sans-serif"),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _layout_base(fig, titulo, altura=250, legenda_embaixo=False)


# ---------------------------------------------------------------------------
# Fluxo de caixa
# ---------------------------------------------------------------------------

def grafico_evolucao_caixa(dados: list, titulo: str = "Evolução do Fluxo de Caixa") -> go.Figure:
    """Entradas x saídas por mês, com a linha do saldo acumulado por cima."""
    if not dados:
        return _grafico_vazio(titulo)

    meses = [_rotulo_mes(d["mes"]) for d in dados]
    entradas = [d["entradas"] for d in dados]
    saidas = [-d["saidas"] for d in dados]
    saldos = [d["saldo_acumulado"] for d in dados]

    fig = go.Figure()
    fig.add_bar(
        x=meses, y=entradas, name="Entradas",
        marker=dict(color=POSITIVO, line=dict(width=0)),
        text=[_moeda_curta(v) if v else "" for v in entradas],
        textposition="outside", textfont=dict(size=12.5, color=POSITIVO),
        hovertemplate="<b>%{x}</b><br>Entradas: R$ %{y:,.2f}<extra></extra>",
    )
    fig.add_bar(
        x=meses, y=saidas, name="Saídas",
        marker=dict(color=NEGATIVO, line=dict(width=0)),
        text=[_moeda_curta(v) if v else "" for v in saidas],
        textposition="outside", textfont=dict(size=12.5, color=NEGATIVO),
        hovertemplate="<b>%{x}</b><br>Saídas: R$ %{y:,.2f}<extra></extra>",
    )
    fig.add_trace(go.Scatter(
        x=meses, y=saldos, name="Saldo acumulado", mode="lines+markers",
        line=dict(color=CIANO, width=3.5, shape="spline"),
        marker=dict(size=9, color=BRANCO, line=dict(color=CIANO, width=2.5)),
        hovertemplate="<b>%{x}</b><br>Saldo acumulado: R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="relative", bargap=0.30)
    return _layout_base(fig, titulo, altura=420)


def grafico_distribuicao_categoria(dados: list, titulo: str = "Distribuição por Categoria") -> go.Figure:
    """Rosca com as categorias, já com percentual e legenda legível."""
    if not dados:
        return _grafico_vazio(titulo)
    labels = [d["categoria"] for d in dados]
    valores = [d["total"] for d in dados]
    fig = go.Figure(data=[go.Pie(
        labels=labels, values=valores, hole=0.62, sort=True,
        marker=dict(colors=CORES_GRAFICO, line=dict(color=FUNDO, width=3)),
        textinfo="percent", textposition="inside",
        textfont=dict(color=BRANCO, size=14.5, family="Space Grotesk, sans-serif"),
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f} (%{percent})<extra></extra>",
    )])
    total = sum(valores)
    fig.add_annotation(
        text=f"<b>{_moeda_curta(total)}</b><br><span style='font-size:11px'>total</span>",
        showarrow=False, font=dict(color=BRANCO, size=17, family="Space Grotesk, sans-serif"),
    )
    return _layout_base(fig, titulo, altura=400)


# ---------------------------------------------------------------------------
# Barras
# ---------------------------------------------------------------------------

def grafico_barra_horizontal(labels: list, valores: list, titulo: str = "",
                              cor_gradiente: bool = True) -> go.Figure:
    """Ranking horizontal, com as barras coloridas nas cores da marca."""
    if not labels:
        return _grafico_vazio(titulo)

    n = len(labels)
    if cor_gradiente and n > 1:
        paleta = [AMARELO, LIMA, CIANO, AZUL, TEAL, BRANCO]
        cores = [paleta[int(i * (len(paleta) - 1) / (n - 1))] for i in range(n)]
    else:
        cores = [AMARELO] * n

    fig = go.Figure(go.Bar(
        x=valores, y=labels, orientation="h",
        marker=dict(color=cores, line=dict(width=0)),
        text=[_moeda_curta(v) for v in valores],
        textposition="outside", textfont=dict(size=12.5, color=BRANCO),
        hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
    ))
    fig.update_layout(yaxis=dict(autorange="reversed"), bargap=0.35)
    fig.update_xaxes(showticklabels=False, showgrid=False)
    maximo = max(valores) if valores else 0
    fig.update_xaxes(range=[0, maximo * 1.22 if maximo else 1])
    return _layout_base(fig, titulo, altura=max(300, 62 * n + 90), legenda_embaixo=False)


def grafico_barras_comparativo(categorias: list, series: list, titulo: str = "",
                                altura: int = 400, moeda: bool = True) -> go.Figure:
    """
    Barras agrupadas genéricas.
    `series` é uma lista de dicionários: {"nome": str, "valores": list, "cor": str}

    `moeda=False` formata os rótulos como números simples — usado, por exemplo,
    para contagem de tarefas, onde "R$ 3" não faria sentido.
    """
    if not categorias:
        return _grafico_vazio(titulo)
    fig = go.Figure()
    for serie in series:
        if moeda:
            rotulos = [_moeda_curta(v) if v else "" for v in serie["valores"]]
            dica = "<b>%{x}</b><br>" + serie["nome"] + ": R$ %{y:,.2f}<extra></extra>"
        else:
            rotulos = [str(int(v)) if v else "" for v in serie["valores"]]
            dica = "<b>%{x}</b><br>" + serie["nome"] + ": %{y}<extra></extra>"
        fig.add_bar(
            x=categorias, y=serie["valores"], name=serie["nome"],
            marker=dict(color=serie.get("cor", AMARELO), line=dict(width=0)),
            text=rotulos,
            textposition="outside", textfont=dict(size=12.5, color=serie.get("cor", BRANCO)),
            hovertemplate=dica,
        )
    fig.update_layout(barmode="group", bargap=0.30, bargroupgap=0.08)
    return _layout_base(fig, titulo, altura=altura)


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------

def grafico_funil_eventos(dados: list) -> go.Figure:
    """Funil de projetos por status, na ordem natural do processo comercial."""
    ordem = ["Orçamento", "Confirmado", "Em Produção", "Concluído"]
    mapa = {d["status"]: d for d in dados}
    labels = [s for s in ordem if s in mapa]
    if not labels:
        return _grafico_vazio("Funil de Projetos")

    quantidades = [mapa[s]["quantidade"] for s in labels]
    valores = [mapa[s]["valor"] for s in labels]

    fig = go.Figure(go.Funnel(
        y=labels, x=quantidades,
        marker=dict(
            color=[CORES_STATUS_EVENTO.get(s, AMARELO) for s in labels],
            line=dict(color=FUNDO, width=2),
        ),
        textinfo="value",
        textfont=dict(size=14, color=BRANCO, family="Space Grotesk, sans-serif"),
        customdata=valores,
        hovertemplate="<b>%{y}</b><br>%{x} projeto(s)<br>R$ %{customdata:,.2f}<extra></extra>",
        connector=dict(line=dict(color=BORDA, width=1)),
    ))
    return _layout_base(fig, "Funil de Projetos por Status", altura=380, legenda_embaixo=False)


def grafico_recebido_vs_pendente(dados: list, titulo: str = "Recebido x Pendente por Projeto") -> go.Figure:
    """Barras empilhadas mostrando, projeto a projeto, o quanto já foi pago."""
    if not dados:
        return _grafico_vazio(titulo)
    nomes = [d["nome"][:28] + ("…" if len(d["nome"]) > 28 else "") for d in dados]
    recebido = [d["total_recebido"] for d in dados]
    pendente = [d["total_pendente"] for d in dados]

    fig = go.Figure()
    fig.add_bar(
        x=recebido, y=nomes, orientation="h", name="Recebido",
        marker=dict(color=POSITIVO, line=dict(width=0)),
        hovertemplate="<b>%{y}</b><br>Recebido: R$ %{x:,.2f}<extra></extra>",
    )
    fig.add_bar(
        x=pendente, y=nomes, orientation="h", name="Pendente",
        marker=dict(color=ALERTA, line=dict(width=0)),
        hovertemplate="<b>%{y}</b><br>Pendente: R$ %{x:,.2f}<extra></extra>",
    )
    fig.update_layout(barmode="stack", bargap=0.35, yaxis=dict(autorange="reversed"))
    return _layout_base(fig, titulo, altura=max(320, 58 * len(nomes) + 110))


# ---------------------------------------------------------------------------
# DRE
# ---------------------------------------------------------------------------

def grafico_dre_evolucao(dados: list) -> go.Figure:
    """Receitas x custos por mês, com a linha de resultado por cima."""
    if not dados:
        return _grafico_vazio("Evolução Mensal do Resultado")
    meses = [_rotulo_mes(d["mes"]) for d in dados]
    resultados = [d["resultado"] for d in dados]

    fig = go.Figure()
    fig.add_bar(
        x=meses, y=[d["receitas"] for d in dados], name="Receitas",
        marker=dict(color=POSITIVO, line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>Receitas: R$ %{y:,.2f}<extra></extra>",
    )
    fig.add_bar(
        x=meses, y=[d["custos"] for d in dados], name="Custos",
        marker=dict(color=NEGATIVO, line=dict(width=0)),
        hovertemplate="<b>%{x}</b><br>Custos: R$ %{y:,.2f}<extra></extra>",
    )
    fig.add_trace(go.Scatter(
        x=meses, y=resultados, name="Resultado", mode="lines+markers",
        line=dict(color=CIANO, width=3.5, shape="spline"),
        marker=dict(size=9, color=BRANCO, line=dict(color=CIANO, width=2.5)),
        hovertemplate="<b>%{x}</b><br>Resultado: R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="group", bargap=0.32)
    return _layout_base(fig, "Evolução Mensal do Resultado", altura=420)


def grafico_resumo_dre(dre: dict) -> go.Figure:
    """
    Gráfico de colunas simples do DRE: receitas, custos e resultado lado a
    lado. Substitui o antigo gráfico de cascata, que era mais difícil de ler
    à primeira vista.
    """
    receitas = dre["receitas"]["total"]
    custos = dre["custos"]["total"]
    resultado = dre["resultado_operacional"]

    if not any(abs(v) for v in (receitas, custos, resultado)):
        return _grafico_vazio("Resumo do Período")

    rotulos = ["Receitas", "Custos e Despesas", "Resultado"]
    valores = [receitas, custos, resultado]
    cores = [POSITIVO, NEGATIVO, AMARELO if resultado >= 0 else NEGATIVO]

    fig = go.Figure(go.Bar(
        x=rotulos, y=valores,
        marker=dict(color=cores, line=dict(width=0)),
        text=[_moeda_curta(v) for v in valores],
        textposition="outside",
        textfont=dict(size=15, color=BRANCO, family="Space Grotesk, sans-serif"),
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
        width=0.55,
    ))
    limite = max(abs(v) for v in valores) or 1
    fig.update_yaxes(range=[min(0, min(valores) * 1.3), limite * 1.28])
    return _layout_base(fig, "Resumo do Período", altura=400, legenda_embaixo=False)


def grafico_detalhe_custos(dre: dict) -> go.Figure:
    """Colunas com a abertura dos custos do período, do maior para o menor."""
    c = dre["custos"]
    itens = [
        ("Custos Fixos", c["custos_fixos"]),
        ("Investimentos", c["investimentos"]),
        ("Outras Despesas", c["outras_despesas"]),
    ]
    itens = [(nome, valor) for nome, valor in itens if valor > 0]
    if not itens:
        return _grafico_vazio("Composição dos Custos")
    itens.sort(key=lambda x: x[1], reverse=True)

    nomes = [i[0] for i in itens]
    valores = [i[1] for i in itens]
    fig = go.Figure(go.Bar(
        x=nomes, y=valores,
        marker=dict(color=[AMARELO, CIANO, LIMA][:len(itens)], line=dict(width=0)),
        text=[_moeda_curta(v) for v in valores],
        textposition="outside",
        textfont=dict(size=14, color=BRANCO, family="Inter, sans-serif"),
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
        width=0.5,
    ))
    fig.update_yaxes(range=[0, max(valores) * 1.28])
    return _layout_base(fig, "Composição dos Custos", altura=380, legenda_embaixo=False)


def grafico_cascata_dre(dre: dict) -> go.Figure:
    """
    Gráfico em cascata do DRE: mostra visualmente como a receita do período
    é consumida pelos custos até chegar no resultado final.
    """
    r = dre["receitas"]
    c = dre["custos"]
    medidas = ["relative", "relative", "relative", "relative", "relative", "total"]
    rotulos = ["Receita de<br>Projetos", "Outras<br>Receitas", "Custos<br>Fixos",
               "Investimentos", "Outras<br>Despesas", "Resultado"]
    valores = [
        r["receita_projetos"], r["outras_receitas"],
        -c["custos_fixos"], -c["investimentos"], -c["outras_despesas"],
        0,
    ]
    if not any(abs(v) for v in valores):
        return _grafico_vazio("Composição do Resultado")

    fig = go.Figure(go.Waterfall(
        orientation="v", measure=medidas, x=rotulos, y=valores,
        text=[_moeda_curta(v) if v else "" for v in valores[:-1]]
             + [_moeda_curta(dre["resultado_operacional"])],
        textposition="outside",
        textfont=dict(size=12, color=BRANCO, family="Inter, sans-serif"),
        increasing=dict(marker=dict(color=POSITIVO)),
        decreasing=dict(marker=dict(color=NEGATIVO)),
        totals=dict(marker=dict(color=AMARELO)),
        connector=dict(line=dict(color=BORDA, width=1, dash="dot")),
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
    ))
    return _layout_base(fig, "Composição do Resultado no Período", altura=420, legenda_embaixo=False)


def grafico_pizza_simples(labels: list, valores: list, titulo: str = "") -> go.Figure:
    if not labels:
        return _grafico_vazio(titulo)
    fig = go.Figure(data=[go.Pie(
        labels=labels, values=valores, hole=0.58,
        marker=dict(colors=CORES_GRAFICO, line=dict(color=FUNDO, width=3)),
        textinfo="percent", textposition="inside",
        textfont=dict(color=BRANCO, size=14.5, family="Space Grotesk, sans-serif"),
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f} (%{percent})<extra></extra>",
    )])
    return _layout_base(fig, titulo, altura=400)
